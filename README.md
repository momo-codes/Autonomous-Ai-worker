# Autonomous AI Task Worker

An AI agent that takes a natural language company task, figures out 
the steps itself, uses tools to do real work, handles errors, 
verifies the outcome, and reports back with evidence.

> **Demo task:** "Find the latest invoice from Northwind Traders, 
> extract the amount and due date, enter it into our internal ERP, 
> and tell me once it is done."

---

## Demo Video


---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Groq API key (free at https://console.groq.com)

### Install
```bash
git clone https://github.com/YOURUSERNAME/autonomous-ai-worker
cd autonomous-ai-worker
pip install -r requirements.txt
```

### Set API Key
```powershell
# Windows PowerShell
$env:GROQ_API_KEY="your-key-here"
```

### Run
```bash
# Demo 1 - Northwind invoice
python main.py --demo 1

# Demo 2 - Globex invoice (asks for approval - bill over 10,000)
python main.py --demo 2

# Demo 3 - Read only query
python main.py --demo 3

# Custom task
python main.py "your task here"

# Skip approval prompts
python main.py --demo 1 --auto-approve
```

---

## Architecture

User gives task
↓
Agent loop (agent.py)
↓
Gemini/Groq LLM decides next tool
↓
Tool runs (files, browser, memory)
↓
Policy checks (approve/deny writes)
↓
Human approval for write actions
↓
Result goes back to LLM
↓
Repeat until done
↓
Independent verifier checks work
↓
Report with evidence



### Files
| File | Purpose |
|---|---|
| `worker/agent.py` | Main loop - goal to completion |
| `worker/tools.py` | 8 tools the AI can use |
| `worker/browser.py` | Opens pages, fills forms |
| `worker/llm.py` | Talks to AI API |
| `worker/memory.py` | Saves facts across steps |
| `worker/policy.py` | Blocks dangerous actions |
| `worker/verifier.py` | Independent checker |
| `worker/trace.py` | Audit log |
| `sandbox/erp_app.py` | Fake company ERP |
| `sandbox/workspace/` | Invoice files + company rules |
| `main.py` | CLI entry point |

---

## How it works - The Agent Loop


Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete


1. **Understand** - reads company context to know procedures
2. **Plan** - LLM decides which tool to use next
3. **Execute** - tool runs (read file, open browser, submit form)
4. **Observe** - reads the result (errors, success, page content)
5. **Adapt** - if 503 error → retry, if date format wrong → fix it
6. **Verify** - re-opens the bill to confirm all values match
7. **Complete** - independent verifier checks the log, then finish

---

## Demo Tasks

| Demo | Task | What it tests |
|---|---|---|
| 1 | Latest Northwind invoice → ERP | Finds correct invoice by date (not email date), handles 503 error, date reformatting, duplicate check |
| 2 | Globex invoice → ERP | Reads PDF invoice, asks human approval (bill over 10,000), vendor matching |
| 3 | Query unpaid Northwind bills | Read-only task, no writes needed |

---

## Key Design Decisions

**1. LLM decides, code enforces**
The AI picks tools and plans steps. But safety rules
(approvals, blocked patterns, verification) are in Python code
not prompts. Code cannot be talked past.

**2. Generic browser not hardcoded workflow**
The browser tool works on ANY webpage. The invoice workflow
exists only in the task description and company context file.
Add a new company = edit one text file.

**3. Errors are observations**
503 errors, validation failures, wrong dates all go back
to the AI as results. It reads them and fixes the cause.
No special error handling code needed.

**4. Two-layer verification**
Layer 1: agent must re-read the live bill before finishing.
Layer 2: separate AI call audits the raw log skeptically.

**5. Company context as data**
All company rules live in company_context.md. Change a
rule = edit a file. No code changes needed.

---

## Known Limitations
- No JavaScript/SPA support (text browser only)
- No email access (invoices must be in inbox/ folder)
- Memory resets between runs
- Single task at a time

## What I Would Build Next
- Playwright browser for JS-heavy sites
- Persistent memory across runs
- Slack/email notifications for approvals
- More demo tasks across different domains
- Automated eval suite

---

## Models and Tools Used
- **LLM:** Groq API (free) with openai/gpt-oss-20b
- **Libraries:** flask, requests, beautifulsoup4, pypdf, groq
- **No agent framework** - loop is custom ~200 lines
- Built with Claude AI assistance