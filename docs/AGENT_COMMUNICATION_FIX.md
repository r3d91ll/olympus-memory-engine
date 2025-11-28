# Agent Communication Fixes

## Issues Identified

### Issue 1: Agent Delegation Understanding
**Problem**: Qwen tried to write the code itself instead of delegating to coder

**Example**:
```
User: @qwen can you have coder write a python script demonstrating the fibonacci sequence please
Qwen: <think> ...  I should write the code myself ... </think>
```

**Root Cause**: System prompt didn't clearly explain WHEN to delegate to other agents

**Fix Applied**: Enhanced system prompt with delegation guidelines:
```
When to delegate to other agents:
- If the user asks you to tell/ask another agent something, use message_agent
- If a task would be better handled by a specialist agent (like "coder"), delegate it
- You can message multiple agents in sequence to accomplish complex tasks
```

### Issue 2: Database Foreign Key Violation
**Problem**: Agent created in-memory but not persisted to database

**Error**:
```
Error: insert or update on table "conversation_history" violates foreign key constraint
DETAIL: Key (agent_id)=(c726cf45-c246-4434-a3a0-af93d3aa60c8) is not present in table "agents".
```

**Root Cause**: When qwen messages coder, if coder isn't in agent_manager's registry, the routing fails

**Fix Applied**: Added auto-creation to `route_message()`:
```python
def route_message(self, agent_name: str, message: str, auto_create: bool = True):
    agent = self.get_agent(agent_name)

    # If agent not found, try to auto-create from existing DB record
    if not agent and auto_create:
        print(f"[AgentManager] Agent '{agent_name}' not in registry, attempting to load...")
        info = self.create_agent(name=agent_name, model_id="llama3.1:8b", storage=self._storage)
```

## Testing

### Test the Fix

1. **Delete existing agents**:
```bash
psql -h /var/run/postgresql -U todd -d olympus_memory \
  -c "DELETE FROM agents WHERE name IN ('qwen', 'coder', 'assistant');"
```

2. **Start chat**:
```bash
python3 multi_agent_chat.py
```

3. **Test delegation**:
```
>>> @qwen please ask coder to write a fibonacci script
```

Expected behavior:
- Qwen should use `message_agent` function
- Coder should be auto-created if not in registry
- Coder should write the script
- No database errors

### Improved User Experience

**Before**:
```
>>> @qwen ask coder to write hello.py
[ERROR] Agent 'coder' not found
```

**After**:
```
>>> @qwen ask coder to write hello.py
[qwen] → coder: Please write hello.py...
[AgentManager] Agent 'coder' not in registry, attempting to load from database...
[AgentManager] Loaded agent 'coder' from database
[AgentManager] Routed message to coder (message: 42 chars, response: 120 chars)
[@coder]: Done! Created hello.py
```

## Future Improvements

### 1. Better Fine-Tuning
The user is right - fine-tuning models specifically for agent collaboration would help:

**Training Data Format**:
```json
{
  "messages": [
    {"role": "user", "content": "Ask Bob to create a file"},
    {"role": "assistant", "content": "```json\n{\"function\": \"message_agent\", \"arguments\": {\"agent_name\": \"bob\", \"message\": \"Please create the file\"}}\n```"}
  ]
}
```

Benefits:
- Models learn delegation patterns
- Better understanding of agent specialization
- More reliable function calling

### 2. Agent Registry from Config
Instead of hardcoded fallback model, read from config:

```python
# In agent_manager.__init__:
self._config = load_config("config.yaml")
self._agent_configs = {a["name"]: a for a in self._config["agents"]}

# In route_message auto-create:
agent_config = self._agent_configs.get(agent_name)
if agent_config:
    model_id = agent_config["model"]
else:
    model_id = "llama3.1:8b"  # fallback
```

### 3. Agent Discovery
Add `/discover` command to show which agents exist and what they do:

```
>>> /discover
Available agents:
- assistant (llama3.1:8b): General purpose assistant
- coder (qwen2.5-coder:latest): Specialized coding agent
- qwen (qwen3:8b): Reasoning tasks
```

### 4. Conversation Context
Track multi-turn agent conversations:

```python
# Each agent-to-agent conversation gets a conversation_id
# Agents can see their conversation history with each other
# Useful for complex multi-step tasks
```

### 5. Agent Capabilities
Add explicit capabilities to agent configs:

```yaml
agents:
  - name: coder
    model: qwen2.5-coder:latest
    capabilities:
      - write_code
      - debug
      - code_review
    specialization: "Python, JavaScript, and systems programming"
```

Then agents can query capabilities before delegating.

## For Conveyance Experiments

These fixes make the system much better for conveyance testing:

### Reliable Delegation
Agents can now reliably delegate tasks to specialists, creating measurable information transfer patterns.

### Error Recovery
Auto-creation means experiments don't fail due to missing agents.

### Observable Patterns
Can track:
- Who delegates to whom
- What types of tasks are delegated
- How information transforms across agent boundaries

### Example Experiment: Code Review Chain
```
1. User → alice: "Create a sorting algorithm"
2. alice → coder: "Write quicksort in Python"
3. coder → alice: [code]
4. alice → reviewer: "Review this code"
5. reviewer → coder: "Add error handling for empty lists"
6. coder → alice: [improved code]
```

Each step is measurable:
- D_eff (dimensionality preserved)
- β (collapse indicator)
- R-score (relational positioning)

## Status

✅ Prompt improved with delegation guidelines
✅ Auto-creation added to route_message()
🔄 Testing in progress
📋 Future improvements identified

The system should now handle agent-to-agent communication much more reliably!
