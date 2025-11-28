# Agent CLI Tools

The Memory Engine agents have access to CLI tools for file manipulation, code execution, and system interaction.

## Workspace

All tools operate in a **sandboxed workspace**: `/home/todd/olympus/agent-workspace`

- Agents cannot access files outside this directory
- All paths are relative to the workspace
- Workspace is automatically created on first use

## Available Tools

### File Operations

**read_file(path)**
- Read contents of a file
- Example: `read_file("notes.txt")`

**write_file(path, content)**
- Write content to a file (creates or overwrites)
- Example: `write_file("hello.txt", "Hello World!")`

**append_file(path, content)**
- Append content to an existing file
- Example: `append_file("log.txt", "New log entry")`

**list_files(path)**
- List files and directories
- Example: `list_files(".")` or `list_files("subdir")`

**delete_file(path)**
- Delete a file
- Example: `delete_file("temp.txt")`

### Code Execution

**run_python(code)**
- Execute Python code in the workspace
- Code runs in isolated process
- Example: `run_python("print('Hello'); result = 2 + 2; print(result)")`

**run_command(command)**
- Run safe shell commands
- Allowed: `ls`, `cat`, `grep`, `find`, `wc`, `head`, `tail`, `tree`, `python3`, `pytest`
- Example: `run_command("ls -la")`

### Information

**get_workspace_info()**
- Get workspace statistics (files, size, etc.)
- Example: `get_workspace_info()`

## How Agents Use Tools

Agents can invoke tools by including the function call in their response:

```
Agent: Let me create a test file for you.
write_file("test.py", "print('Hello from agent!')")

Agent: Now let me run it:
run_python(open("test.py").read())
```

The system automatically:
1. Detects function calls in the response
2. Executes the tool
3. Replaces the call with the result
4. Shows the result to the user

## Example Session

```
👤 USER: Create a Python script that calculates fibonacci numbers

🤖 AGENT: I'll create a fibonacci calculator.
write_file("fibonacci.py", "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)\n\nfor i in range(10):\n    print(f'fib({i}) = {fib(i)}')")

✓ Wrote 156 chars to fibonacci.py

👤 USER: Run it

🤖 AGENT: Let me execute the script:
run_python(open("fibonacci.py").read())

Output:
fib(0) = 0
fib(1) = 1
fib(2) = 1
fib(3) = 2
fib(4) = 3
fib(5) = 5
fib(6) = 8
fib(7) = 13
fib(8) = 21
fib(9) = 34

👤 USER: What files do I have?

🤖 AGENT: Let me check:
list_files(".")

Contents of .:
  📄 fibonacci.py (156 bytes)
```

## Security

**Sandboxing:**
- All file operations restricted to `/home/todd/olympus/agent-workspace`
- Cannot access files outside workspace
- Path traversal attacks prevented

**Command Restrictions:**
- Only whitelisted commands allowed
- No destructive system commands
- 30-second timeout on all executions

**Code Execution:**
- Python code runs in isolated subprocess
- Limited to workspace directory
- Cannot import dangerous modules (blocked by Python's normal security)

## Tool Schemas

The tools are defined with OpenAPI-style schemas in `tools.py` (`TOOL_SCHEMAS`). These schemas can be passed to models that support function calling.

For models without native function calling support (like Ollama models), we use simple string parsing to detect and execute function calls.

## Disabling Tools

To create an agent without tools:

```python
agent = MemGPTAgent(
    name="no-tools-agent",
    model_id="llama3.1:8b",
    enable_tools=False
)
```

## Testing Tools

Test the tools directly:

```bash
cd /home/todd/olympus/systems/memory-engine/prototype
python3 tools.py
```

This runs through all tool functions and verifies they work correctly.
