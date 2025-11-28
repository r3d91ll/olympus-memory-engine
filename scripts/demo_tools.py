#!/usr/bin/env python3
"""
Demo: Agent using CLI tools
Shows agent creating files, running code, and remembering context
"""

from memgpt_agent import MemGPTAgent, MemoryStorage
import time


def demo():
    print("=" * 70)
    print("Olympus Memory Engine - CLI Tools Demo")
    print("=" * 70)
    print()

    storage = MemoryStorage()

    # Clean slate
    print("🧹 Cleaning up old demo agent...")
    import psycopg
    with psycopg.connect("host=/var/run/postgresql dbname=olympus_memory user=todd") as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agents WHERE name = 'demo-coder'")
            conn.commit()

    # Create agent
    print("🤖 Creating agent with tools enabled...")
    agent = MemGPTAgent(name="demo-coder", model_id="llama3.1:8b", storage=storage, enable_tools=True)
    print(f"✅ Agent ready: {agent.agent_id}\n")

    print("=" * 70)
    print("Demo Conversation")
    print("=" * 70)
    print()

    conversations = [
        "Hi! I'm Todd. Can you tell me about your workspace?",
        "Create a Python file called hello.py that prints 'Hello from the Memory Engine!'",
        "Now create a calculator.py that has add, subtract, multiply, and divide functions",
        "List all the files in your workspace",
        "Run the hello.py file",
    ]

    for msg in conversations:
        print(f"👤 TODD: {msg}")
        time.sleep(0.5)  # Dramatic pause

        response = agent.chat(msg)
        print(f"🤖 AGENT: {response}")
        print()
        time.sleep(1)

    # Show stats
    print("=" * 70)
    print("Agent Statistics")
    print("=" * 70)
    stats = agent.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Show workspace contents
    print("\n" + "=" * 70)
    print("Workspace Files Created")
    print("=" * 70)
    result = agent.tools.list_files(".")
    print(result)

    storage.close()
    print("\n" + "=" * 70)
    print("✅ Demo Complete!")
    print("=" * 70)
    print()
    print("Try it yourself:")
    print("  python3 chat.py")
    print()


if __name__ == "__main__":
    demo()
