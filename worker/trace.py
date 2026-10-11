import json
import time
from pathlib import Path


class Trace:
    """
    Records everything the agent does to a log file.
    
    Why we need this:
    1. EVIDENCE for the submission - proves the agent actually did work
    2. DEBUGGING - if something goes wrong you can see exactly what happened
    3. AUDIT TRAIL - who approved what, what the agent decided
    
    Two outputs:
    - trace.jsonl = every event as JSON (one per line)
    - report.md   = human readable summary with evidence table
    
    Example trace.jsonl content after a run:
    
    {"t":1728000001, "kind":"goal",    "goal":"Find latest invoice..."}
    {"t":1728000002, "kind":"thought", "step":1, "text":"I'll list files first"}
    {"t":1728000003, "kind":"tool",    "step":1, "name":"list_files", "ok":true}
    {"t":1728000010, "kind":"tool",    "step":2, "name":"read_file",  "ok":true}
    {"t":1728000020, "kind":"approval","tool":"browser_submit", "approved":true}
    {"t":1728000030, "kind":"verifier","passed":true}
    {"t":1728000031, "kind":"end",     "status":"success"}
    """

    def __init__(self,run_dir,verbose=True):
        """
         run_dir = folder to save files in
                  e.g. Path("runs/2026-10-10-143022")
        
        verbose = True means also print to terminal
                  False means only save to file (used in tests)
        """
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True,exist_ok=True)
        self.log_file=self.dir /'trace.json1'
        self.verbose=verbose

    def event(self,kind,**data):
        """
        Records one event to the log file.
        
        kind = what type of event it is
        data = any extra information about the event
        
        Examples:
        trace.event("goal", goal="Find latest invoice")
        trace.event("tool", step=1, name="list_files", ok=True, result={...})
        trace.event("approval", tool="browser_submit", approved=True)
        trace.event("end", status="success", summary="Bill created")
        
        Each call adds ONE line to trace.jsonl:
        {"t": 1728000001, "kind": "goal", "goal": "Find latest invoice"}
        """    

        record = {
            "t":round(time.time(),2),
            "kind":kind,
            **data
        }
        # Append to file (one json object per line)
        with self.log_file.open("a") as f:
            f.write(json.dumps(record, default=str)+"\n")

    def say(self,message):
        """
        Prints a message to terminal (if verbose=True).
        Used to show the agent's progress while it runs.
        
        Examples of what you see in terminal:
        
        TASK: Find the latest invoice from Northwind...
        
        [1] → list_files {}
             ✓ {"ok": true, "entries": ["2026-09-22..."]}
        
        [2] → read_file {"path": "inbox/2026-09-22...txt"}
             ✓ {"ok": true, "content": "Invoice Number: INV-2057..."}
        
        [3] → remember {"key": "amount", "value": "4820.50"}
             ✓ {"ok": true, "stored": "amount"}
        """        

        if self.verbose:
            print(message,flush=True)


    def write_report(self,goal,result,history):
        """
        Writes a human readable summary to report.md
        
        report.md looks like:
        
        # Run Report
        
        **Task:** Find the latest Northwind invoice...
        **Status:** success
        **Summary:** Bill BILL-0003 created successfully
        
        ## Evidence
        - BILL-0003 created at /payables/BILL-0003
        - Amount 4820.50 matches invoice INV-2057
        - Due date 2026-10-21 matches invoice
        
        ## Action Log
        | Step | Tool | Result | Detail |
        |------|------|--------|--------|
        | 1 | list_files | ok | found 6 files |
        | 2 | read_file | ok | read INV-2057 |
        | 3 | remember | ok | stored amount |
        ...
        """        

        evidence_lines=""
        for e in result.evidence:
            evidence_lines+=f"- {e}\n"
        if not evidence_lines:
            evidence_lines= "- (no evidence  recorded)\n"

        #build action log table
        # 
        table_rows=""
        for h in history:
            # shorten result for table
            detail=json.dumps(h["result"],default=str)[:80]
            ok_text = "ok" if h["result"].get("ok") else "failed"
            table_rows += (
                f"| {h['step']} "
                f"| `{h['tool']}` "
                f"| {ok_text} "
                f"| {detail} |\n"
            )       

        report = f"""# Run Report

**Task:** {goal}
**Status:** {result.status}
**Summary:** {result.summary}

## Evidence
{evidence_lines}
## Action Log
| Step | Tool | Result | Detail |
|------|------|--------|--------|
{table_rows}
"""
        (self.dir/"report.md").write_text(report,encoding="utf-8")