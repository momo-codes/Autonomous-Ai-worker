import datetime
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from .trace import Trace
from .errors import ToolError



#how many characters to show from tool results
MAX_RESULT_CHARS = 6000

# how many recent messages to keep in full
# older ones get compressed to save space

KEEP_RECENT =8

#Instruction given to ai at every step
SYSTEM_PROMPT = """
You are an autonomous AI worker for a company.
Your job is to complete tasks end to end using tools.
You are judged on OUTCOMES - the task must actually be done and verified.

Today's date: {today}
You are on step {step} of maximum {max_steps}.

HOW TO WORK:
1. Read the goal carefully. Use the COMPANY CONTEXT to understand
   the rules, procedures and conventions.

2. Always start by gathering information:
   - List files to see what invoices exist
   - Read relevant files to extract details
   - Check the ERP to see what bills already exist

3. Save important facts with remember() right after you find them:
   - invoice number, amount, due date, vendor

4. Before entering a bill always check for duplicates in /payables

5. When filling forms:
   - Dates must be YYYY-MM-DD format (e.g. 2026-09-21)
   - Amount must be the GRAND TOTAL including tax
   - Vendor must match the ERP dropdown exactly

6. After every action read the result carefully:
   - ok=false means something went wrong, read the error and fix it
   - 503 error means temporary, just retry
   - Date format error means fix the date to YYYY-MM-DD
   - Duplicate means bill already exists

7. NEVER claim success without verifying:
   - After creating a bill, open it in the ERP
   - Check every field matches the invoice
   - Only then call finish with status=success

8. If a bill is over 10000 INR, use ask_human to get approval first.

9. Call finish only when:
   - status=success: task done AND verified in live system
   - status=failed: could not complete, explain why
   - status=blocked: need human help

COMPANY CONTEXT:
{company_context}

YOUR WORKING MEMORY (facts you saved):
{memory}
"""

@dataclass
class RunResult:
    """
    The final result of a task run.
    
    status   = "success", "failed" or "blocked"
    summary  = what happened in plain English
    evidence = list of proof points
    steps    = how many steps it took
    run_dir  = where the trace files are saved
    """
    status: str
    summary: str
    evidence: list = field(default_factory=list)
    steps: int = 0
    run_dir: str = ""


@dataclass
class Context:
    """
    Everything the agent needs to do its job.
    Passed to every tool function.
    
    workspace = Path to the inbox folder
    browser   = the Browser instance
    memory    = the Memory instance  
    human     = CLIHuman or ScriptedHuman
    company_context = contents of company_context.md
    """    
    workspace : Path
    browser:object
    memory:object
    human:object
    company_context:str=""

class Agent:
    """
    The main brain that connects everything together.
    
    The loop:
    1. Send goal + tools to Gemini
    2. Gemini picks a tool and args
    3. We run the tool
    4. We send the result back to Gemini
    5. Go to step 1
    6. Repeat until Gemini calls finish()
    
    The harness (this class) handles:
    - Approvals before write actions
    - Blocked patterns
    - Step budget (max steps)
    - Verification gate (must re-read before finish)
    - Audit logging
    - Context compression (old messages shrunk)
    """    

    def __init__(self,llm,tools,ctx,policy,verifier,trace,max_steps=40):
        self.llm = llm
        self.tools = tools
        self.ctx = ctx
        self.policy = policy
        self.verifier = verifier
        self.trace = trace
        self.max_steps = max_steps

        # Full history of tool calls for verifier and report
        self.history=[]

        # Trace repeated failures
        # If same tool+args fails 3 times -> warn agent
        self.fail_counts={}

        #True after a write action
        #Agent must re-read the system before calling finish
        self.pending_verification=False

        #How many times verifier rejected the finish
        self.verifier_rejections=0

        # set when agent calls finish
        self._final_result=None

    def run(self,goal):
        """
        Main entry point. Runs the agent loop.
        
        goal = the task from the user
        e.g. "Find the latest Northwind invoice and enter it into ERP"
        
        Returns RunResult with status, summary, evidence

        """    
        self.goal = goal
        self.trace.event("goal",goal=goal)
        self.trace.say(f"\n TASK: {goal}\n")

        # Start conversation with the goal
        messages=[
            {"role":"user","content":f"TASK: {goal}"}
        ]

        #Get tool specs to send to Gemini
        tool_specs=[t.spec() for t in self.tools.values()]

        #Track idle turns (no tool calls)
        idle_turns=0

        #Main loop
        for step in range(1, self.max_steps+1):
            #Build system prompt with current state
            system=SYSTEM_PROMPT.format(
                today=datetime.date.today().isoformat(),
                step=step,
                max_steps=self.max_steps,
                company_context=self.ctx.company_context,
                memory=self.ctx.memory.render()
            )

            #Ask Gemini what to do next
            response=self.llm.complete(
                system=system,
                messages=self._compress(messages),
                tools=tool_specs
            )

            # Add response to conversation
            messages.append({
                "role":"assistant",
                "content":response.content
            })

            #Print any thinking text
            for block in response.content:
                if block["type"]=="text" and block["text"].strip():
                    self.trace.say(
                        f"[{step}] thinking: {block['text'][:300]}"
                    )
                    self.trace.event(
                        "thought",
                        step=step,
                        text=block["text"]
                    )

            # Get all tool calls from response
            tool_calls=[
                b for b in response.content
                if b["type"] == "tool_use"
            ]        

            #No tool calls- agent is idle
            if not tool_calls:
                idle_turns+=1
                if idle_turns >=3:
                    return self._end(
                        "failed",
                        "Agent stopped calling tools without finishing.",
                        [],
                        step
                    )
                # Nudge the agent to continue
                messages.append({
                    "role": "user",
                    "content": (
                        "Please continue by calling a tool. "
                        "When task is complete and verified call finish()."
                    )
                })
                continue
            idle_turns=0

            #Run each tool call
            tool_results=[]
            for call in tool_calls:
                result = self._run_tool(call, step)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": self._clip(
                        json.dumps(result, default=str)
                    )
                })

             # Add results to conversation
            messages.append({
                "role": "user",
                "content": tool_results
            })

            # Check if agent called finish
            if self._final_result:
                return self._final_result

        # Ran out of steps
        return self._end(
            "failed",
            f"Ran out of steps ({self.max_steps}) before finishing.",
            [],
            self.max_steps
        )    


    def _run_tool(self,call,step):
        """
        Runs one tool call from the agent.
        
        Handles:
        - finish tool (special case)
        - unknown tools
        - policy check (approve/deny)
        - human approval for write actions
        - actually running the tool function
        - logging the result
        
        Example call dict:
        {
            "type": "tool_use",
            "id": "call_1",
            "name": "read_file",
            "input": {"path": "inbox/INV-2057.txt"}
        }
        
        Returns the tool result dict e.g.:
        {"ok": True, "content": "Invoice Number: INV-2057..."}
        """
        name=call["name"]
        args = call.get("input") or {}

        self.trace.say(
            f"[{step}]->{name} "
            f"{json.dumps(args, default=str)[:200]}"
        )

        t0 = time.time()
        result = self._execute(name, args)
        elapsed=round(time.time()-t0,2)

        # check for repeated failures
        if not result.get("ok",True):
            fail_key=name + json.dumps(args, sort_keys=True, default=str)
            self.fail_counts[fail_key] = self.fail_counts.get(fail_key,0)+1
            if self.fail_counts[fail_key]>=3:
                result["warning"]=(
                   "You have tried this exact action 3 times and it keeps failing. "
                    "Try a different approach or call finish with status=blocked."
                )

        # Log to trace file
        ok = result.get("ok", True)
        self.trace.say(f"     {'ok' if ok else 'FAILED'}: {self._short(result)}")
        self.trace.event(
            "tool",
            step=step,
            name=name,
            args=args,
            ok=ok,
            result=result,
            seconds=elapsed
        )

        # add history to verifier
        self.history.append({
            "step": step,
            "tool": name,
            "args": args,
            "result": result
        })

        return result

    def _execute(self,name,args):
        """
        Actually executes the tool.
        
        Flow:
        finish tool? → handle specially
        unknown tool? → return error
        policy check → allow / approve / deny
        human approval (if needed) → yes/no
        run the function → return result
        """
        # special case : finish tool
        if name in ("finish", "functions.finish"):
            return self._handle_finish(args)

        # unknown tool
        tool= self.tools.get(name)
        if not tool:
            return {
                "ok": False,
                "error": (
                    f"Unknown tool '{name}'. "
                    f"Available tools: {list(self.tools.keys())}"
                )
            }

        #POLICY CHECK   
        decision = self.policy.review(tool, args, self.ctx)

        if decision.kind=="deny":
            self.trace.event(
                "policy_deny",
                tool=name,
                reason=decision.reason
            )
            return {
                "ok": False,
                "error": f"BLOCKED by policy: {decision.reason}"
            }

        if decision.kind == "approve":
            # Ask human to approve this write action
            approved, note = self.ctx.human.approve(decision.description)
            self.trace.event(
                "approval",
                tool=name,
                description=decision.description,
                approved=approved,
                note=note
            )
            if not approved:
                return {
                    "ok": False,
                    "error": f"Human denied this action. Reason: {note}",
                    "denied_by_human": True
                }

        # run the tool function
        try:
            result = tool.fn(self.ctx, **args)
        except ToolError as e:
             return {"ok": False, "error": str(e)}
        except TypeError as e:
            return {"ok": False, "error": f"Wrong arguments for {name}: {e}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

        # mark the system was changed (needs verfication)
        if tool.mutating and result.get("ok",True):
            self.pending_verification=True

        # Mark that system was re-read (verification satisfied)
        if name=="browser_open" and result.get("ok",True):
            self.pending_verification= False

        return result


    def _handle_finish(self,args):
        """
        Handles the finish tool call.
        
        Two gates before accepting success:
        
        Gate 1 - Verification gate:
        Agent must have re-read the live system after
        the last write. If not, reject and tell it to verify.
        
        Gate 2 - Independent verifier:
        A separate AI call checks the raw log to confirm
        the work was actually done correctly.
        
        Example rejection from gate 1:
        Agent writes bill → Agent calls finish(success)
        Gate says: "You haven't re-read the ERP since writing.
                    Open the bill and verify it first."
        Agent opens bill → Agent calls finish(success) again
        Gate 1 passes → Gate 2 checks the log → passes
        Result: success ✓
        """       

        status = args.get("status","failed")
        summary = args.get("summary", "")
        evidence = args.get("evidence", [])

        # gate 1: must verify before claiming success
        if status == "success" and self.pending_verification:
            return {
                "ok": False,
                "error": (
                    "VERIFICATION GATE: You made changes but haven't "
                    "re-read the live system since. "
                    "Call browser_open to open the created bill, "
                    "check all fields match the invoice, then call finish."
                )
            }

        if status == "success":
            self.trace.say("Running independent verification...")
            passed, reason = self.verifier.verify(
                goal=self.goal,
                summary=summary,
                evidence=evidence,
                digest=self._build_digest(),
                company_context=self.ctx.company_context
            )

            self.trace.event(
                "verifier",
                passed=passed,
                reason=reason
            )
            self.trace.say(
                f"Verifier: {'PASS' if passed else 'FAIL'} - {reason}"
            )

            if not passed:
                self.verifier_rejections += 1
                if self.verifier_rejections < 2:
                    # Give agent one chance to fix
                    return {
                        "ok": False,
                        "error": (
                            f"Independent verifier rejected completion: {reason} "
                            "Fix the issue and try again."
                        )
                    }
                # After 2 rejections mark as unverified
                status = "unverified"
                summary = f"{summary} [Verifier could not confirm: {reason}]"

        self._end(status, summary, evidence, len(self.history))
        return {"ok": True, "accepted": True}

    def _end(self, status, summary, evidence, steps):
        """Creates the final result and writes the report"""
        self._final_result = RunResult(
            status=status,
            summary=summary,
            evidence=evidence,
            steps=steps,
            run_dir=str(self.trace.dir)
        )
        self.trace.event(
            "end",
            status=status,
            summary=summary,
            evidence=evidence
        )
        self.trace.write_report(
            self.goal,
            self._final_result,
            self.history
        )
        return self._final_result


    def _build_digest(self):
        """
        Builds a text summary of all tool calls.
        Sent to the verifier so it can check the work.
        
        Looks like:
        #1 list_files({}) -> {"ok": true, "entries": [...]}
        #2 read_file({"path": "inbox/INV-2057.txt"}) -> {"ok": true, ...}
        #3 remember({"key": "amount", "value": "4820.50"}) -> {"ok": true}
        #4 browser_open({"url": ".../payables"}) -> {"ok": true, ...}
        #5 browser_submit({...}) -> {"ok": true, ...}
        #6 browser_open({"url": ".../payables/BILL-0003"}) -> {"ok": true, ...}
        """
        lines = []
        for h in self.history:
            if h["tool"] == "finish":
                continue
            args_str = json.dumps(h["args"], default=str)[:300]
            result_str = json.dumps(h["result"], default=str)[:800]
            lines.append(
                f"#{h['step']} {h['tool']}({args_str}) -> {result_str}"
            )
        return "\n".join(lines)      


    def _compress(self, messages):
        """
        Compresses old messages to save context space.
        
        Gemini has a context limit.
        In long tasks old tool results take up too much space.
        
        Solution: keep recent messages in full,
        shrink old tool results to first 400 chars.
        
        Important facts are safe because agent saved them
        with remember() which injects them every step.
        """
        result = []
        cutoff = len(messages) - KEEP_RECENT

        for i, msg in enumerate(messages):
            if (i < cutoff and
                    msg["role"] == "user" and
                    isinstance(msg["content"], list)):
                shrunk = []
                for block in msg["content"]:
                    if (block.get("type") == "tool_result" and
                            len(block.get("content", "")) > 400):
                        block = {
                            **block,
                            "content": block["content"][:400] + "...[compressed]"
                        }
                    shrunk.append(block)
                msg = {**msg, "content": shrunk}
            result.append(msg)

        return result


    @staticmethod
    def _clip(text):
        """Clips long text to avoid overwhelming the context"""
        if len(text) <= MAX_RESULT_CHARS:
            return text
        return text[:MAX_RESULT_CHARS] + '..."[clipped]'

    @staticmethod
    def _short(result):
        """One line summary of a result for terminal output"""
        if not result.get("ok", True):
            err = result.get("error", result.get("title", "unknown error"))
            return f"ERROR: {str(err)[:150]}"
        if "status" in result and "url" in result:
            return f"HTTP {result['status']} {result['url']}"
        return json.dumps(result, default=str)[:150]

        