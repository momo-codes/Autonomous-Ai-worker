import json
import re



## prompt
VERIFIER_PROMPT = """
You are a strict QA auditor checking whether an AI worker
actually completed a task correctly.

You will receive:
1. The original goal
2. What the AI worker claimed it did
3. The raw log of every action the AI took

Your job is to check:
- Did the log PROVE the goal was achieved in the real system?
- Did the agent actually re-read the live system AFTER making changes?
- Do the values written match the source documents?
- Were company policy requirements followed (duplicate check, approvals)?
- Were there any unresolved errors?

Be strict. "The agent submitted the form" is NOT proof.
Proof is "the agent opened the created bill and confirmed all values match".

Reply with ONLY this JSON (no other text):
{"verdict": "pass", "reason": "one sentence explanation"}
OR
{"verdict": "fail", "reason": "one sentence explanation of what was missing"}
"""

class LLMVerifier:
    """
        An independent AI that checks the agent's work.
    
    Why independent?
    - Uses a SEPARATE AI call with different instructions
    - The verifier is SKEPTICAL, not helpful
    - Reduces chance of the agent rubber-stamping its own work
    
    Example verification:
    
    goal = "Enter latest Northwind invoice into ERP"
    
    summary = "I created BILL-0003 with amount 4820.50"
    
    evidence = [
        "BILL-0003 created at /payables/BILL-0003",
        "Verified: amount 4820.50 matches INV-2057",
        "Verified: due date 2026-10-21 matches invoice"
    ]
    
    digest = (the raw log of every tool call)
    
    Verifier checks the digest and says:
    {"verdict": "pass", "reason": "Agent re-read bill and confirmed all values"}
    
    OR if agent never re-read:
    {"verdict": "fail", "reason": "Agent never opened the bill after creating it"}
    """

    def __init__(self,llm):
        #uses the same llm client but diferent prompt
        self.llm = llm

    def verify(self,goal,summary,evidence,digest,company_context):
        """
        Checks if the agent actually completed the task.
        
        goal            = original task from user
        summary         = what agent claims it did
        evidence        = list of proof points agent provided
        digest          = raw log of all tool calls and results
        company_context = company rules (for checking policy compliance)
        
        Returns: (passed, reason)
        passed = True if work is verified, False if not
        reason = explanation of the decision
        """
        # Build the messge for the verifier
        message = f"""
            ORIGINAL GOAL:
            {goal}

            COMPANY CONTEXT:
            {company_context}

            AGENT'S CLAIM:
            {summary}

            EVIDENCE AGENT PROVIDED:
            {json.dumps(evidence, indent=2)}

            RAW ACTION LOG:
            {digest}

            Based on the raw action log, did the agent ACTUALLY complete the goal?
            """
        response = self.llm.complete(
        system=VERIFIER_PROMPT,
        messages=[{"role": "user", "content": message}],
        tools=None
        )

        text = ""
        for block in response.content:
            if block.get("type") == "text":
                text += block.get("text", "")

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return False, f"Verifier returned unexpected output: {text[:200]}"

        try:
            data = json.loads(match.group(0))
            passed = data.get("verdict") == "pass"
            reason = data.get("reason", "no reason given")
            return passed, reason
        except json.JSONDecodeError:
            return False, f"Verifier parse error: {text[:200]}"