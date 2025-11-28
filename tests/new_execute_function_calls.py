    def _execute_function_calls(self, response: str) -> str:
        """Execute function calls found in the response (JSON format)"""

        # Look for JSON code blocks
        json_pattern = r'```json\s*(\{.*?\}|\[.*?\])\s*```'
        matches = re.findall(json_pattern, response, re.DOTALL)

        if not matches:
            # Try without code block markers
            json_pattern_bare = r'(\{[\s\n]*"function"[\s\n]*:.*?\}|\[[\s\n]*\{[\s\n]*"function"[\s\n]*:.*?\])'
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
                results = []
                for func_call in func_data:
                    if not isinstance(func_call, dict) or "function" not in func_call:
                        print(f"[{self.name}] Warning: Invalid function call structure")
                        continue

                    func_name = func_call["function"]
                    args = func_call.get("arguments", {})

                    # Execute the function
                    result = self._execute_single_function(func_name, args)
                    results.append(result)

                # Replace JSON block with results
                results_text = "\n".join(results)
                # Find the full JSON block including ```json markers if present
                full_block_pattern = r'```json\s*' + re.escape(json_str) + r'\s*```'
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

        # Memory functions
        if func_name == "save_memory":
            content = args.get("content", "")
            return self.save_memory(content)

        elif func_name == "search_memory":
            query = args.get("query", "")
            return self.search_memory(query)

        elif func_name == "update_working_memory":
            text = args.get("text", "")
            return self.update_working_memory(text)

        # Agent-to-agent communication
        elif func_name == "message_agent":
            agent_name = args.get("agent_name", "")
            message = args.get("message", "")
            if not agent_name or not message:
                return f"✗ message_agent requires 'agent_name' and 'message' arguments"
            print(f"[{self.name}] → {agent_name}: {message[:60]}...")
            return self.message_agent(agent_name, message)

        # File and CLI tools
        elif self.tools:
            if func_name == "read_file":
                path = args.get("path", "")
                return self.tools.read_file(path)

            elif func_name == "write_file":
                path = args.get("path", "")
                content = args.get("content", "")
                return self.tools.write_file(path, content)

            elif func_name == "append_file":
                path = args.get("path", "")
                content = args.get("content", "")
                return self.tools.append_file(path, content)

            elif func_name == "list_files":
                path = args.get("path", ".")
                return self.tools.list_files(path)

            elif func_name == "delete_file":
                path = args.get("path", "")
                return self.tools.delete_file(path)

            elif func_name == "run_python":
                code = args.get("code", "")
                return self.tools.run_python(code)

            elif func_name == "run_command":
                command = args.get("command", "")
                return self.tools.run_command(command)

            elif func_name == "get_workspace_info":
                return self.tools.get_workspace_info()

        # Unknown function
        return f"✗ Unknown function: {func_name}"
