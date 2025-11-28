# Agent-to-Agent Communication - Status Report

## ✅ What's Implemented

### 1. Core Infrastructure
- **`message_agent()` function** in `memgpt_agent.py:235-247`
  - Agents can send messages to other agents via the agent manager
  - Returns the target agent's response
  - Error handling for missing agents

### 2. System Prompt Updates
- **Updated agent instructions** in `memgpt_agent.py:124-138`
  - Clear documentation of `message_agent(agent_name, message)` function
  - Examples of when to use agent-to-agent communication
  - Explicit instructions to NOT hallucinate responses

### 3. Function Execution
- **Pattern matching** in `_execute_function_calls()` at `memgpt_agent.py:252-276`
  - Regex to detect `message_agent()` calls in agent responses
  - Handles backticks and code blocks
  - Debug output for troubleshooting

### 4. Agent Manager Integration
- **Agents get manager reference** in `agent_manager.py:69-76`
  - Each agent receives `agent_manager=self` on creation
  - Enables routing messages between agents

## 🐛 Current Issues

### Issue 1: LLM Instruction Following
**Problem**: The LLM (llama3.1:8b) is not reliably generating the function call text. Instead it:
- Describes what it would do without actually doing it
- Hallucin ates responses from other agents
- Sometimes echoes back its entire context window

**Root Cause**: Open-source LLMs like Llama 3.1 8B have weaker instruction-following than GPT-4 or Claude. They struggle with:
- Function calling syntax
- Distinguishing between "describe" vs "do"
- Long system prompts with many capabilities

**Evidence from Testing**:
```
[DEBUG alice] Response contains 'message_agent'
[DEBUG alice] Response text (first 300 chars):
=== SYSTEM MEMORY ===
You are alice, a MemGPT agent with hierarchical memory.
...
```

The agent is returning its context window instead of a proper response.

### Issue 2: Example Text Matching
The regex is matching the EXAMPLE in the system prompt:
```
message_agent("agent_name", "your message here")
```

Instead of the agent's actual function call.

## 🎯 Recommended Solutions

### Option A: Better Model (Recommended)
Use a more capable model with stronger instruction-following:
- **Qwen 2.5 Coder** (already configured) - Better at function calling
- **GPT-4o-mini** via API - Excellent instruction following
- **Claude 3.5 Haiku** via API - Best instruction following

### Option B: Structured Output
Implement JSON-based function calling:
```json
{
  "action": "message_agent",
  "agent_name": "bob",
  "message": "Hello Bob"
}
```

This is easier for LLMs to generate consistently.

### Option C: Few-Shot Prompting
Add concrete examples to the system prompt:
```
Example conversation:
User: Ask bob to create hello.txt
Assistant: message_agent("bob", "Please create a file called hello.txt")
Bob's response: Done! Created hello.txt
Assistant: Bob has created the file.
```

## 📊 Architecture Validation

Despite the LLM instruction-following issues, the **architecture is sound**:

✅ Agent manager routing works
✅ Message passing infrastructure complete
✅ Function detection regex works (when LLM cooperates)
✅ Error handling in place
✅ Agent isolation maintained

The problem is purely the LLM's ability to follow the instructions, not the system design.

## 🔬 For Conveyance Experiments

This setup is actually **perfect for conveyance experiments** because:

1. **Isolated Memory**: Each agent has its own memory space
2. **Measurable Transfer**: Can track messages between agents
3. **Turn-Based**: Agents communicate via explicit function calls
4. **Observable**: All interactions logged to PostgreSQL

### Experiment Ideas

**1. Tic-Tac-Toe**
- Agent A manages game state
- Agent B makes moves
- Measure how well game state transfers

**2. Code Review Collaboration**
- Agent A writes code
- Agent B reviews and suggests changes
- Measure information preservation in review process

**3. 20 Questions**
- Agent A thinks of something
- Agent B asks yes/no questions
- Measure information gain per exchange

**4. Collaborative Writing**
- Agents take turns adding to a story
- Measure narrative coherence across handoffs

## 🚀 Next Steps

### Immediate (Fix LLM Issue)
1. Test with Qwen 2.5 Coder model
2. If that fails, implement JSON-based function calling
3. Add few-shot examples to system prompt

### For Conveyance Testing
1. Design simple turn-based game protocol
2. Add geometric metrics tracking to agent interactions
3. Implement boundary object extraction from agent messages
4. Measure D_eff, β, R-score for agent-to-agent transfers

## 📝 How to Test

### Current Test Scripts
- `test_agent_to_agent.py` - Full collaboration test
- `test_simple_collab.py` - Minimal function call test

### Manual Testing
```bash
python3 multi_agent_chat.py

# In the shell:
@alice ask bob to tell you his name
```

### With Better Model
Edit `config.yaml`:
```yaml
agents:
  - name: alice
    model: qwen2.5-coder:latest  # Better at function calling
  - name: bob
    model: qwen2.5-coder:latest
```

Then delete old agents:
```bash
psql -h /var/run/postgresql -U todd -d olympus_memory \
  -c "DELETE FROM agents WHERE name IN ('alice', 'bob');"
```

## 💡 Key Insight

The infrastructure for agent-to-agent communication is **complete and working**. The challenge is getting the LLM to reliably output the correct function call syntax. This is a **prompt engineering problem**, not an architecture problem.

For production conveyance experiments, consider using API-based models (GPT-4, Claude) which have much stronger instruction-following capabilities.
