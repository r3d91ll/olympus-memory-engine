#!/usr/bin/env python3
"""
Interactive chat with MemGPT agent
"""

from memgpt_agent import MemGPTAgent, MemoryStorage
import ollama
import yaml
import sys
import os


def load_config():
    """Load config file"""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(config_path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # Return default config if file doesn't exist
        return {
            "default_model": "llama3.1:8b",
            "default_agent": "assistant",
            "embedding_model": "nomic-embed-text",
            "memory": {
                "fifo_queue_size": 10,
                "archival_search_limit": 5,
                "max_tokens": 512,
                "temperature": 0.7,
            },
            "models": [],
        }


def get_available_models():
    """Get list of models from Ollama"""
    try:
        models = ollama.list()
        return [m["name"] for m in models["models"]]
    except Exception as e:
        print(f"Warning: Could not fetch Ollama models: {e}")
        return []


def select_model(config):
    """Let user select a model"""
    print("\n📦 Available models:")

    # Get models from Ollama
    ollama_models = get_available_models()

    if ollama_models:
        print("\n  From Ollama:")
        for i, model in enumerate(ollama_models, 1):
            print(f"  {i}. {model}")

    # Show configured models if any
    if config.get("models"):
        print("\n  Recommended (from config.yaml):")
        for model in config["models"]:
            print(f"  • {model['id']} - {model['description']}")

    print(f"\n  Default: {config['default_model']}")
    print("\n💡 You can enter:")
    print("  - A number from the list above")
    print("  - Any model ID (e.g., 'llama3.1:8b')")
    print("  - Just press Enter for default")

    choice = input("\nSelect model: ").strip()

    if not choice:
        return config["default_model"]

    # Check if it's a number
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ollama_models):
            return ollama_models[idx]

    # Otherwise treat as model ID
    return choice


def chat_interface():
    """Interactive chat loop"""
    print("=" * 70)
    print("Olympus Memory Engine - Interactive Chat")
    print("=" * 70)

    # Load config
    config = load_config()

    # Select model
    model_id = select_model(config)

    # Choose or create agent
    agent_name = input(f"\nAgent name (default='{config['default_agent']}'): ").strip()
    agent_name = agent_name or config["default_agent"]

    print(f"\n🤖 Initializing {agent_name} with {model_id}...")
    storage = MemoryStorage()
    agent = MemGPTAgent(name=agent_name, model_id=model_id, storage=storage)

    print(f"\n✅ Ready! Agent ID: {agent.agent_id}")
    print("\nCommands:")
    print("  /stats    - Show agent statistics")
    print("  /memory   - Search archival memory")
    print("  /save     - Save current context to memory")
    print("  /reset    - Clear conversation (keeps archival memory)")
    print("  /help     - Show this help")
    print("  /quit     - Exit chat")
    print("\n" + "=" * 70)
    print()

    # Chat loop
    while True:
        try:
            user_input = input("👤 YOU: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input == "/quit":
                print("\n👋 Goodbye!")
                break

            elif user_input == "/help":
                print("\n📖 Commands:")
                print("  /stats    - Show agent statistics")
                print("  /memory   - Search archival memory")
                print("  /save     - Save current context to memory")
                print("  /reset    - Clear conversation")
                print("  /quit     - Exit\n")
                continue

            elif user_input == "/stats":
                stats = agent.get_stats()
                print("\n📊 Agent Statistics:")
                for key, value in stats.items():
                    print(f"   {key}: {value}")
                print()
                continue

            elif user_input == "/memory":
                query = input("   Search query: ").strip()
                if query:
                    result = agent.search_memory(query)
                    print(f"\n   {result}\n")
                continue

            elif user_input == "/save":
                context = input("   What to save: ").strip()
                if context:
                    result = agent.save_memory(context)
                    print(f"\n   {result}\n")
                continue

            elif user_input == "/reset":
                agent.fifo_queue.clear()
                print("\n🔄 Conversation cleared (archival memory preserved)\n")
                continue

            # Regular chat
            response = agent.chat(user_input)
            print(f"🤖 {agent.name.upper()}: {response}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            import traceback
            traceback.print_exc()

    storage.close()
    print()


if __name__ == "__main__":
    chat_interface()
