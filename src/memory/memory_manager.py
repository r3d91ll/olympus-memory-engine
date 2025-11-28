"""Hierarchical memory management for MemGPT.

Implements the four-tier memory hierarchy:
1. System Memory: Static instructions (context flow, function schemas)
2. Working Memory: Editable facts about agent/conversation
3. FIFO Queue: Recent conversation history with overflow
4. Archival Storage: Searchable external persistent memory
"""

from collections import deque
from typing import Any, cast
from uuid import UUID

from src.config.settings import get_settings
from src.logging.logger import get_logger
from src.memgpt_core.external_storage import ExternalStorage

logger = get_logger(__name__)


class Message:
    """Represents a single message in the conversation history."""

    def __init__(
        self,
        role: str,
        content: str,
        function_name: str | None = None,
        function_args: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a message.

        Args:
            role: Message role (user, assistant, function)
            content: Message content
            function_name: Function name if role is function
            function_args: Function arguments if role is function
        """
        self.role = role
        self.content = content
        self.function_name = function_name
        self.function_args = function_args

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary format."""
        msg_dict: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.function_name:
            msg_dict["function_name"] = self.function_name
        if self.function_args:
            msg_dict["function_args"] = self.function_args
        return msg_dict

    def token_count(self) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 chars)."""
        total_chars = len(self.content)
        if self.function_name:
            total_chars += len(self.function_name)
        if self.function_args:
            total_chars += len(str(self.function_args))
        return total_chars // 4

    def __repr__(self) -> str:
        """String representation."""
        return f"Message(role={self.role}, content={self.content[:50]}...)"


class MemoryManager:
    """Manages hierarchical memory for a MemGPT agent."""

    def __init__(
        self,
        agent_id: UUID,
        storage: ExternalStorage,
        system_memory: str | None = None,
        working_memory: str | None = None,
    ) -> None:
        """Initialize memory manager.

        Args:
            agent_id: Agent UUID
            storage: External storage backend
            system_memory: Initial system memory content
            working_memory: Initial working memory content
        """
        settings = get_settings()
        self.agent_id = agent_id
        self.storage = storage

        # System memory: Static instructions and function schemas
        self.system_memory = system_memory or self._default_system_memory()

        # Working memory: Editable facts about agent/conversation
        self.working_memory = working_memory or self._default_working_memory()

        # FIFO queue: Recent conversation history
        self.max_fifo_tokens = settings.memgpt_fifo_queue_size
        self.fifo_queue: deque[Message] = deque()
        self._fifo_token_count = 0

        # Load existing conversation history from storage
        self._load_recent_conversation()

        logger.info(
            "Memory manager initialized",
            agent_id=str(agent_id),
            system_memory_len=len(self.system_memory),
            working_memory_len=len(self.working_memory),
            fifo_size=len(self.fifo_queue),
        )

    def _default_system_memory(self) -> str:
        """Get default system memory instructions."""
        return """You are a MemGPT agent with hierarchical memory capabilities.

You have access to the following memory operations:
- core_memory_append: Add new information to working memory
- core_memory_replace: Modify existing information in working memory
- archival_memory_insert: Store information in long-term archival memory
- archival_memory_search: Search through archival memory
- conversation_search: Search recent conversation history

Your memory is organized hierarchically:
1. System Memory: These instructions (read-only)
2. Working Memory: Facts about yourself and current conversation (editable)
3. FIFO Queue: Recent conversation history (automatic)
4. Archival Memory: Long-term storage (searchable)

Use memory operations to manage what you remember."""

    def _default_working_memory(self) -> str:
        """Get default working memory content."""
        return """Agent Status:
- I am a MemGPT agent focused on measuring geometric conveyance
- My purpose is to learn from human input and organize information in memory
- I track dimensional preservation of semantic information

Current Context:
- Empty working memory, ready to learn
"""

    def _load_recent_conversation(self) -> None:
        """Load recent conversation history from storage into FIFO queue."""
        settings = get_settings()
        history = self.storage.get_conversation_history(
            self.agent_id,
            limit=settings.memgpt_conversation_search_limit,
        )

        for entry in history:
            msg = Message(
                role=entry["role"],
                content=entry["content"],
                function_name=entry.get("function_name"),
                function_args=entry.get("function_args"),
            )
            self._add_to_fifo_internal(msg)

    def _add_to_fifo_internal(self, message: Message) -> None:
        """Add message to FIFO queue (internal, no storage)."""
        msg_tokens = message.token_count()

        # If adding this message would exceed limit, remove oldest messages
        while self._fifo_token_count + msg_tokens > self.max_fifo_tokens and self.fifo_queue:
            removed = self.fifo_queue.popleft()
            self._fifo_token_count -= removed.token_count()
            logger.debug(
                "FIFO overflow: removed oldest message",
                removed_role=removed.role,
                remaining_messages=len(self.fifo_queue),
            )

        self.fifo_queue.append(message)
        self._fifo_token_count += msg_tokens

    def add_message(
        self,
        role: str,
        content: str,
        function_name: str | None = None,
        function_args: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to conversation history.

        Args:
            role: Message role (user, assistant, function)
            content: Message content
            function_name: Function name if role is function
            function_args: Function arguments if role is function
        """
        message = Message(role, content, function_name, function_args)

        # Add to FIFO queue
        self._add_to_fifo_internal(message)

        # Persist to storage
        self.storage.insert_conversation(
            self.agent_id,
            role=role,  # type: ignore
            content=content,
            function_name=function_name,
            function_args=function_args,
        )

        logger.debug(
            "Message added to memory",
            agent_id=str(self.agent_id),
            role=role,
            fifo_size=len(self.fifo_queue),
            fifo_tokens=self._fifo_token_count,
        )

    def get_context_window(self) -> str:
        """Get the full context window for the LLM.

        Returns:
            Formatted context string with all memory tiers
        """
        context_parts = [
            "=== SYSTEM MEMORY ===",
            self.system_memory,
            "",
            "=== WORKING MEMORY ===",
            self.working_memory,
            "",
            "=== RECENT CONVERSATION ===",
        ]

        # Add FIFO queue messages
        for msg in self.fifo_queue:
            if msg.role == "function":
                context_parts.append(
                    f"[Function: {msg.function_name}] {msg.content}"
                )
            else:
                context_parts.append(f"{msg.role.upper()}: {msg.content}")

        return "\n".join(context_parts)

    def update_working_memory(self, new_content: str) -> None:
        """Update working memory content.

        Args:
            new_content: New working memory content
        """
        self.working_memory = new_content
        self.storage.update_agent_memory(self.agent_id, working_memory=new_content)
        logger.info(
            "Working memory updated",
            agent_id=str(self.agent_id),
            content_length=len(new_content),
        )

    def append_to_working_memory(self, text: str) -> None:
        """Append text to working memory.

        Args:
            text: Text to append
        """
        self.working_memory += f"\n{text}"
        self.storage.update_agent_memory(self.agent_id, working_memory=self.working_memory)
        logger.info(
            "Text appended to working memory",
            agent_id=str(self.agent_id),
            appended_length=len(text),
        )

    def replace_in_working_memory(self, old_text: str, new_text: str) -> bool:
        """Replace text in working memory.

        Args:
            old_text: Text to replace
            new_text: Replacement text

        Returns:
            True if replacement was made, False if old_text not found
        """
        if old_text in self.working_memory:
            self.working_memory = self.working_memory.replace(old_text, new_text)
            self.storage.update_agent_memory(self.agent_id, working_memory=self.working_memory)
            logger.info(
                "Working memory text replaced",
                agent_id=str(self.agent_id),
                old_length=len(old_text),
                new_length=len(new_text),
            )
            return True
        else:
            logger.warning(
                "Working memory replacement failed: text not found",
                agent_id=str(self.agent_id),
                old_text=old_text[:100],
            )
            return False

    def insert_archival_memory(
        self,
        content: str,
        embedding: list[float] | None = None,
    ) -> UUID:
        """Insert content into archival memory.

        Args:
            content: Content to store
            embedding: Optional vector embedding

        Returns:
            UUID of created memory entry
        """
        memory_id = cast(
            UUID,
            self.storage.insert_memory(
                self.agent_id,
                content,
                memory_type="archival",
                embedding=embedding,
            ),
        )
        logger.info(
            "Archival memory inserted",
            agent_id=str(self.agent_id),
            memory_id=str(memory_id),
            content_length=len(content),
        )
        return memory_id

    def search_archival_memory(
        self,
        query_embedding: list[float],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search archival memory by semantic similarity.

        Args:
            query_embedding: Query vector
            limit: Maximum number of results

        Returns:
            List of matching memory entries
        """
        settings = get_settings()
        limit = limit or settings.memgpt_archival_search_limit

        results = cast(
            list[dict[str, Any]],
            self.storage.search_memory(
                self.agent_id,
                query_embedding,
                memory_type="archival",
                limit=limit,
            ),
        )

        logger.info(
            "Archival memory search completed",
            agent_id=str(self.agent_id),
            result_count=len(results),
        )

        return results

    def search_conversation_history(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[Message]:
        """Search recent conversation history.

        Args:
            query: Search query text
            limit: Maximum number of results

        Returns:
            List of matching messages from FIFO queue
        """
        settings = get_settings()
        limit = limit or settings.memgpt_conversation_search_limit

        # Simple text matching in FIFO queue
        matches = [
            msg for msg in self.fifo_queue
            if query.lower() in msg.content.lower()
        ][:limit]

        logger.info(
            "Conversation history search completed",
            agent_id=str(self.agent_id),
            query=query[:50],
            result_count=len(matches),
        )

        return matches

    def get_memory_stats(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dictionary with memory statistics
        """
        return {
            "agent_id": str(self.agent_id),
            "system_memory_chars": len(self.system_memory),
            "working_memory_chars": len(self.working_memory),
            "fifo_messages": len(self.fifo_queue),
            "fifo_tokens": self._fifo_token_count,
            "fifo_capacity": self.max_fifo_tokens,
            "fifo_utilization": self._fifo_token_count / self.max_fifo_tokens,
        }
