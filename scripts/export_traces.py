#!/usr/bin/env python3
"""
Export Traces for SFT Training

This script exports conversation traces from the OME database in formats
suitable for SFT (Supervised Fine-Tuning) training.

Exports include:
- Full conversation history with role labels
- Function calls and their results
- Multi-turn interactions in JSONL format

Usage:
    poetry run python scripts/export_traces.py --output traces.jsonl
    poetry run python scripts/export_traces.py --agent alice --format chat
    poetry run python scripts/export_traces.py --since 2025-01-01 --limit 1000
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class TraceExporter:
    """Export conversation traces for SFT training."""

    def __init__(self, connection_string: str | None = None):
        if connection_string is None:
            connection_string = (
                "host=/var/run/postgresql "
                "dbname=olympus_memory "
                "user=todd"
            )
        self.pool = ConnectionPool(connection_string, min_size=1, max_size=2)
        print("[TraceExporter] Connected to database")

    def close(self):
        self.pool.close()

    def get_agents(self) -> list[dict[str, Any]]:
        """Get all agents from the database."""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id, name, model_id, created_at FROM agents ORDER BY name")
                return cur.fetchall()

    def get_conversations(
        self,
        agent_id: UUID | None = None,
        agent_name: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get conversation history, optionally filtered."""

        where_clauses = []
        params: dict[str, Any] = {}

        # Resolve agent_name to agent_id
        if agent_name and not agent_id:
            with self.pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT id FROM agents WHERE name = %s", (agent_name,))
                    result = cur.fetchone()
                    if result:
                        agent_id = result["id"]

        if agent_id:
            where_clauses.append("c.agent_id = %(agent_id)s")
            params["agent_id"] = agent_id

        if since:
            where_clauses.append("c.created_at >= %(since)s")
            params["since"] = since

        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"
        limit_sql = f"LIMIT {limit}" if limit else ""

        query = f"""
            SELECT
                c.id,
                c.agent_id,
                a.name as agent_name,
                a.model_id,
                c.role,
                c.content,
                c.function_name,
                c.function_args,
                c.created_at
            FROM conversation_history c
            JOIN agents a ON c.agent_id = a.id
            WHERE {where_sql}
            ORDER BY c.created_at ASC
            {limit_sql}
        """

        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                return cur.fetchall()

    def to_chat_format(self, conversations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert conversations to OpenAI-style chat format.

        Groups messages into multi-turn conversations for SFT training.
        """
        # Group by agent_id for separate conversation threads
        by_agent: dict[str, list[dict[str, Any]]] = {}
        for conv in conversations:
            agent_name = conv["agent_name"]
            if agent_name not in by_agent:
                by_agent[agent_name] = []
            by_agent[agent_name].append(conv)

        chat_examples = []

        for agent_name, messages in by_agent.items():
            # Create training examples from user-assistant pairs
            current_messages = []

            for msg in messages:
                role = msg["role"]
                content = msg["content"]

                # Handle function calls specially
                if msg["function_name"]:
                    content = f"[Function: {msg['function_name']}]\n{content}"

                current_messages.append({
                    "role": role,
                    "content": content,
                })

                # When we see an assistant response, create a training example
                if role == "assistant" and len(current_messages) >= 2:
                    chat_examples.append({
                        "agent": agent_name,
                        "model": msg["model_id"],
                        "timestamp": msg["created_at"].isoformat() if msg["created_at"] else None,
                        "messages": list(current_messages),  # Copy the list
                    })

        return chat_examples

    def to_instruction_format(self, conversations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert to instruction-response format for SFT.

        Creates instruction/input/output triples suitable for fine-tuning.
        """
        examples = []

        # Pair up consecutive user-assistant messages
        i = 0
        while i < len(conversations) - 1:
            user_msg = conversations[i]
            assistant_msg = conversations[i + 1]

            if user_msg["role"] == "user" and assistant_msg["role"] == "assistant":
                # Create instruction-response pair
                instruction = user_msg["content"]
                response = assistant_msg["content"]

                # Add function context if present
                context = ""
                if assistant_msg["function_name"]:
                    context = f"Function called: {assistant_msg['function_name']}"
                    if assistant_msg["function_args"]:
                        context += f"\nArguments: {json.dumps(assistant_msg['function_args'])}"

                examples.append({
                    "instruction": instruction,
                    "input": context if context else "",
                    "output": response,
                    "agent": assistant_msg["agent_name"],
                    "model": assistant_msg["model_id"],
                    "timestamp": assistant_msg["created_at"].isoformat() if assistant_msg["created_at"] else None,
                })
                i += 2
            else:
                i += 1

        return examples

    def get_function_traces(
        self,
        agent_name: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get function call traces from conversation history.

        Extracts messages where function calls were made.
        """
        conversations = self.get_conversations(agent_name=agent_name, since=since)

        function_traces = []
        for conv in conversations:
            if conv["function_name"]:
                function_traces.append({
                    "agent": conv["agent_name"],
                    "model": conv["model_id"],
                    "function": conv["function_name"],
                    "arguments": conv["function_args"],
                    "result": conv["content"],
                    "timestamp": conv["created_at"].isoformat() if conv["created_at"] else None,
                })

        return function_traces

    def export_jsonl(self, data: list[dict[str, Any]], output_path: Path) -> int:
        """Export data to JSONL format."""
        with open(output_path, "w") as f:
            for item in data:
                f.write(json.dumps(item, default=str) + "\n")
        return len(data)

    def get_statistics(self) -> dict[str, Any]:
        """Get database statistics for trace collection."""
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Count agents
                cur.execute("SELECT COUNT(*) as count FROM agents")
                agent_count = cur.fetchone()["count"]

                # Count conversations
                cur.execute("SELECT COUNT(*) as count FROM conversation_history")
                conv_count = cur.fetchone()["count"]

                # Count by role
                cur.execute("""
                    SELECT role, COUNT(*) as count
                    FROM conversation_history
                    GROUP BY role
                """)
                role_counts = {row["role"]: row["count"] for row in cur.fetchall()}

                # Count function calls
                cur.execute("""
                    SELECT function_name, COUNT(*) as count
                    FROM conversation_history
                    WHERE function_name IS NOT NULL
                    GROUP BY function_name
                    ORDER BY count DESC
                """)
                function_counts = {row["function_name"]: row["count"] for row in cur.fetchall()}

                # Get date range
                cur.execute("""
                    SELECT
                        MIN(created_at) as first_message,
                        MAX(created_at) as last_message
                    FROM conversation_history
                """)
                date_range = cur.fetchone()

                return {
                    "agents": agent_count,
                    "total_messages": conv_count,
                    "by_role": role_counts,
                    "function_calls": function_counts,
                    "first_message": date_range["first_message"],
                    "last_message": date_range["last_message"],
                }


def main():
    parser = argparse.ArgumentParser(
        description="Export OME conversation traces for SFT training"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("traces.jsonl"),
        help="Output file path (default: traces.jsonl)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["chat", "instruction", "function", "raw"],
        default="chat",
        help="Export format (default: chat)",
    )
    parser.add_argument(
        "--agent", "-a",
        type=str,
        help="Filter by agent name",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Filter messages since date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of messages to export",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics and exit",
    )

    args = parser.parse_args()

    exporter = TraceExporter()

    try:
        if args.stats:
            print("\n=== OME Trace Statistics ===\n")
            stats = exporter.get_statistics()
            print(f"Agents: {stats['agents']}")
            print(f"Total Messages: {stats['total_messages']}")
            print(f"\nBy Role:")
            for role, count in stats["by_role"].items():
                print(f"  {role}: {count}")
            print(f"\nFunction Calls:")
            for func, count in stats["function_calls"].items():
                print(f"  {func}: {count}")
            if stats["first_message"]:
                print(f"\nDate Range: {stats['first_message']} to {stats['last_message']}")
            return

        # Parse date filter
        since = None
        if args.since:
            since = datetime.fromisoformat(args.since)

        # Get conversations
        print(f"\nFetching conversations...")
        conversations = exporter.get_conversations(
            agent_name=args.agent,
            since=since,
            limit=args.limit,
        )
        print(f"Found {len(conversations)} messages")

        if not conversations:
            print("No conversations to export.")
            return

        # Convert to requested format
        if args.format == "chat":
            data = exporter.to_chat_format(conversations)
            print(f"Created {len(data)} chat examples")
        elif args.format == "instruction":
            data = exporter.to_instruction_format(conversations)
            print(f"Created {len(data)} instruction examples")
        elif args.format == "function":
            data = exporter.get_function_traces(agent_name=args.agent, since=since)
            print(f"Found {len(data)} function traces")
        else:  # raw
            data = [
                {
                    "agent": c["agent_name"],
                    "role": c["role"],
                    "content": c["content"],
                    "function": c["function_name"],
                    "timestamp": c["created_at"].isoformat() if c["created_at"] else None,
                }
                for c in conversations
            ]

        # Export
        count = exporter.export_jsonl(data, args.output)
        print(f"\nExported {count} records to {args.output}")

        # Show sample
        if data:
            print("\nSample record:")
            print(json.dumps(data[0], indent=2, default=str)[:500] + "...")

    finally:
        exporter.close()


if __name__ == "__main__":
    main()
