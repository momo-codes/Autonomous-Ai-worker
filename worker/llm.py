import os
import time
import json

class LLMResponse:
    """
    Holds the si's response.
    
    content = list of blocks. Each block is either:
    
    1. A text block (Ai thinking out loud):
    {
        "type": "text",
        "text": "I should check the inbox files first..."
    }
    
    2. A tool call block (Ai wants to use a tool):
    {
        "type": "tool_use",
        "id": "call_abc123",
        "name": "read_file",
        "input": {"path": "inbox/2026-09-22_northwind_INV-2057.txt"}
    }
    
    stop_reason tells us WHY Ai stopped:
    - "tool_use"   = Ai wants to call a tool
    - "end_turn"   = Ai is done talking
    """
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class GeminiLLM:
    """
    Wrapper around Google Gemini API.
    
    Gemini is free and supports tool use (function calling)
    which is exactly what our agent needs.
    
    How tool use works with Gemini:
    
    1. We send the task + list of available tools
    2. Gemini responds with which tool to call and what args
    3. We run the tool
    4. We send the result back to Gemini
    5. Gemini decides next tool or says it's done
    6. Repeat until task complete
    
    Example conversation:
    
    US:     "Find latest Northwind invoice"
            tools available: [list_files, read_file, ...]
    
    GEMINI: tool_call: list_files(path="inbox")
    
    US:     tool result: ["INV-2031.txt", "INV-2057.txt", ...]
    
    GEMINI: tool_call: read_file(path="inbox/INV-2057.txt")
    
    US:     tool result: "Invoice Date: 21 Sep 2026, TOTAL: 4820.50"
    
    GEMINI: tool_call: remember(key="amount", value="4820.50")
    
    ... and so on
    """

    def __init__(self,model=None,max_tokens=2048):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise SystemExit(
                "GEMINI_API_KEY not set!\n"
                "Get free key at: https://aistudio.google.com\n"
                "Then run: set GEMINI_API_KEY=your-key-here"
            )

        import google.generativeai as genai
        genai.configure(api_key=api_key)

        self.genai = genai
        # we will use gemini-1.5-flash as it is free and fast
        self.model_name = model or os.getenv("WORKER_MODEL", "gemini-1.5-flash")
        self.max_tokens = max_tokens


    def complete(self,system,messages,tools=None):
        """
        Sends messages to Gemini and returns response.
        
        Converts our internal message format to Gemini format
        and converts Gemini response back to our format.
        
        Our format:                    Gemini format:
        ─────────────────────         ──────────────────────
        role: "user"          →       role: "user"
        role: "assistant"     →       role: "model"
        tool_result block     →       function_response part
        tool_use block        →       function_call part
        """ 

        # converts tools to gemini function declaration
        gemini_tools = None
        if tools:
            gemini_tools = self._build_tools(tools)

        # converts messages to gemini format

        gemini_history, last_message = self._convert_messages(messages)

        #create the model with system instruction
        model = self.genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system,
            tools=gemini_tools
        )    

        # retry up to 5 times if api is busy

        for attempt in range(5):
            try:
                # start chat with history
                chat = model.start_chat(history=gemini_history)
                # send the last message
                
                response = chat.send_message(last_message)
                break
            except Exception as e:
                error_str = str(e).lower()
                # Retry on rate limit or server errors
                if "429" in error_str or "503" in error_str or "500" in error_str:
                    if attempt ==4:
                        raise
                    wait = 2**attempt
                    print(f"API busy, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        return self._convert_response(response)

    def _build_tools(self,tools):
        """
        Builds Gemini Tool object from our specs.
        
        tools = list of dicts already in Gemini format:
        [
            {
                "name": "read_file",
                "description": "...",
                "parameters": {"type": "OBJECT", ...}
            },
            ...
        ]
        
        We just wrap them in FunctionDeclaration objects.
        No type conversion needed - spec() already did that!
        """
        from google.generativeai.types import (
            FunctionDeclaration,
            Tool
        )

        declarations=[]
        for tool_spec in tools:
            declarations.append(
                FunctionDeclaration(
                    name=tool_spec["name"],
                    description=tool_spec["description"],
                    parameters = tool_spec["parameters"]
                )
            )

        return [Tool(function_declarations=declarations)] 

    
       

    def _convert_messages(self, messages):
        """
        Converts our messages to Gemini format.
        Returns (history, last_message) separately
        because Gemini's chat API works that way.
        
        history     = all messages except the last one
        last_message = the most recent message to send now
        
        Our message formats and their Gemini equivalents:
        
        1. Simple user text:
           Ours:   {"role": "user", "content": "Find invoice"}
           Gemini: {"role": "user", "parts": ["Find invoice"]}
        
        2. Assistant with text + tool calls:
           Ours:   {"role": "assistant", "content": [
                       {"type": "text", "text": "I'll check..."},
                       {"type": "tool_use", "id": "t1",
                        "name": "list_files", "input": {}}
                   ]}
           Gemini: {"role": "model", "parts": [
                       "I'll check...",
                       FunctionCall(name="list_files", args={})
                   ]}
        
        3. Tool results:
           Ours:   {"role": "user", "content": [
                       {"type": "tool_result",
                        "tool_use_id": "t1",
                        "content": '{"ok": true, "entries": [...]}'}
                   ]}
           Gemini: {"role": "user", "parts": [
                       FunctionResponse(
                           name="list_files",
                           response={"result": '{"ok": true, ...}'}
                       )
                   ]}
        """
        gemini_messages = []

        # We need to track tool call ids to names
        # so we can match results back to the right function
        id_to_name = {}

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            gemini_role = "model" if role == "assistant" else "user"

            # Simple string message
            if isinstance(content, str):
                gemini_messages.append({
                    "role": gemini_role,
                    "parts": [content]
                })
                continue

            # List of blocks
            if isinstance(content, list):
                parts = []
                result_parts = []

                for block in content:
                    btype = block.get("type")

                    # Text block
                    if btype == "text" and block.get("text"):
                        parts.append(block["text"])

                    # Tool call block
                    elif btype == "tool_use":
                        # Remember id → name mapping
                        id_to_name[block["id"]] = block["name"]
                        parts.append(
                            self.genai.protos.Part(
                                function_call=self.genai.protos.FunctionCall(
                                    name=block["name"],
                                    args=block.get("input", {})
                                )
                            )
                        )

                    # Tool result block
                    elif btype == "tool_result":
                        tool_id = block.get("tool_use_id", "")
                        # Look up which function this result is for
                        tool_name = id_to_name.get(tool_id, "unknown")
                        result_content = block.get("content", "{}")

                        try:
                            result_data = json.loads(result_content)
                        except Exception:
                            result_data = {"result": result_content}

                        result_parts.append(
                            self.genai.protos.Part(
                                function_response=self.genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": json.dumps(result_data)}
                                )
                            )
                        )

                if parts:
                    gemini_messages.append({
                        "role": gemini_role,
                        "parts": parts
                    })

                if result_parts:
                    gemini_messages.append({
                        "role": "user",
                        "parts": result_parts
                    })

        # Split into history and last message
        # Gemini needs them separate
        if not gemini_messages:
            return [], "Start the task."

        last = gemini_messages[-1]
        history = gemini_messages[:-1]

        # Last message parts
        last_parts = last["parts"]

        return history, last_parts

    def _convert_response(self, response):
        """
        Converts Gemini response to our format.
        
        Gemini gives us:
        response.candidates[0].content.parts = [
            Part(text="I'll check the inbox first"),
            Part(function_call=FunctionCall(
                name="list_files",
                args={"path": "inbox"}
            ))
        ]
        
        We convert to:
        [
            {"type": "text", "text": "I'll check the inbox first"},
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "list_files",
                "input": {"path": "inbox"}
            }
        ]
        """
        blocks = []
        stop_reason = "end_turn"
        call_counter = 0

        try:
            parts = response.candidates[0].content.parts
        except (IndexError, AttributeError):
            return LLMResponse(
                [{"type": "text", "text": "No response generated."}],
                "end_turn"
            )

        for part in parts:
            # Text part
            if hasattr(part, "text") and part.text:
                blocks.append({
                    "type": "text",
                    "text": part.text
                })

            # Function call part
            elif hasattr(part, "function_call") and part.function_call.name:
                call_counter += 1
                stop_reason = "tool_use"

                # Convert Gemini MapComposite args to regular dict
                args = {}
                for key, value in part.function_call.args.items():
                    args[key] = value

                blocks.append({
                    "type": "tool_use",
                    "id": f"call_{call_counter}",
                    "name": part.function_call.name,
                    "input": args
                })

        if not blocks:
            blocks = [{"type": "text", "text": "No content in response."}]

        return LLMResponse(blocks, stop_reason)