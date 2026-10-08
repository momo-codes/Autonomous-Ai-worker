class ToolError(Exception):
    """
    When a tool fails in a way the agent should know about.
    
    Instead of crashing the whole program, we catch this
    and send the error message back to the AI so it can
    fix the problem and try again.
    
    Example: wrong file path, blocked website, bad form field
    """
    pass