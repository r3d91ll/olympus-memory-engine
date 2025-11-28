# External Actor System - Design Document

**Date**: October 27, 2025
**Status**: DESIGN PHASE
**Purpose**: Distinguish between internal agents (part of Olympus) and external actors (users/systems interacting with Olympus)

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Current Behavior vs Desired Behavior](#current-behavior-vs-desired-behavior)
3. [Architecture Overview](#architecture-overview)
4. [Data Structures](#data-structures)
5. [Implementation Phases](#implementation-phases)
6. [Testing Strategy](#testing-strategy)
7. [Migration Plan](#migration-plan)
8. [Open Questions](#open-questions)

---

## Problem Statement

### The Core Issue

Internal agents (alice, bob, etc.) cannot distinguish between:
- **External actors** (todd, claude, testers) - users/systems interacting WITH Olympus
- **Internal agents** (alice, bob, coder) - agents running ON Olympus

This causes agents to incorrectly attempt to use `message_agent()` to contact external actors, resulting in errors.

### Example of Current Bug

```
User "todd": @alice do you know my name
Alice: *tries to call message_agent("todd", "What is your real response?...")*
Error: Agent 'todd' not found and could not be created
```

**Why this happens:**
- Alice sees "todd" in the conversation
- Doesn't know todd is EXTERNAL (outside the agent network)
- Treats todd as a peer agent and tries to message them
- Fails because todd has no agent record in the database

### What Should Happen

```
User "todd": @alice do you know my name
Alice: I don't see your name in my memory. Could you tell me?
```

Alice should recognize todd as an external actor and respond DIRECTLY, not try to route a message.

---

## Current Behavior vs Desired Behavior

### Current Behavior

**Agent Context Window:**
```
=== SYSTEM MEMORY ===
You are alice, a MemGPT agent...

=== WORKING MEMORY ===
[facts about alice]

=== RECENT CONVERSATION ===
USER: @alice do you know my name
```

**Problems:**
1. ❌ Agent doesn't know WHO "USER" is
2. ❌ Agent doesn't know if USER is internal or external
3. ❌ No context about other participants in the conversation
4. ❌ No join/leave announcements

### Desired Behavior

**Agent Context Window:**
```
=== SYSTEM MEMORY ===
You are alice, a MemGPT agent...

UNDERSTANDING PARTICIPANTS:

EXTERNAL ACTORS (outside Olympus):
- todd (human user, primary)
- claude (AI assistant)
- These are users interacting WITH the system
- Respond DIRECTLY to them, never use message_agent()

INTERNAL AGENTS (inside Olympus, your peers):
- alice, bob, coder, qwen, assistant
- Use message_agent() to collaborate with them

=== CURRENT PARTICIPANTS ===
External: todd (human user, primary)
Internal: alice, bob, coder, qwen, assistant

=== WORKING MEMORY ===
[facts about alice]

=== RECENT CONVERSATION ===
[SYSTEM] todd (human user, primary) has joined the conversation
TODD: @alice do you know my name
```

**Benefits:**
1. ✅ Agent knows todd is EXTERNAL (don't message, respond directly)
2. ✅ Agent knows alice, bob, etc. are INTERNAL (can message)
3. ✅ Clear participant list in every context
4. ✅ System announcements provide join/leave context

---

## Architecture Overview

### Key Concepts

**Internal Agents:**
- Running ON the Olympus server
- Have database records (agents table)
- Have memory, tools, conversation history
- Can message each other via `message_agent()`
- Examples: alice, bob, coder, qwen, assistant

**External Actors:**
- Users/systems interacting WITH Olympus
- Do NOT have agent database records
- May be human or AI or other systems
- May be local or remote
- Agents respond to them directly (not via message_agent)
- Examples: todd (human), claude (AI), testers, future external agents

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                   External Actors                       │
│  (todd, claude, testers - outside the system)           │
└──────────────────┬──────────────────────────────────────┘
                   │
                   │ Interact via Terminal/CLI
                   ↓
┌─────────────────────────────────────────────────────────┐
│                  Agent Manager                          │
│  • Track external actors (who's connected)              │
│  • Broadcast system messages (join/leave)               │
│  • Route messages (internal only)                       │
│  • Prevent routing to external actors                   │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│                  Internal Agents                        │
│  alice, bob, coder, qwen, assistant                     │
│  • Receive join/leave announcements                     │
│  • See participant list in context                      │
│  • Know who's external vs internal                      │
└─────────────────────────────────────────────────────────┘
```

### Data Flow: External Actor Joins

```
1. User starts Olympus:
   $ poetry run olympus

2. System prompts for identity:
   "Who are you? 1. todd  2. claude  3. other"

3. User selects "todd"

4. Agent Manager:
   - Registers todd as external actor
   - Broadcasts: "[SYSTEM] todd (human user) has joined"

5. All internal agents:
   - Receive system message in FIFO queue
   - Message saved to conversation_history
   - Context window updated with participant list

6. User sees:
   "[SYSTEM] todd (human user) has joined the conversation"
   >>> [ready for input]
```

### Data Flow: Message to Agent

```
1. todd types: @alice hello

2. Agent Manager:
   - Routes to alice
   - Passes "hello" with context that it's from todd

3. Alice's context includes:
   - System memory (with internal vs external explanation)
   - Participant list (todd is EXTERNAL)
   - Recent conversation

4. Alice generates response:
   - Knows todd is external
   - Responds directly (doesn't try message_agent)

5. Response displayed to todd
```

---

## Data Structures

### External Actor Registry

**Location**: `AgentManager.external_actors` (in-memory dict)

```python
external_actors: Dict[str, ExternalActor] = {
    "todd": {
        "actor_id": "ext_todd_12345",  # Unique ID
        "type": "human",                # human, ai_assistant, external_agent
        "display_name": "todd",
        "description": "human user, primary",
        "connected_at": datetime(2025, 10, 27, 15, 30, 0),
        "connection_type": "local_terminal",  # or remote_ssh, api, etc.
        "metadata": {
            "session_id": "sess_abc123",
            "ip_address": "127.0.0.1",  # For remote connections
        }
    }
}
```

**Type Definition:**
```python
from typing import TypedDict, Literal
from datetime import datetime

class ExternalActor(TypedDict):
    actor_id: str
    type: Literal["human", "ai_assistant", "external_agent", "other"]
    display_name: str
    description: str
    connected_at: datetime
    connection_type: str
    metadata: dict
```

### Configuration: Predefined External Actors

**Location**: `config.yaml`

```yaml
# External actors (users/systems that can connect)
external_actors:
  - actor_id: todd
    type: human
    display_name: todd
    description: human user, primary
    requires_auth: false  # For future authentication

  - actor_id: claude
    type: ai_assistant
    display_name: claude
    description: AI assistant (Anthropic Claude)
    requires_auth: false

  - actor_id: tester1
    type: human
    display_name: tester1
    description: external tester
    requires_auth: true  # Future: require password

  # Allow creation of new external actors at runtime
  allow_dynamic_creation: true
```

### Database Schema Changes

**Option 1: No database changes** (recommended for MVP)
- External actors tracked only in-memory
- Session data not persisted
- Simple, no migration needed

**Option 2: Track external actor sessions** (future enhancement)

```sql
-- New table for external actor sessions
CREATE TABLE external_actor_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id VARCHAR(100) NOT NULL,
    actor_type VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP,
    connection_type VARCHAR(50),
    metadata JSONB
);

CREATE INDEX idx_external_actor_sessions_actor_id
    ON external_actor_sessions(actor_id);
CREATE INDEX idx_external_actor_sessions_connected_at
    ON external_actor_sessions(connected_at);
```

**Benefits of database tracking:**
- History of who connected when
- Session analytics
- Support for persistent connections
- Better audit trail

**Drawbacks:**
- More complex
- Requires migration
- May be overkill for MVP

**Decision for MVP**: Skip database changes, use in-memory only.

---

## Implementation Phases

### Phase 1: Core External Actor System (MVP)

**Goal**: Basic distinction between internal agents and external actors

**Components:**
1. ✅ External actor registry in AgentManager
2. ✅ Identity prompt on startup (with `--identity` flag support)
3. ✅ Broadcast system for join/leave announcements
4. ✅ Updated agent system prompts (with clearer internal vs external language)
5. ✅ Enhanced context window with participant list (cached)
6. ✅ Prevent routing to external actors (with graceful error messages)
7. ✅ Name collision detection (reject external actor names matching internal agents)
8. ✅ Existing agent prompt upgrade on load

**Files to modify:**
- `src/agents/agent_manager.py` (external actor registry, broadcast, participant list cache)
- `src/agents/memgpt_agent.py` (system prompts, context window, graceful error handling)
- `src/ui/shell.py` (identity prompt, --identity flag, join/leave display)
- `config.yaml` (external_actors section)

**Testing:**
- Unit tests for external actor registry
- Unit test for name collision detection
- Unit test for graceful error when messaging external actor
- Integration test for join announcements
- Integration test for participant list in context
- Manual test: Start as todd, message alice, verify no routing error
- Regression test: All 125 existing tests still pass

**Deliverable**: Agents can distinguish internal from external, no more routing errors, professional UX

**Estimated effort**: 5-6 hours (updated from 3-4 to account for edge cases and graceful degradation)

---

### Phase 2: Enhanced UX and Commands

**Goal**: Better visibility and control

**Components:**
1. `/who` command - Show current participants
2. `/identity` command - Show/change current identity
3. Rich terminal display for join/leave
4. Better error messages when external actor tries to join as existing agent name

**Files to modify:**
- `src/ui/shell.py`
- `src/ui/terminal_ui.py`

**Testing:**
- Test all new commands
- Test identity switching
- Test name collision (todd tries to join as "alice")

**Deliverable**: Professional chat room UX

**Estimated effort**: 2-3 hours

---

### Phase 3: Multiple Concurrent External Actors

**Goal**: Support multiple users/systems connected simultaneously

**Components:**
1. Multi-session support (different terminals, same actors dict)
2. Broadcast to all terminals (not just agents)
3. Handle disconnections gracefully
4. Show who sent each message in conversation

**Technical challenges:**
- Current shell.py is single-threaded
- Need message queue or pub/sub for multi-terminal
- May require websockets or similar

**Files to modify:**
- `src/ui/shell.py` (major refactor)
- `src/agents/agent_manager.py`

**Testing:**
- Two terminals, same machine
- Verify both see announcements
- Verify both see messages

**Deliverable**: Multi-user chat room

**Estimated effort**: 5-6 hours

**Note**: May defer to future if complex

---

### Phase 4: Remote Access and Authentication

**Goal**: Allow remote connections with security

**Components:**
1. SSH server or web interface
2. Authentication system
3. Session management
4. Rate limiting
5. Audit logging

**Technical approach:**
- Option A: SSH tunnel + tmux shared session
- Option B: Web interface (FastAPI + WebSockets)
- Option C: Custom TCP server

**Files to create:**
- `src/server/` (new directory)
- Authentication module
- Session manager

**Testing:**
- Remote connection test
- Authentication test
- Security audit

**Deliverable**: Remote multi-user system

**Estimated effort**: 10-15 hours

**Note**: Definitely defer to future (post-MVP)

---

## Testing Strategy

### Unit Tests

**File**: `tests/test_external_actors.py` (new)

```python
def test_register_external_actor():
    """Test registering an external actor"""
    manager = AgentManager()
    manager.register_external_actor("todd", "human", "human user, primary")

    assert "todd" in manager.external_actors
    assert manager.external_actors["todd"]["type"] == "human"

def test_prevent_routing_to_external_actor():
    """Test that routing to external actor raises error"""
    manager = AgentManager()
    manager.register_external_actor("todd", "human", "human user, primary")

    with pytest.raises(ValueError, match="Cannot route to external actor"):
        manager.route_message("todd", "hello")

def test_broadcast_system_message():
    """Test broadcasting to all agents"""
    manager = AgentManager()
    # Create agents
    manager.create_agent("alice", "llama3.1:8b")
    manager.create_agent("bob", "llama3.1:8b")

    # Broadcast
    manager.broadcast_system_message("todd has joined")

    # Verify both agents received message
    alice = manager.get_agent("alice")
    bob = manager.get_agent("bob")

    assert len(alice.fifo_queue) == 1
    assert "[SYSTEM]" in alice.fifo_queue[0]["content"]
    assert len(bob.fifo_queue) == 1
```

### Integration Tests

**File**: `tests/test_external_actor_integration.py` (new)

```python
def test_external_actor_join_announcement():
    """Test that all agents receive join announcement"""
    manager = AgentManager()
    storage = MemoryStorage()

    # Create internal agents
    alice = manager.create_agent("alice", "llama3.1:8b", storage=storage)
    bob = manager.create_agent("bob", "llama3.1:8b", storage=storage)

    # External actor joins
    manager.connect_external_actor("todd", "human", "human user, primary")

    # Check alice's conversation history
    alice_history = storage.get_conversation_history(alice.agent_id, limit=10)
    assert any("[SYSTEM]" in msg["content"] and "todd" in msg["content"]
               for msg in alice_history)

    # Check bob's conversation history
    bob_history = storage.get_conversation_history(bob.agent_id, limit=10)
    assert any("[SYSTEM]" in msg["content"] and "todd" in msg["content"]
               for msg in bob_history)

def test_agent_context_includes_participants():
    """Test that agent context window includes participant list"""
    manager = AgentManager()
    manager.register_external_actor("todd", "human", "human user, primary")

    alice = manager.create_agent("alice", "llama3.1:8b")
    context = alice.get_context_window()

    # Should mention external actors
    assert "EXTERNAL ACTORS" in context or "External:" in context
    assert "todd" in context

    # Should mention internal agents
    assert "INTERNAL AGENTS" in context or "Internal:" in context
```

### Manual Testing Scenarios

**Scenario 1: Basic join and interaction**
```
1. Start Olympus: poetry run olympus
2. Select identity: todd
3. Verify join announcement appears
4. Send message: @alice hello
5. Verify alice responds without routing error
6. Exit: /exit
7. Verify leave announcement appears
```

**Scenario 2: Agent collaboration with external actor present**
```
1. Join as todd
2. Message: @alice ask bob to create test.txt
3. Verify alice uses message_agent("bob", ...) correctly
4. Verify alice does NOT try to message todd
5. Verify file is created
```

**Scenario 3: Multiple agents, one external actor**
```
1. Join as todd
2. Message: @alice @bob @coder everyone work together on a Python script
3. Verify agents collaborate using message_agent
4. Verify no one tries to message todd
```

**Scenario 4: Name collision**
```
1. Join as "alice" (same name as internal agent)
2. Should either:
   - Reject: "Name 'alice' reserved for internal agent"
   - Or auto-rename: "Joining as 'alice_external'"
```

---

## Migration Plan

### Backwards Compatibility

**Goal**: Existing agents and conversations should work without changes

**Approach**:
1. **Default behavior if no identity provided**:
   - Use generic "user" as external actor name
   - No breaking changes to existing workflows

2. **Existing agent data**:
   - No database migration needed (Phase 1)
   - Existing agents load normally
   - System prompts updated on next agent creation

3. **Existing tests**:
   - Update tests that expect specific error messages
   - Add new tests for external actor system
   - All existing tests should still pass

### Migration Steps

**Step 1: Add without breaking**
- Add external actor system alongside existing code
- Don't require identity on startup (make it optional)
- Default to "user" if not provided

**Step 2: Update tests**
- Fix any failing tests
- Add new tests for external actor features

**Step 3: Enable by default**
- Make identity prompt required (but allow --no-identity flag)
- Update documentation

**Step 4: Deprecate old behavior**
- Remove --no-identity flag
- Remove fallback to "user"
- Require explicit identity

### Rollback Plan

If Phase 1 implementation causes problems:
1. Revert changes to `memgpt_agent.py` system prompts
2. Revert changes to `agent_manager.py` routing
3. Keep identity prompt but make it no-op
4. All agents work as before

Git strategy:
```bash
# Create feature branch
git checkout -b feature/external-actors

# Implement Phase 1
git commit -m "feat: external actor system phase 1"

# If problems, easy to revert
git checkout main
```

---

## Open Questions

### Question 1: Identity Persistence

**Q**: Should we remember the last identity used?

**Options**:
A. Always ask on startup (simple, explicit)
B. Remember last identity in `~/.olympus/last_identity` (convenience)
C. Allow `--identity todd` flag to skip prompt (flexibility)

**DECISION**: **Option C + A** - Support flag, always prompt by default

```bash
# Default: always prompt
poetry run olympus

# Convenience: skip prompt with flag
poetry run olympus --identity todd

# Future: Remember last
poetry run olympus --identity last
```

**Rationale**: Gives flexibility without complexity. Flag is easy to implement and respects explicit user intent.

---

### Question 2: External Actor Names

**Q**: Can external actor names collide with internal agent names?

**Options**:
A. Reject: "Name 'alice' is reserved for internal agent"
B. Allow but auto-rename: "alice" → "alice_external"
C. Allow collision, distinguish by type in routing

**DECISION**: **Option A** - Reject with helpful error message

```python
if actor_name in [agent.name for agent in self.list_agents()]:
    raise ValueError(
        f"Name '{actor_name}' is reserved for internal agent. "
        f"Please choose a different name."
    )
```

**Rationale**: Clearest semantics, prevents confusion. Error message guides users to pick a different name.

---

### Question 3: Anonymous External Actors

**Q**: Should we allow anonymous/guest connections?

**Options**:
A. No - always require identity (more context for agents)
B. Yes - auto-assign "guest_1234" names (less friction)

**DECISION**: **Hybrid approach** - Require for MVP, design for future support

```yaml
# config.yaml
external_actors:
  allow_anonymous: false  # MVP: require identity
  anonymous_pattern: "guest_{timestamp}"  # Future: auto-naming
```

**Rationale**: Require identity for MVP (better agent context), but design system to support anonymous in future when adding remote access.

---

### Question 4: External Actor Capabilities

**Q**: Can external actors use tools?

**Current**: External actors don't have tool access (only send messages to agents)

**Future**: Could allow external actors to run commands directly?
- Example: `> ls` (todd runs ls command)
- vs: `@alice run ls` (alice runs ls command)

**DECISION**: **Keep simple for MVP, design for extensibility**

```python
@dataclass
class ExternalActor:
    # ...existing fields...
    capabilities: List[str] = field(default_factory=list)
    # Future: ["send_messages", "use_tools", "read_memory"]
```

**Rationale**: MVP - external actors only send messages (no tool access). Data structure allows adding capabilities later without breaking changes.

---

### Question 5: System Message Storage

**Q**: Where should system messages (join/leave) be stored?

**Options**:
A. Only in FIFO queue (in-memory, lost on agent restart)
B. In conversation_history (persistent, agents see on reload)
C. Separate system_messages table (better querying)

**DECISION**: **Option B with enhancements** - Store in conversation_history with message_type field

```python
# In storage layer
def add_system_message(self, agent_id: UUID, content: str):
    """Add system announcement (join/leave) to conversation history."""
    self.add_conversation_message(
        agent_id=agent_id,
        role="system",
        content=content,
        message_type="announcement"  # New field (future enhancement)
    )
```

**Rationale**: Agents should see join/leave history on reload. Consider adding message_type field to distinguish system messages from user messages. Ensures system messages don't pollute FIFO queue unnecessarily.

---

### Question 6: Participant List Update Frequency

**Q**: When should agents update their participant list understanding?

**Options**:
A. Only on join/leave (system messages in FIFO)
B. Every message (inject participant list into context)
C. Periodically (update working memory every N messages)

**DECISION**: **Option B with caching optimization** - Every message, but cache the participant list string

```python
class AgentManager:
    def __init__(self):
        self._participant_list_cache: Optional[str] = None
        self._cache_dirty: bool = True

    def _invalidate_participant_cache(self):
        """Mark cache as needing refresh."""
        self._cache_dirty = True

    def get_participant_list(self) -> str:
        """Get current participant list (cached)."""
        if self._cache_dirty or self._participant_list_cache is None:
            self._participant_list_cache = self._build_participant_list()
            self._cache_dirty = False
        return self._participant_list_cache

    def connect_external_actor(self, ...):
        # ...existing code...
        self._invalidate_participant_cache()
```

**Rationale**: Ensures agents always have current participant info without regenerating strings constantly.

---

## Additional Design Considerations

### 1. Improved Agent Prompt Clarity

Make system prompts more explicit about when to use `message_agent()`:

```python
UNDERSTANDING PARTICIPANTS:

EXTERNAL ACTORS (outside Olympus - NEVER use message_agent):
- todd (human user, primary)
- claude (AI assistant)
→ Respond DIRECTLY in your chat response
→ They cannot receive message_agent() calls
→ These are users interacting WITH the system

INTERNAL AGENTS (inside Olympus - CAN use message_agent):
- alice, bob, coder, qwen, assistant
→ Use message_agent() to collaborate with them
→ They have their own memory and tools
→ These are agents running ON the system

When to use message_agent():
✓ User asks you to tell another agent something
✓ Task would be better handled by specialist agent
✓ Need to collaborate with another agent

When to respond directly:
✓ User is asking YOU a question
✓ User is an external actor (todd, claude, etc.)
```

**Rationale**: More explicit guidance reduces confusion and makes the distinction crystal clear.

### 2. Graceful Degradation

If an agent mistakenly tries to message an external actor (defensive programming):

```python
def message_agent(self, target_agent: str, message: str) -> str:
    """Send a message to another agent and get response"""

    # Check if target is external actor (shouldn't happen, but be defensive)
    if self.agent_manager and target_agent in self.agent_manager.external_actors:
        error_msg = (
            f"ERROR: '{target_agent}' is an external actor, not an internal agent. "
            f"External actors cannot receive message_agent() calls. "
            f"Please respond directly to them in your chat response instead."
        )
        self.logger.warning(f"Attempted to message external actor: {target_agent}")
        return error_msg

    # ...existing routing logic...
```

**Benefits**:
- Gives LLM feedback to self-correct
- Better than cryptic "Agent not found" errors
- Helps LLM learn the distinction through feedback

### 3. Migration: Upgrading Existing Agent Prompts

Existing agents loaded from database have OLD system prompts without external/internal distinction.

**Solution**: Upgrade prompts on first load after update:

```python
def _load_agent_from_db(self, name: str):
    """Load existing agent from database"""
    existing = self.storage.get_agent_by_name(name)

    # ...load agent data...

    # Check if system prompt needs upgrade
    if "EXTERNAL ACTORS" not in existing["system_memory"]:
        self.logger.info(f"Upgrading system prompt for {name}")

        # Generate new system memory with participant understanding
        upgraded_prompt = self._default_system_memory()

        # Update in database
        self.storage.update_agent_system_memory(
            agent_id=existing["id"],
            system_memory=upgraded_prompt
        )

        # Use upgraded prompt for this agent instance
        self.system_memory = upgraded_prompt
    else:
        # Already upgraded, use as-is
        self.system_memory = existing["system_memory"]
```

**Benefits**:
- Existing agents get new context without manual intervention
- Idempotent (safe to run multiple times)
- Preserves custom modifications (if any) by regenerating from scratch

### 4. Enhanced Test Coverage

Add edge case test:

```python
def test_external_actor_message_attempt_rejected():
    """Verify agents cannot message external actors."""
    manager = AgentManager()
    storage = MemoryStorage()

    # Register external actor
    manager.connect_external_actor("todd", "human", "test user")

    # Create internal agent
    alice = manager.create_agent("alice", "llama3.1:8b", storage=storage)

    # Alice tries to message todd (external actor)
    result = alice.message_agent("todd", "Hello!")

    # Should get helpful error, not exception
    assert "ERROR" in result
    assert "external actor" in result.lower()
    assert "respond directly" in result.lower()
```

**Additional tests to add**:
- `test_name_collision_rejected()` - External actor can't use internal agent name
- `test_participant_list_cache_invalidation()` - Cache updates on join/leave
- `test_join_announcement_broadcast()` - All agents receive announcement
- `test_existing_agent_prompt_upgrade()` - Old agents get new prompts

---

## Next Steps

### Immediate (Design Phase)

1. ✅ Create this design document
2. ⏳ Review with Todd
3. ⏳ Address open questions
4. ⏳ Finalize Phase 1 scope

### Phase 1 Implementation (3-4 hours)

1. Update `config.yaml` with external_actors section
2. Modify `agent_manager.py`:
   - Add external_actors dict
   - Add register_external_actor()
   - Add broadcast_system_message()
   - Update route_message() to reject external actors
3. Modify `memgpt_agent.py`:
   - Update _default_system_memory() with internal vs external explanation
   - Update get_context_window() to include participant list
4. Modify `src/ui/shell.py`:
   - Add identity prompt on startup
   - Display join announcement
   - Handle /exit with leave announcement
5. Add tests:
   - Unit tests for external actor registry
   - Integration tests for announcements
6. Manual testing with scenarios above

### After Phase 1

- Evaluate what went well / what needs adjustment
- Plan Phase 2 implementation
- Consider if Phases 3-4 are needed or can be deferred

---

## Success Criteria

### Phase 1 Success = All of:

1. ✅ User can select identity on startup (or use `--identity` flag)
2. ✅ Agents receive join announcement (in FIFO and conversation_history)
3. ✅ Agents see participant list in context (cached for performance)
4. ✅ Agents distinguish internal vs external (clear system prompts)
5. ✅ No more "Agent 'todd' not found" errors
6. ✅ Name collisions rejected with helpful error
7. ✅ Graceful error when agent tries to message external actor
8. ✅ Existing agents get upgraded system prompts on load
9. ✅ All 125 existing tests still pass (zero regressions)
10. ✅ No noticeable performance degradation
11. ✅ Join/leave announcements feel natural, not spammy
12. ✅ Manual test scenarios pass

---

## References

### Related Documents
- `CAPABILITIES_REPORT.md` - Full system capabilities
- `TESTING_REPORT.md` - Current testing status
- `README.md` - Project overview

### Code Locations
- Agent system: `src/agents/`
- UI/Shell: `src/ui/`
- Storage: `src/memory/`
- Configuration: `config.yaml`

---

## Design Review and Approval

**Date**: October 27, 2025
**Reviewer**: Todd (primary user)
**Status**: ✅ **APPROVED - Ready for Phase 1 Implementation**

### Key Decisions Made

All 6 open questions resolved:
1. ✅ Identity persistence: Flag support + always prompt by default
2. ✅ Name collisions: Reject with helpful error
3. ✅ Anonymous actors: Require identity for MVP, design for future support
4. ✅ External actor capabilities: MVP simple (messages only), extensible design
5. ✅ System message storage: conversation_history with message_type consideration
6. ✅ Participant list updates: Every message with caching optimization

### Additional Enhancements Approved

1. ✅ Improved system prompt clarity (explicit when to use message_agent)
2. ✅ Graceful degradation (helpful error feedback)
3. ✅ Existing agent prompt upgrades (automatic migration)
4. ✅ Enhanced test coverage (edge cases and regressions)
5. ✅ Participant list caching (performance optimization)

### Risk Assessment

**Risk Level**: LOW ✅

- In-memory implementation (no database migration)
- Backwards compatible (defaults to "user" if no identity)
- Existing tests expected to pass
- Clear rollback plan (feature branch)

### Estimated Timeline

**Phase 1 Implementation**: 5-6 hours
- 3 hours: Core functionality (registry, broadcast, prompts, context)
- 1 hour: Edge cases and graceful degradation
- 1 hour: Testing (unit, integration, manual)
- 0.5 hour: Documentation updates

**Phase 2** (Optional): 2-3 hours
**Phases 3-4** (Future): Deferred until needed

### Success Metrics

**Phase 1 success** = 12 criteria (see Success Criteria section above)

**Critical path items**:
- Zero regressions (all 125 tests pass)
- No "Agent 'todd' not found" errors
- Agents distinguish internal vs external
- Professional UX (join/leave announcements)

---

**Status**: ✅ **DESIGN APPROVED - BEGIN PHASE 1 IMPLEMENTATION**

**Next**: Implement Phase 1 systematically with tests
