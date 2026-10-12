import os
import time
import json


class LLMResponse:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class GeminiLLM:
    """
    Despite the class name we now use Groq.
    Groq is free, fast and supports tool use
    without any thought_signature issues.
    
    We keep the class name GeminiLLM so we don't
    need to change any other file that imports it.
    """

    def __init__(self, model=None, max_tokens=512):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise SystemExit(
                "GROQ_API_KEY not set!\n"
                "Get free key at: https://console.groq.com\n"
                "Then run: $env:GROQ_API_KEY='your-key-here'"
            )
        from groq import Groq
        self.client = Groq(api_key=api_key)
        # llama-3.3-70b is free, smart and supports tool use
        self.model_name = model or os.getenv(
            "WORKER_MODEL", "openai/gpt-oss-20b"
        )
        self.max_tokens = max_tokens

    def complete(self, system, messages, tools=None):
        """
        Sends messages to Groq and returns response.
        
        Groq uses OpenAI-compatible format which is
        simpler than Gemini - no thought signatures,
        no content type conversions needed.
        
        What we send:
        messages = [
            {"role": "system", "content": "You are..."},
            {"role": "user", "content": "Find invoice"},
            {"role": "assistant", "content": null,
             "tool_calls": [{"id": "c1", "function": {"name": "list_files", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'}
        ]
        
        What we get back:
        choice.message.content = text (if thinking)
        choice.message.tool_calls = list of tool calls
        """
        # Convert our messages to Groq format
        groq_messages = self._convert_messages(system, messages)

        # Convert our tool specs to Groq format
        groq_tools = self._convert_tools(tools) if tools else None

        # Retry up to 5 times
        for attempt in range(5):
            try:
                kwargs = {
                    "model": self.model_name,
                    "messages": groq_messages,
                    "max_tokens": self.max_tokens,
                    "temperature": 0.2,
                    "parallel_tool_calls":False
                }
                if groq_tools:
                    kwargs["tools"] = groq_tools
                    kwargs["tool_choice"] = "auto"

                response = self.client.chat.completions.create(**kwargs)
                return self._convert_response(response)

            except Exception as e:
                error_str = str(e).lower()
                if any(c in error_str for c in ["429", "503", "500", "rate"]):
                    if attempt == 4:
                        raise
                    wait = 2 ** attempt
                    print(f"API busy, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def _convert_messages(self, system, messages):
        """
        Converts our messages to Groq/OpenAI format.
        
        Groq format is simpler than Gemini:
        
        1. System message goes first as its own message:
        {"role": "system", "content": "You are an AI worker..."}
        
        2. User text:
        {"role": "user", "content": "Find latest invoice"}
        
        3. Assistant with tool calls:
        {
            "role": "assistant",
            "content": null,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "list_files",
                        "arguments": "{}"
                    }
                }
            ]
        }
        
        4. Tool result:
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": '{"ok": true, "entries": [...]}'
        }
        """
        groq_messages = [{"role": "system", "content": system}]

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Simple string message
            if isinstance(content, str):
                groq_messages.append({
                    "role": role,
                    "content": content
                })
                continue

            # List of blocks
            if isinstance(content, list):
                text_parts = []
                tool_calls = []
                tool_results = []

                for block in content:
                    btype = block.get("type")

                    if btype == "text" and block.get("text", "").strip():
                        text_parts.append(block["text"])

                    elif btype == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(
                                    block.get("input", {})
                                )
                            }
                        })

                    elif btype == "tool_result":
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content", "{}")
                        })

                # Assistant message with tool calls
                if role == "assistant":
                    assistant_msg = {
                        "role": "assistant",
                        "content": "\n".join(text_parts) or None
                    }
                    if tool_calls:
                        assistant_msg["tool_calls"] = tool_calls
                    groq_messages.append(assistant_msg)

                # Tool results (each gets its own message)
                for tr in tool_results:
                    groq_messages.append(tr)

                # User message
                if role == "user" and text_parts and not tool_results:
                    groq_messages.append({
                        "role": "user",
                        "content": "\n".join(text_parts)
                    })

        return groq_messages

    def _convert_tools(self, tools):
        """
        Converts our tool specs to Groq/OpenAI format.
        
        Our format (from Tool.spec()):
        {
            "name": "read_file",
            "description": "Read a file...",
            "parameters": {
                "type": "OBJECT",          ← uppercase from our spec
                "properties": {
                    "path": {"type": "STRING"}
                },
                "required": ["path"]
            }
        }
        
        Groq needs lowercase types:
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file...",
                "parameters": {
                    "type": "object",       ← lowercase
                    "properties": {
                        "path": {"type": "string"}  ← lowercase
                    },
                    "required": ["path"]
                }
            }
        }
        """
        groq_tools = []
        for tool_spec in tools:
                params = self._lowercase_types(
                    tool_spec.get("parameters", {})
                )
                # Remove 'enum' from type fields - Groq doesn't like it
                params = self._clean_schema(params)
                groq_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_spec["name"],
                        "description": tool_spec["description"],
                        "parameters": params
                    }
                })
        return groq_tools

    def _clean_schema(self, schema):
        """
        Cleans schema for Groq compatibility.
        Groq sometimes fails on complex nested schemas.
        We simplify by removing problematic fields.
        """
        if not isinstance(schema, dict):
            return schema
        result = {}
        for key, value in schema.items():
            # Skip 'enum' inside type definitions at top level
            if key == "enum" and isinstance(value, list):
                continue
            elif isinstance(value, dict):
                result[key] = self._clean_schema(value)
            elif isinstance(value, list):
                result[key] = [
                    self._clean_schema(i) if isinstance(i, dict) else i
                    for i in value
                ]
            else:
                result[key] = value
        return result

    def _lowercase_types(self, schema):
        """
        Recursively converts uppercase types to lowercase.
        Our Tool.spec() outputs uppercase for Gemini.
        Groq needs lowercase.
        
        "OBJECT" → "object"
        "STRING" → "string"
        "INTEGER" → "integer"
        "ARRAY" → "array"
        """
        if not isinstance(schema, dict):
            return schema
        result = {}
        for key, value in schema.items():
            if key == "type" and isinstance(value, str):
                result[key] = value.lower()
            elif isinstance(value, dict):
                result[key] = self._lowercase_types(value)
            elif isinstance(value, list):
                result[key] = [
                    self._lowercase_types(i) if isinstance(i, dict) else i
                    for i in value
                ]
            else:
                result[key] = value
        return result

    def _convert_response(self, response):
        """
        Converts Groq response to our format.
        
        Groq response:
        response.choices[0].message.content = "I'll check inbox..."
        response.choices[0].message.tool_calls = [
            ToolCall(
                id="call_1",
                type="function",
                function=Function(
                    name="list_files",
                    arguments="{}"
                )
            )
        ]
        
        Our format:
        [
            {"type": "text", "text": "I'll check inbox..."},
            {"type": "tool_use", "id": "call_1",
             "name": "list_files", "input": {}}
        ]
        """
        blocks = []
        stop_reason = "end_turn"

        try:
            message = response.choices[0].message
        except (IndexError, AttributeError):
            return LLMResponse(
                [{"type": "text", "text": "No response generated."}],
                "end_turn"
            )

        # Text content
        if message.content and message.content.strip():
            blocks.append({
                "type": "text",
                "text": message.content
            })

        # Tool calls
        if message.tool_calls:
            stop_reason = "tool_use"
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": args
                })

        if not blocks:
            blocks = [{"type": "text", "text": "Empty response."}]

        return LLMResponse(blocks, stop_reason)