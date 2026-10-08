"""
Its like a security guard for the agent.
Every tool is either:
- READ (safe) - runs without asking anyone
- WRITE (changes something) - needs human approval first

Some actions are ALWAYS blocked regardless of what the AI says.
The AI cannot talk its way past this - it's enforced in code.

It is like a middleware
"""

# These URL patterns are always blocked, even if AI thinks it needs to do them

BLOCKED_PATTERNS = [
    "/delete",
    "/admin",
    "/__reset",
    "/payments/release"
]

class Decision:
    def __init__(self,kind,description="",reason=""):
        """
        kind = "allow"   → run the tool immediately
        kind = "approve" → ask human first
        kind = "deny"    → block it completely
        """
        self.kind = kind
        self.description = description
        self.reason = reason

class Policy:

    def review(self,tool,args,ctx):
        """
        Checks whether a tool call should be:
        - allowed immediately
        - sent for human approval
        - blocked completely
        """

        if not tool.mutating:
            return Decision("allow")

        if tool.name== "browser_submit":
            description = ctx.browser.describe_submission(args.get("form_index",-1),
                                                          args.get("fields",{}))
        else:
            description = f"{tool.name} with {args}"
        # check block pattern
        for pattern in BLOCKED_PATTERNS:
            if pattern in description:
                return Decision("deny",description,f"matches blocked pattern {pattern}")         


        return Decision("approve",description)