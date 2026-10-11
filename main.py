import argparse
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from worker.agent import Agent, Context
from worker.browser import Browser
from worker.human import CLIHuman, ScriptedHuman
from worker.llm import GeminiLLM
from worker.memory import Memory
from worker.policy import Policy
from worker.tools import build_tools
from worker.trace import Trace
from worker.verifier import LLMVerifier



"""
Run the autonomous AI worker.

Usage:
    python main.py "Find the latest Northwind invoice and enter it into ERP"
    python main.py --demo 1
    python main.py --demo 2
    python main.py --demo 3
"""

# Three demo tasks that show different capabilities
DEMOS = {
    "1": (
        "Find the latest invoice from Northwind Traders, "
        "extract the amount and due date, enter it into our "
        "internal ERP system, and tell me once it is done."
    ),
    "2": (
        "Find the most recent Globex Logistics invoice "
        "and enter it into the ERP."
    ),
    "3": (
        "Which Northwind invoices are already in the ERP "
        "and what is the total value of unpaid ones?"
    ),
}

ERP_URL = "http://127.0.0.1:5055"

def start_erp():
    """start the sandbox ERP server in background"""
    from sandbox.erp_app import create_app
    from werkzeug.serving import make_server

    erp = create_app(flaky=True)
    server = make_server("127.0.0.1", 5055, erp, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(1)
    print(f"ERP running at {ERP_URL}")
    return server


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Task Worker")
    parser.add_argument(
        "task",
        nargs="?",
        help="The task to complete in natural language"
    )
    parser.add_argument(
        "--demo",
        choices=["1", "2", "3"],
        help="Run a preset demo task"
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto approve all write actions (for testing)"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=40,
        help="Maximum steps before giving up"
    )
    args = parser.parse_args()

    if args.demo:
        task = DEMOS[args.demo]
    elif args.task:
        task = args.task
    else:
        parser.error("Provide a task or use --demo 1/2/3")

     # Start ERP
    start_erp()

    # Setup paths
    workspace = Path("sandbox/workspace")
    run_dir = Path("runs") / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    # Read company context
    context_file = workspace / "company_context.md"
    company_context = context_file.read_text() if context_file.exists() else ""
    company_context += f"\n- The internal ERP is at {ERP_URL}\n"

    # Build all components
    llm = GeminiLLM()

    ctx = Context(
        workspace=workspace,
        browser=Browser(
            allowed_hosts={urlparse(ERP_URL).netloc}
        ),
        memory=Memory(run_dir / "memory.json"),
        human=ScriptedHuman(approve=True) if args.auto_approve else CLIHuman(),
        company_context=company_context
    )

    agent = Agent(
        llm=llm,
        tools=build_tools(),
        ctx=ctx,
        policy=Policy(),
        verifier=LLMVerifier(llm),
        trace=Trace(run_dir, verbose=True),
        max_steps=args.max_steps
    )

    # run the task

    result = agent.run(task)

    # Print final result
    print(f"\n{'='*50}")
    print(f"RESULT: {result.status.upper()}")
    print(f"{'='*50}")
    print(f"\n{result.summary}")

    if result.evidence:
        print("\nEVIDENCE:")
        for e in result.evidence:
            print(f"  • {e}")

    print(f"\nFull trace saved to: {result.run_dir}/")
    print(f"Open report:         {result.run_dir}/report.md")


if __name__ == "__main__":
    main()