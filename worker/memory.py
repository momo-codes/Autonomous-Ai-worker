import json
from pathlib import Path

class Memory:
    """
    The agent's working notepad.

    Why we need this:
    - AI conversations have a limited size (context window)
    - Old messages get compressed/forgotten in long tasks
    - Important facts (like extracted invoice amount) must survive

    Solution: agent calls remember("amount", "4820.50")
    We save it to a file AND inject it into every prompt
    So the AI always has its key facts even if old messages are gone

    Like localStorage in JavaScript but for the AI's brain.
    """
    def __init__(self,path=None):
        self.facts ={}
        self.path = path

    def remember(self,key,value):
        """Saving facts"""
        self.facts[key]= value
        if self.path:
            Path(self.path).parent.mkdir(parents=True,exist_ok=True) 
            Path(self.path).write_text(json.dumps(self.facts, indent=2))   

    def render(self):
        """
        returns all the facts in memory as a string
        this gets injected into every prompt so the agent can use it to make decisions
        """
        if not self.facts:
            return "no facts in memory"
        lines=[]
        for key,value in self.facts.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)    