class CLIHuman:
    """
    The real human interaction - uses terminal input/output.
    Used when running the agent normally.
    """
    def ask(self,question):
        """Agent asks human a question, wait for answer"""
        print(f"\n[AGENT NEEDS YOUR INPUT]")
        print(f"Question: {question}")
        return input("Your answer: ").strip()
    
    def approve(self,description):
        """
        agent want to do any changes to the system so it needs approval from human
        It returns true/false and reason

        """
        print(f"\n[APPROVAL REQUIRED]")
        print(f"The agent wants to: {description}")
        answer = input("Approve [y/N]: ").strip().lower()

        if answer in ("y","yes"):
            return True, ""
        else:
            reason = answer if answer not in ("no","n","") else "denied"
            return False, reason


class ScriptedHuman:
    """
    it is like a fake human for automated tests
    Instead of waiting for keyboard input, it uses 
    pre-written answers and auto-approves actions.
    """        

    def __init__(self,answers=None,approve=True):
        # prewritten answers to questions
        self.answers = list(answers or [])
        # weteher to auto-approve all actions
        self.auto_approve = approve
        # Track the number of questions asked
        self.asked = []
        self.approvals = []
    
    def ask(self,question):
        """Agent asks human a question, wait for answer"""
        self.asked.append(question)
        if self.answers:
            return self.answers.pop(0)
        return "Yes, please proceed."

    def approve(self,description):
        self.approvals.append(description)
        if self.auto_approve:
            return True, ""
        return False, "denied by test"    
