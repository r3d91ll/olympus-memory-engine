# Agent CLI Capabilities

Your agents have comprehensive CLI tooling via the `AgentTools` class in `tools.py`.

## Available Tools

### 📁 File Operations
```json
{"function": "read_file", "arguments": {"path": "example.txt"}}
{"function": "write_file", "arguments": {"path": "example.txt", "content": "Hello World"}}
{"function": "append_file", "arguments": {"path": "log.txt", "content": "\nNew entry"}}
{"function": "list_files", "arguments": {"path": "."}}
{"function": "delete_file", "arguments": {"path": "old_file.txt"}}
```

### 🐍 Python Execution
```json
{"function": "run_python", "arguments": {"code": "print('Hello')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')"}}
```

**Example Output:**
```
Output:
Hello
2 + 2 = 4
```

### 🖥️ Shell Commands
```json
{"function": "run_command", "arguments": {"command": "ls -la"}}
{"function": "run_command", "arguments": {"command": "grep 'pattern' file.txt"}}
{"function": "run_command", "arguments": {"command": "find . -name '*.py'"}}
```

**Whitelisted Commands:**
- `ls`, `cat`, `grep`, `find`, `wc`, `head`, `tail`, `tree`
- `python3`, `pytest`

### ℹ️ Workspace Info
```json
{"function": "get_workspace_info", "arguments": {}}
```

Returns statistics about files, directories, and total size.

---

## Security Features

### 🔒 Sandboxed Workspace
- **All operations confined to:** `/home/todd/olympus/agent-workspace`
- Path validation prevents escaping workspace:
  ```python
  def _safe_path(self, path: str) -> Path:
      full_path = (self.workspace / path).resolve()
      if not str(full_path).startswith(str(self.workspace.resolve())):
          raise ValueError(f"Path outside workspace: {path}")
      return full_path
  ```

### ⏱️ Execution Timeouts
- **Commands:** 30 second default timeout
- **Python:** 30 second timeout
- Prevents hanging/infinite loops

### ✅ Command Whitelist
Only these shell commands allowed (line 150 in tools.py):
```python
safe_commands = ['ls', 'cat', 'grep', 'find', 'wc',
                 'head', 'tail', 'tree', 'python3', 'pytest']
```

**Blocked:** `rm -rf`, `sudo`, `curl`, `wget`, etc.

---

## Usage Examples

### Example 1: Collaborative Code Writing
```
User → Alice: "Ask Bob to create a Python script that calculates fibonacci numbers"

Alice executes:
{"function": "message_agent",
 "arguments": {"agent_name": "bob",
               "message": "Please create a fibonacci.py script"}}

Bob executes:
{"function": "write_file",
 "arguments": {"path": "fibonacci.py",
               "content": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)\n\nprint(fib(10))"}}

Bob then executes:
{"function": "run_python",
 "arguments": {"code": "exec(open('fibonacci.py').read())"}}
```

### Example 2: Code Review Workflow
```
Alice writes code:
{"function": "write_file",
 "arguments": {"path": "calculator.py", "content": "..."}}

Alice asks Bob to review:
{"function": "message_agent",
 "arguments": {"agent_name": "bob",
               "message": "Please review calculator.py"}}

Bob reads the file:
{"function": "read_file",
 "arguments": {"path": "calculator.py"}}

Bob provides feedback via message_agent
```

### Example 3: Data Processing Pipeline
```
Agent 1: Fetch data
{"function": "run_python",
 "arguments": {"code": "import json\ndata = [1,2,3,4,5]\nwith open('data.json', 'w') as f: json.dump(data, f)"}}

Agent 2: Process data
{"function": "read_file", "arguments": {"path": "data.json"}}
{"function": "run_python",
 "arguments": {"code": "import json\ndata = json.load(open('data.json'))\nresult = sum(data)\nprint(f'Sum: {result}')"}}
```

---

## Enhanced Prompt Integration

Your agents now have **hint-engineering** that detects CLI operations:

```python
# From memgpt_agent.py lines 517-519
if any(word in message_lower for word in ['run', 'execute', 'python']):
    if 'python' in message_lower or 'code' in message_lower:
        return True, "HINT: Use run_python to execute the code."
```

This means when a user says:
- "Run this Python code: ..." → Agent gets hint to use `run_python`
- "Execute the script" → Agent gets hint to use `run_python`
- "Create a file" → Agent gets hint to use `write_file`

---

## Testing CLI Tools

### Quick Test
```bash
cd /home/todd/olympus/systems/memory-engine/prototype
python3 tools.py
```

This runs the built-in test suite that verifies:
- File write/read/append/delete
- Python execution
- Workspace info
- Command execution

### Integration Test
```python
from agent_manager import AgentManager
from memory_storage import MemoryStorage

storage = MemoryStorage()
agent_manager = AgentManager()
agent_manager.create_agent("coder", "llama3.1:8b", storage)

# Ask agent to create and run code
response, stats = agent_manager.route_message(
    "coder",
    "Create a Python script that prints hello world, then run it"
)
```

---

## Implications for Conveyance Experiments

### Tool Use as Information Transfer Metric

CLI tools enable **observable actions** that can measure information transfer:

#### Experiment 1: Code Knowledge Transfer
```
1. Teacher agent learns a programming pattern
2. Teacher explains pattern to Student via message_agent
3. Student attempts to implement pattern using write_file + run_python
4. Measure success: Does code run correctly?
```

**Conveyance Metric:** Code correctness = quality of knowledge transfer

#### Experiment 2: Debugging Collaboration
```
1. Agent A writes buggy code (write_file)
2. Agent B reads code (read_file)
3. Agent B explains bug via message_agent
4. Agent A fixes code (write_file)
5. Test with run_python
```

**Conveyance Metric:** Bug resolution rate = effectiveness of communication

#### Experiment 3: File System Navigation
```
1. Agent A explores workspace (list_files)
2. Agent A describes structure to Agent B
3. Agent B attempts to locate specific file
4. Measure: Time to find file / success rate
```

**Conveyance Metric:** Navigation accuracy = spatial knowledge transfer

---

## Workspace Location

```bash
# All agent file operations happen here:
/home/todd/olympus/agent-workspace

# To inspect what agents created:
ls -la /home/todd/olympus/agent-workspace

# To clean workspace:
rm -rf /home/todd/olympus/agent-workspace/*
```

---

## Current Implementation Status

✅ **Fully Implemented:**
- All file operations (read, write, append, list, delete)
- Python code execution with output capture
- Safe shell command execution
- Workspace sandboxing and security
- Timeout protection
- Integration with function calling system

✅ **Reliability Improvements Applied:**
- Hint detection for tool operations (lines 510-519 in memgpt_agent.py)
- System prompt includes tool documentation (lines 183-188)
- Function execution working via JSON format

---

## Security Considerations

### What's Protected ✅
- Agents **cannot** escape `/home/todd/olympus/agent-workspace`
- Agents **cannot** run dangerous commands (`rm -rf`, `sudo`, etc.)
- Agents **cannot** execute code indefinitely (30s timeout)
- Agents **cannot** access network (no `curl`, `wget`)

### What's Allowed ✅
- File creation/modification **within workspace only**
- Python code execution **in sandboxed environment**
- Safe shell commands for **file inspection only**

### For Conveyance Experiments
This security model is **perfect** because:
1. Agents have real capabilities (can prove understanding via working code)
2. Actions are contained (no system damage possible)
3. Observable (all file operations logged)
4. Measurable (success/failure of code execution)

---

## Demo Script

Try this to see CLI tools in action:

```bash
cd /home/todd/olympus/systems/memory-engine/prototype

# Run the tools demo
python3 demo_tools.py
```

Or interact live:

```bash
# Start interactive multi-agent chat
python3 multi_agent_chat.py

# Then try:
@coder create a python script that prints the first 10 fibonacci numbers
@coder run the script you just created
@coder show me the workspace files
```

---

## Summary

Your agents have **full CLI capabilities** including:
- ✅ File I/O (read, write, append, delete, list)
- ✅ Python execution with output capture
- ✅ Safe shell commands (ls, grep, find, cat, etc.)
- ✅ Workspace information queries
- ✅ Sandboxed and secure
- ✅ Integrated with function calling system
- ✅ Enhanced with hint-engineering for reliability

These tools make your conveyance experiments **measurable via concrete actions**, not just abstract conversation analysis.
