#!/usr/bin/env python3
"""
MemGPT Agent - Local model with hierarchical memory
Uses Ollama for inference and nomic-embed-text for embeddings
"""

import json
import re
import time
from collections import deque
from typing import Any, Deque

import ollama

from src.infrastructure.logging_config import (
    get_logger,
    log_function_call,
    set_context,
)
from src.infrastructure.metrics import get_metrics
from src.memory.memory_storage import MemoryStorage
from src.tools.tools import AgentTools


class OllamaClient:
    """Simple Ollama client for inference and embeddings"""

    def __init__(self, model_id: str = "llama3.1:8b", embedding_model: str = "nomic-embed-text"):
        self.model_id = model_id
        self.embedding_model = embedding_model
        print(f"[OllamaClient] Using model: {model_id}, embeddings: {embedding_model}")

    def chat(self, messages: list[dict], max_tokens: int = 2048, temperature: float = 0.7, debug: bool = False):
        """Chat completion"""
        try:
            response = ollama.chat(  # type: ignore[call-overload]
                model=self.model_id,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            )
            message = response["message"]
            content = message.get("content", "")

            # Debug: show full response structure for GPT-OSS
            if debug or ('gpt-oss' in self.model_id.lower() and len(content) < 10):
                print(f"[DEBUG] Raw response ({len(content)} chars): {repr(content[:500])}")
                # Check for tool_calls in response
                if "tool_calls" in message:
                    print(f"[DEBUG] Tool calls: {message['tool_calls']}")
                # Show all keys in message
                print(f"[DEBUG] Message keys: {list(message.keys())}")

            # Handle native tool calls from Ollama (GPT-OSS may use these)
            if "tool_calls" in message and message["tool_calls"]:
                tool_calls = message["tool_calls"]
                # Convert Ollama tool calls to our format
                results = []
                for tc in tool_calls:
                    func_name = tc.get("function", {}).get("name", "")
                    args = tc.get("function", {}).get("arguments", {})
                    results.append(f'{{"function": "{func_name}", "arguments": {json.dumps(args)}}}')
                # Return as JSON for our parser to handle
                return "```json\n" + "\n".join(results) + "\n```"

            # Strip <think> tags if present (for non-Harmony models)
            if '<think>' in content.lower():
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)

            return content.strip()
        except Exception as e:
            # If response is too long or other error, return graceful message
            error_msg = str(e)
            if "parsing tool call" in error_msg or "unexpected end" in error_msg:
                return "I apologize, my response was too long. Let me give you a simpler version."
            raise

    def stop(self):
        """Stop/unload the model from Ollama."""
        try:
            import subprocess
            subprocess.run(["ollama", "stop", self.model_id], capture_output=True)
            print(f"[OllamaClient] Stopped model: {self.model_id}")
        except Exception as e:
            print(f"[OllamaClient] Failed to stop model: {e}")

    def embed(self, text: str) -> list[float]:
        """Generate 768-dim embedding"""
        response = ollama.embeddings(
            model=self.embedding_model,
            prompt=text,
        )
        return list(response["embedding"])  # type: ignore[return-value]


class MemGPTAgent:
    """
    MemGPT-style agent with hierarchical memory:
    - System Memory: Static instructions
    - Working Memory: Editable facts about agent/conversation
    - FIFO Queue: Recent conversation history
    - Archival Memory: Searchable long-term storage (PostgreSQL + pgvector)
    """

    def __init__(
        self,
        name: str,
        model_id: str = "llama3.1:8b",
        storage: MemoryStorage | None = None,
        enable_tools: bool = True,
        workspace: str | None = None,
    ):
        self.name = name
        self.storage = storage or MemoryStorage()
        self.tools = AgentTools(workspace_dir=workspace) if enable_tools else None

        # Initialize logging and metrics
        self.logger = get_logger(f"agents.{name}")
        set_context(agent_name=name)
        self.metrics = get_metrics()

        # Get or create agent in storage
        existing = self.storage.get_agent_by_name(name)
        if existing:
            # Load existing agent - use its stored model_id
            self.agent_id = existing["id"]
            stored_model = existing["model_id"]
            self.model_id = stored_model
            self.ollama = OllamaClient(model_id=stored_model)
            # Always refresh system memory to latest default (ensures new features are available)
            self.system_memory = self._default_system_memory()
            self.working_memory = existing["working_memory"] or self._default_working_memory()

            # Update system memory in database
            self.storage.update_agent_memory(
                agent_id=self.agent_id,
                system_memory=self.system_memory,
                working_memory=self.working_memory
            )

            print(f"[MemGPTAgent] Loaded existing agent: {name} (model: {stored_model}, id: {self.agent_id})")
            self.logger.info("Loaded existing agent", extra={
                'extra_data': {'model': stored_model, 'agent_id': str(self.agent_id)}
            })

            # Load recent archival memories into working memory
            self._load_archival_summary()
        else:
            # Create new agent
            self.model_id = model_id
            self.ollama = OllamaClient(model_id=model_id)
            system_mem = self._default_system_memory()
            working_mem = self._default_working_memory()
            self.agent_id = self.storage.create_agent(
                name=name,
                model_id=model_id,
                system_memory=system_mem,
                working_memory=working_mem,
            )
            self.system_memory = system_mem
            self.working_memory = working_mem
            print(f"[MemGPTAgent] Created new agent: {name} (model: {model_id}, id: {self.agent_id})")
            self.logger.info("Created new agent", extra={
                'extra_data': {'model': model_id, 'agent_id': str(self.agent_id)}
            })

        # FIFO queue for recent conversation (in-memory)
        self.fifo_queue: Deque[dict[str, Any]] = deque(maxlen=10)  # Keep last 10 messages

    def _default_system_memory(self) -> str:
        base = f"""You are {self.name}, a MemGPT agent with hierarchical memory.

CRITICAL INSTRUCTION - READ THIS FIRST:
When you need to use a function, OUTPUT THE JSON IMMEDIATELY. Do NOT describe what you're going to do, do NOT explain the function call, just OUTPUT THE JSON. The system will execute it and show results automatically.

FUNCTION CALLING:
You can call functions by outputting JSON. The JSON will be executed and replaced with the result.

Format for single function:
```json
{{"function": "function_name", "arguments": {{"arg1": "value1", "arg2": "value2"}}}}
```

Format for multiple functions (will be executed in order):
```json
[
  {{"function": "function_name1", "arguments": {{"arg": "value"}}}},
  {{"function": "function_name2", "arguments": {{"arg": "value"}}}}
]
```

EXECUTION EXAMPLES (Correct Behavior):
User: "Save that I prefer Python"
You: ```json
{{"function": "save_memory", "arguments": {{"content": "User prefers Python programming language"}}}}
```

User: "What do you remember about me?"
You: ```json
{{"function": "search_memory", "arguments": {{"query": "user preferences"}}}}
```

ANTI-PATTERNS (Incorrect - DO NOT DO THIS):
❌ "I should save this to memory using save_memory..."
❌ "Let me search my memory for that..."

✅ Just output the JSON. No preamble. No explanation.

AVAILABLE FUNCTIONS:

Memory Functions:
- save_memory: Save important information to long-term archival memory
  Arguments: {{"content": "text to save"}}

- search_memory: Search your archival memory for relevant information
  Arguments: {{"query": "search query"}}

- update_working_memory: Update your working memory with current context
  Arguments: {{"text": "text to add"}}

Your memory is organized in tiers:
1. System Memory: These instructions (read-only)
2. Working Memory: Current context and facts about yourself
3. Recent Conversation: Last 10 messages (automatic)
4. Archival Memory: Long-term searchable storage"""

        if self.tools:
            base += """

File and CLI Tools:
- read_file: Read a file from the workspace
  Arguments: {{"path": "filename.txt"}}

- write_file: Write content to a file
  Arguments: {{"path": "filename.txt", "content": "file content"}}

- edit_file: Edit a file by replacing text (PREFERRED over write_file for modifications)
  Arguments: {{"path": "filename.txt", "old_string": "text to find", "new_string": "replacement text"}}
  Optional: {{"replace_all": true}} to replace all occurrences

- append_file: Append to a file
  Arguments: {{"path": "filename.txt", "content": "text to append"}}

- list_files: List files in a directory
  Arguments: {{"path": "directory"}} or {{"path": "."}} for current directory

- delete_file: Delete a file
  Arguments: {{"path": "filename.txt"}}

- find_files: Find files by pattern (like glob)
  Arguments: {{"pattern": "*.py"}} or {{"pattern": "test_*.txt"}} or {{"pattern": "**/*.md"}}

- search_in_files: Search for text in files (like grep)
  Arguments: {{"pattern": "function.*main", "file_pattern": "*.py"}}

- run_python: Execute Python code
  Arguments: {{"code": "print('hello')"}}

- run_command: Run safe shell commands (ls, cat, grep, etc.)
  Arguments: {{"command": "ls -la"}}

- fetch_url: Fetch content from the internet (HTTP/HTTPS only)
  Arguments: {{"url": "https://example.com/api/data"}}

- get_workspace_info: Get workspace statistics
  Arguments: {{}} (no arguments)

Your workspace directory is determined when the agent starts.
All file paths are relative to this workspace.

IMPORTANT: When creating code, keep it simple and concise. Write minimal working examples without extensive documentation or comments."""

        return base

    def _default_working_memory(self) -> str:
        return f"""Agent: {self.name}
Status: Ready
Current Context: Fresh start, no prior context
"""

    def _load_archival_summary(self) -> None:
        """Load recent archival memories into working memory on startup."""
        # Get recent memories (limit to 3 most recent)
        all_memories = self.storage.get_all_memories(
            agent_id=self.agent_id,
            memory_type="archival",
        )

        if all_memories:
            # Take up to 3 most recent memories
            recent_memories = all_memories[:3]
            memory_summary = "\n".join([
                f"- {mem['content']}"
                for mem in recent_memories
            ])
            self.working_memory += f"\n\nRecent Memories:\n{memory_summary}"
            print(f"[MemGPTAgent] Loaded {len(recent_memories)} archival memories")

    def get_context_window(self) -> str:
        """Build full context for LLM"""
        parts = [
            "=== SYSTEM MEMORY ===",
            self.system_memory,
            "",
            "=== WORKING MEMORY ===",
            self.working_memory,
            "",
            "=== RECENT CONVERSATION ===",
        ]

        for msg in self.fifo_queue:
            parts.append(f"{msg['role'].upper()}: {msg['content']}")

        return "\n".join(parts)

    def save_memory(self, content: str) -> str:
        """Save to archival memory with embedding"""
        embedding = self.ollama.embed(content)
        self.storage.insert_memory(
            agent_id=self.agent_id,
            content=content,
            memory_type="archival",
            embedding=embedding,
        )
        self.logger.info("Saved to archival memory", extra={
            'extra_data': {'content_preview': content[:100]}
        })
        self.metrics.record_memory_operation(self.name, "save")
        return f"✓ Saved to archival memory: {content[:60]}..."

    def search_memory(self, query: str, limit: int = 3) -> str:
        """Search archival memory"""
        query_emb = self.ollama.embed(query)
        results = self.storage.search_memory(
            agent_id=self.agent_id,
            query_embedding=query_emb,
            memory_type="archival",
            limit=limit,
        )

        self.logger.info("Searched archival memory", extra={
            'extra_data': {'query': query, 'results_count': len(results)}
        })
        self.metrics.record_memory_operation(self.name, "search", results=len(results))

        if not results:
            return "No memories found."

        lines = [f"Found {len(results)} memories:"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['content']} (similarity: {r['similarity']:.3f})")

        return "\n".join(lines)

    def update_working_memory(self, text: str):
        """Update working memory"""
        self.working_memory += f"\n{text}"
        self.storage.update_agent_memory(
            agent_id=self.agent_id,
            working_memory=self.working_memory,
        )
        self.logger.info("Updated working memory", extra={
            'extra_data': {'text_preview': text[:100]}
        })
        self.metrics.record_memory_operation(self.name, "update")
        return "✓ Updated working memory"

    def _uses_harmony_format(self) -> bool:
        """Check if the model uses Harmony format (GPT-OSS models)."""
        harmony_models = ['gpt-oss', 'gpt-oss:20b', 'gpt-oss:120b']
        return any(m in self.model_id.lower() for m in harmony_models)

    def _parse_harmony_response(self, response: str) -> tuple[str, list[dict]]:
        """Parse Harmony format response into content and function calls.

        Harmony format uses channels:
        - <|channel|>analysis = thinking (stripped)
        - <|channel|>final = response content
        - <|channel|>commentary to=functions.{name} = function call

        Returns:
            (final_content, list of function calls)
        """
        final_content = ""
        function_calls = []

        # Extract final channel content
        final_pattern = r'<\|channel\|>final<\|message\|>(.*?)(?:<\|end\|>|<\|start\|>|$)'
        final_matches = re.findall(final_pattern, response, re.DOTALL)
        if final_matches:
            final_content = final_matches[-1].strip()  # Take last final block

        # Extract function calls from commentary channel
        # Pattern: <|channel|>commentary to=functions.{name} <|constrain|>json<|message|>{args}<|call|>
        func_pattern = r'<\|channel\|>commentary\s+to=(?:functions\.)?(\w+)\s*<\|constrain\|>json<\|message\|>(.*?)<\|call\|>'
        func_matches = re.findall(func_pattern, response, re.DOTALL)

        for func_name, args_str in func_matches:
            try:
                args = json.loads(args_str.strip()) if args_str.strip() else {}
                function_calls.append({
                    "function": func_name,
                    "arguments": args
                })
            except json.JSONDecodeError:
                print(f"[{self.name}] Harmony: Failed to parse function args: {args_str[:50]}...")

        # If no Harmony markers found, check for raw function call patterns
        if not final_content and not function_calls:
            # Model might have output without proper markers
            # Check for analysis/thinking blocks and strip them
            if '<|channel|>analysis' in response:
                # Strip analysis content
                response = re.sub(r'<\|channel\|>analysis<\|message\|>.*?(?:<\|end\|>|$)', '', response, flags=re.DOTALL)

            # Return cleaned response as content
            final_content = re.sub(r'<\|[^|]+\|>', '', response).strip()

        return final_content, function_calls

    def _execute_harmony_function_calls(self, function_calls: list[dict]) -> str:
        """Execute function calls from Harmony format and return results."""
        results = []
        for call in function_calls:
            func_name = call.get("function", "")
            args = call.get("arguments", {})
            result = self._execute_single_function(func_name, args)
            results.append(f"[{func_name}]: {result}")
        return "\n".join(results)

    def _execute_function_calls_with_followup(self, response: str, messages: list[dict], max_rounds: int = 5) -> tuple[str, bool]:
        """Execute function calls and send results back to model for processing.

        This handles the tool call loop:
        1. Model requests tool call
        2. We execute the tool
        3. We send results back to model
        4. Model generates final response (or more tool calls)
        5. Repeat until no more tool calls or max_rounds reached

        Returns:
            (final_response, had_tool_calls)
        """
        current_response = response
        had_any_tool_calls = False

        for round_num in range(max_rounds):
            # Check for JSON function calls
            json_pattern = r'```json\s*(\{[^`]+\}|\[[^`]+\])\s*```'
            matches = re.findall(json_pattern, current_response, re.DOTALL)

            if not matches:
                # Try bare JSON
                json_pattern_bare = r'(\{\s*"function"\s*:(?:[^{}]|\{[^{}]*\})*\})'
                matches = re.findall(json_pattern_bare, current_response, re.DOTALL)

            if not matches:
                # No function calls in this response
                if round_num == 0:
                    # First round, no tool calls at all
                    return self._execute_function_calls(current_response), False
                else:
                    # Later round, we've processed some tools and now have final response
                    return current_response, had_any_tool_calls

            had_any_tool_calls = True

            # Execute function calls and collect results
            all_results = []
            for json_str in matches:
                try:
                    func_data = json.loads(json_str)
                    if isinstance(func_data, dict):
                        func_data = [func_data]

                    for func_call in func_data:
                        if not isinstance(func_call, dict) or "function" not in func_call:
                            continue

                        func_name = func_call["function"]
                        args = func_call.get("arguments", {})
                        result = self._execute_single_function(func_name, args)
                        all_results.append({
                            "function": func_name,
                            "result": result
                        })
                except json.JSONDecodeError:
                    continue

            if not all_results:
                return current_response, had_any_tool_calls

            # Build tool response message
            tool_results_text = "\n\n".join([
                f"Result of {r['function']}:\n{r['result'][:8000]}"  # Limit size
                for r in all_results
            ])

            # Add assistant's tool call and tool response to messages
            messages.append({"role": "assistant", "content": current_response})
            messages.append({
                "role": "user",
                "content": f"Here are the results from the tools you called:\n\n{tool_results_text}\n\nPlease process these results. If you need to save information to memory, call save_memory. Otherwise, provide a summary."
            })

            # Call model again to process results
            print(f"[{self.name}] Tool call round {round_num + 1}: sending results back to model...")
            current_response = self.ollama.chat(messages, max_tokens=1024, debug=True)

            # Empty response means the model only produced tool_calls (handled by Ollama wrapper)
            if current_response.strip() == "":
                print(f"[{self.name}] Model returned empty response (likely tool_calls), continuing...")
                continue

        # Reached max rounds
        print(f"[{self.name}] Warning: Reached max tool call rounds ({max_rounds})")
        return current_response, had_any_tool_calls

    def _execute_function_calls(self, response: str) -> str:
        """Execute function calls found in the response (JSON format)"""

        # Check if using Harmony format
        if self._uses_harmony_format() and ('<|' in response or not response.strip()):
            final_content, function_calls = self._parse_harmony_response(response)

            if function_calls:
                results = self._execute_harmony_function_calls(function_calls)
                # Combine final content with function results
                if final_content:
                    return f"{final_content}\n\n{results}"
                return results

            # Return final content or original if parsing found nothing
            return final_content if final_content else response

        # Look for JSON code blocks (with or without "json" label)
        # Use greedy matching to capture full JSON including nested braces
        json_pattern = r'```(?:json)?\s*(\{[^`]+\}|\[[^`]+\])\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)

        if not matches:
            # Try without code block markers - be more generous with matching
            # Match from {"function": to the closing brace, handling nested structures
            json_pattern_bare = r'(\{\s*"function"\s*:(?:[^{}]|\{[^{}]*\})*\})'
            matches = re.findall(json_pattern_bare, response, re.DOTALL)

        if not matches:
            return response  # No JSON found

        # Process each JSON block found
        for json_str in matches:
            try:
                # Parse JSON
                func_data = json.loads(json_str)

                # Handle both single function and array of functions
                if isinstance(func_data, dict):
                    func_data = [func_data]  # Convert to list for uniform processing
                elif not isinstance(func_data, list):
                    print(f"[{self.name}] Warning: Invalid JSON structure (not dict or list)")
                    continue

                # Execute functions and collect results
                call_results: list[str] = []
                for func_call in func_data:
                    if not isinstance(func_call, dict) or "function" not in func_call:
                        print(f"[{self.name}] Warning: Invalid function call structure")
                        continue

                    func_name = func_call["function"]
                    args = func_call.get("arguments", {})

                    # Execute the function
                    result = self._execute_single_function(func_name, args)
                    call_results.append(result)

                # Replace JSON block with results
                results_text = "\n".join(call_results)
                # Find the full JSON block including ``` markers if present (with or without "json")
                full_block_pattern = r'```(?:json)?\s*' + re.escape(json_str) + r'\s*```'
                if re.search(full_block_pattern, response, re.DOTALL):
                    response = re.sub(full_block_pattern, results_text, response, count=1, flags=re.DOTALL)
                else:
                    # Replace bare JSON
                    response = response.replace(json_str, results_text, 1)

            except json.JSONDecodeError as e:
                print(f"[{self.name}] JSON parse error: {e}")
                print(f"[{self.name}] JSON string was: {json_str[:100]}...")
                continue
            except Exception as e:
                print(f"[{self.name}] Error executing functions: {e}")
                import traceback
                traceback.print_exc()
                continue

        return response

    def _execute_single_function(self, func_name: str, args: dict) -> str:
        """Execute a single function call and return result"""
        start_time = time.time()
        success = False
        result = ""

        # Handle nested arguments from GPT-OSS (it sometimes wraps args in another 'arguments' key)
        if "arguments" in args and isinstance(args["arguments"], dict):
            args = args["arguments"]

        try:
            # Memory functions
            if func_name == "save_memory":
                content = args.get("content", "")
                result = self.save_memory(content)
                success = True

            elif func_name == "search_memory":
                query = args.get("query", "")
                result = self.search_memory(query)
                success = True

            elif func_name == "update_working_memory":
                text = args.get("text", "")
                result = self.update_working_memory(text)
                success = True

            # File and CLI tools
            elif self.tools:
                if func_name == "read_file":
                    path = args.get("path", "")
                    result = self.tools.read_file(path)
                    success = True

                elif func_name == "write_file":
                    path = args.get("path", "")
                    content = args.get("content", "")
                    result = self.tools.write_file(path, content)
                    success = True

                elif func_name == "append_file":
                    path = args.get("path", "")
                    content = args.get("content", "")
                    result = self.tools.append_file(path, content)
                    success = True

                elif func_name == "list_files":
                    path = args.get("path", ".")
                    result = self.tools.list_files(path)
                    success = True

                elif func_name == "delete_file":
                    path = args.get("path", "")
                    result = self.tools.delete_file(path)
                    success = True

                elif func_name == "run_python":
                    code = args.get("code", "")
                    result = self.tools.run_python(code)
                    success = True

                elif func_name == "run_command":
                    command = args.get("command", "")
                    result = self.tools.run_command(command)
                    success = True

                elif func_name == "get_workspace_info":
                    result = self.tools.get_workspace_info()
                    success = True

                elif func_name == "edit_file":
                    path = args.get("path", "")
                    old_string = args.get("old_string", "")
                    new_string = args.get("new_string", "")
                    replace_all = args.get("replace_all", False)
                    result = self.tools.edit_file(path, old_string, new_string, replace_all)
                    success = True

                elif func_name == "search_in_files":
                    pattern = args.get("pattern", "")
                    file_pattern = args.get("file_pattern", "*.py")
                    max_results = args.get("max_results", 20)
                    result = self.tools.search_in_files(pattern, file_pattern, max_results)
                    success = True

                elif func_name == "find_files":
                    pattern = args.get("pattern", "")
                    result = self.tools.find_files(pattern)
                    success = True

                elif func_name == "fetch_url":
                    url = args.get("url", "")
                    timeout = args.get("timeout", 30)
                    result = self.tools.fetch_url(url, timeout)
                    success = True
                else:
                    result = f"✗ Unknown function: {func_name}"
            else:
                # Unknown function
                result = f"✗ Unknown function: {func_name}"

        except Exception as e:
            result = f"✗ Error executing {func_name}: {e}"
            success = False
            self.logger.error("Function execution failed", extra={
                'extra_data': {'function': func_name, 'args': args, 'error': str(e)}
            }, exc_info=True)

        # Log the function call and record metrics
        duration = time.time() - start_time
        log_function_call(
            agent_name=self.name,
            function_name=func_name,
            arguments=args,
            result=result[:200] if success else None,
            error=result if not success else None
        )
        self.metrics.record_function_call(
            agent=self.name,
            function=func_name,
            success=success,
            duration=duration
        )

        return result

    def _detect_function_intent(self, user_message: str) -> tuple[bool, str]:
        """Detect if user message likely requires a function call and return a hint.

        Returns:
            (requires_function, hint_text)
        """
        message_lower = user_message.lower()

        # Memory operations
        if any(word in message_lower for word in ['save', 'remember', 'store']):
            return True, "HINT: Use save_memory to store this information."

        if any(word in message_lower for word in ['search', 'recall', 'find in memory', 'what do you remember']):
            return True, "HINT: Use search_memory to find relevant information."

        # File operations (if tools enabled)
        if self.tools:
            # Edit/modify operations
            if any(word in message_lower for word in ['edit', 'modify', 'change', 'replace', 'fix']):
                if 'file' in message_lower or any(ext in message_lower for ext in ['.py', '.txt', '.md']):
                    return True, "HINT: Use edit_file to modify the file by replacing text."

            # Search operations
            if any(word in message_lower for word in ['search for', 'find', 'grep', 'look for']):
                if 'file' in message_lower or 'code' in message_lower:
                    return True, "HINT: Use search_in_files to search for patterns in files."

            # File finding
            if any(word in message_lower for word in ['find files', 'list all', 'show files matching']):
                return True, "HINT: Use find_files with a pattern like '*.py'."

            # Web/URL operations
            if any(word in message_lower for word in ['fetch', 'download', 'get from url', 'http']):
                return True, "HINT: Use fetch_url to get content from the internet."

            # Basic file operations
            if any(word in message_lower for word in ['create file', 'write file', 'save to file']):
                return True, "HINT: Use write_file function to create the file."

            if any(word in message_lower for word in ['read file', 'show file', 'what\'s in']):
                return True, "HINT: Use read_file function to read the file."

            # Code execution
            if any(word in message_lower for word in ['run', 'execute', 'python']):
                if 'python' in message_lower or 'code' in message_lower:
                    return True, "HINT: Use run_python to execute the code."

        return False, ""

    def chat(self, user_message: str) -> str:
        """Process user message and generate response"""

        # Log incoming user message
        self.logger.info("Processing user message", extra={
            'extra_data': {'message_preview': user_message[:100]}
        })

        # Add user message to FIFO
        self.fifo_queue.append({"role": "user", "content": user_message})

        # Build context
        context = self.get_context_window()

        # Detect if this requires a function call and add hint if needed
        requires_function, hint = self._detect_function_intent(user_message)

        # Generate response
        llm_start = time.time()
        if requires_function:
            # Add strategic hint to increase function calling reliability
            enhanced_message = f"{user_message}\n\n{hint}"
            messages = [
                {"role": "system", "content": context},
                {"role": "user", "content": enhanced_message},
            ]
        else:
            messages = [
                {"role": "system", "content": context},
                {"role": "user", "content": user_message},
            ]

        response = self.ollama.chat(messages, max_tokens=512)
        llm_duration = time.time() - llm_start

        # Log LLM interaction
        self.logger.info("LLM response generated", extra={
            'extra_data': {
                'model': self.model_id,
                'latency_seconds': llm_duration,
                'response_preview': response[:100] if response else "(tool call)"
            }
        })
        # Record LLM metrics (Ollama doesn't provide token counts, so we estimate)
        self.metrics.record_llm_request(
            agent=self.name,
            model=self.model_id,
            latency=llm_duration,
            input_tokens=len(context.split()) // 4,  # Rough estimate
            output_tokens=len(response.split()) // 4 if response else 0
        )

        # Execute any function calls and handle tool response loop
        response, _ = self._execute_function_calls_with_followup(response, messages)

        # Add response to FIFO
        self.fifo_queue.append({"role": "assistant", "content": response})

        # Save to conversation history
        self.storage.insert_conversation(
            agent_id=self.agent_id,
            role="user",
            content=user_message,
        )
        self.storage.insert_conversation(
            agent_id=self.agent_id,
            role="assistant",
            content=response,
        )

        return response

    def get_stats(self) -> dict:
        """Get agent memory statistics"""
        all_memories = self.storage.get_all_memories(
            agent_id=self.agent_id,
            memory_type="archival",
        )
        conversation = self.storage.get_conversation_history(
            agent_id=self.agent_id,
            limit=100,
        )

        return {
            "name": self.name,
            "agent_id": str(self.agent_id),
            "archival_memories": len(all_memories),
            "conversation_messages": len(conversation),
            "fifo_size": len(self.fifo_queue),
            "working_memory_chars": len(self.working_memory),
        }


def demo():
    """Demo of MemGPT agent"""
    print("=" * 70)
    print("MemGPT Agent Demo - Local Ollama + PostgreSQL Memory")
    print("=" * 70)

    storage = MemoryStorage()
    agent = MemGPTAgent(name="demo-agent", model_id="llama3.1:8b", storage=storage)

    print(f"\nAgent: {agent.name}")
    print("Model: llama3.1:8b")
    print(f"Agent ID: {agent.agent_id}")

    # Conversation
    print("\n" + "=" * 70)
    print("Conversation Start")
    print("=" * 70)

    messages = [
        "Hi! My name is Todd and I'm building an AI memory system.",
        "What's your name and what can you remember?",
        "Can you save that I prefer to work on systems programming in Python and C++?",
        "What do you remember about me?",
    ]

    for msg in messages:
        print(f"\n👤 USER: {msg}")
        response = agent.chat(msg)
        print(f"🤖 {agent.name.upper()}: {response}")

    # Show stats
    print("\n" + "=" * 70)
    print("Agent Statistics")
    print("=" * 70)
    stats = agent.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    storage.close()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    demo()
