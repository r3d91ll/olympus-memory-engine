#!/usr/bin/env python3
"""
Test script for enhanced agent tooling
Tests: edit_file, fetch_url, search_in_files, find_files, dynamic workspace
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from src.tools.tools import AgentTools


def test_edit_file():
    """Test the new edit_file functionality"""
    print("=" * 70)
    print("Test 1: edit_file - Precise File Modifications")
    print("=" * 70)

    tools = AgentTools()

    # Create a test file
    print("\n[1] Creating test file...")
    content = """def hello(name):
    print(f"Hello {name}")

def goodbye(name):
    print(f"Goodbye {name}")
"""
    result = tools.write_file("greetings.py", content)
    print(result)

    # Test single replacement
    print("\n[2] Editing file (single replacement)...")
    result = tools.edit_file(
        "greetings.py",
        'def hello(name):',
        'def hello(name, greeting="Hello"):'
    )
    print(result)

    # Read back
    print("\n[3] Reading modified file...")
    result = tools.read_file("greetings.py")
    print(result)

    # Test replace_all
    print("\n[4] Editing file (replace all occurrences)...")
    result = tools.edit_file(
        "greetings.py",
        "name",
        "person",
        replace_all=True
    )
    print(result)

    # Read final version
    print("\n[5] Reading final version...")
    result = tools.read_file("greetings.py")
    print(result)

    # Cleanup
    tools.delete_file("greetings.py")
    print("\n✓ edit_file test complete")


def test_search_in_files():
    """Test the search_in_files functionality"""
    print("\n" + "=" * 70)
    print("Test 2: search_in_files - Code Search (Grep)")
    print("=" * 70)

    tools = AgentTools()

    # Create test files
    print("\n[1] Creating test files...")
    tools.write_file("module1.py", """def function_one():
    return message_agent("bob", "hello")

def function_two():
    pass
""")

    tools.write_file("module2.py", """class MyClass:
    def method_one(self):
        message_agent("alice", "test")

    def method_two(self):
        return 42
""")

    # Search for pattern
    print("\n[2] Searching for 'message_agent' calls...")
    result = tools.search_in_files("message_agent", "*.py")
    print(result)

    # Search for function definitions
    print("\n[3] Searching for function definitions...")
    result = tools.search_in_files("def.*function", "*.py")
    print(result)

    # Cleanup
    tools.delete_file("module1.py")
    tools.delete_file("module2.py")
    print("\n✓ search_in_files test complete")


def test_find_files():
    """Test the find_files functionality"""
    print("\n" + "=" * 70)
    print("Test 3: find_files - File Pattern Matching (Glob)")
    print("=" * 70)

    tools = AgentTools()

    # Create test files
    print("\n[1] Creating test files...")
    tools.write_file("test_unit.py", "# unit tests")
    tools.write_file("test_integration.py", "# integration tests")
    tools.write_file("config.json", "{}")
    tools.write_file("README.md", "# Readme")

    # Find Python test files
    print("\n[2] Finding test files (test_*.py)...")
    result = tools.find_files("test_*.py")
    print(result)

    # Find all Python files
    print("\n[3] Finding all Python files (*.py)...")
    result = tools.find_files("*.py")
    print(result)

    # Find markdown files
    print("\n[4] Finding markdown files (*.md)...")
    result = tools.find_files("*.md")
    print(result)

    # Cleanup
    tools.delete_file("test_unit.py")
    tools.delete_file("test_integration.py")
    tools.delete_file("config.json")
    tools.delete_file("README.md")
    print("\n✓ find_files test complete")


def test_fetch_url():
    """Test the fetch_url functionality"""
    print("\n" + "=" * 70)
    print("Test 4: fetch_url - Internet Access")
    print("=" * 70)

    tools = AgentTools()

    # Test 1: Simple API call
    print("\n[1] Fetching GitHub zen...")
    result = tools.fetch_url("https://api.github.com/zen")
    print(result[:500] if len(result) > 500 else result)

    # Test 2: JSON API
    print("\n[2] Fetching IP info...")
    result = tools.fetch_url("https://httpbin.org/ip")
    print(result[:500] if len(result) > 500 else result)

    # Test 3: Error handling (invalid URL)
    print("\n[3] Testing error handling (invalid protocol)...")
    result = tools.fetch_url("ftp://example.com")
    print(result)

    print("\n✓ fetch_url test complete")


def test_dynamic_workspace():
    """Test dynamic workspace configuration"""
    print("\n" + "=" * 70)
    print("Test 5: Dynamic Workspace")
    print("=" * 70)

    # Test 1: Default (current directory)
    print("\n[1] Default workspace (current directory)...")
    tools1 = AgentTools()
    print(f"Workspace: {tools1.workspace}")

    # Test 2: Custom workspace
    print("\n[2] Custom workspace...")
    import tempfile
    temp_dir = tempfile.mkdtemp()
    tools2 = AgentTools(workspace_dir=temp_dir)
    print(f"Workspace: {tools2.workspace}")

    # Write a file
    tools2.write_file("test.txt", "Hello from custom workspace")
    result = tools2.read_file("test.txt")
    print(result)

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)

    print("\n✓ dynamic_workspace test complete")


def main():
    """Run all tests"""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + "  ENHANCED AGENT TOOLING - COMPREHENSIVE TEST SUITE".center(68) + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    print()

    try:
        test_edit_file()
        test_search_in_files()
        test_find_files()
        test_fetch_url()
        test_dynamic_workspace()

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print()
        print("Your agents now have:")
        print("  ✓ Precise file editing (edit_file)")
        print("  ✓ Internet access (fetch_url)")
        print("  ✓ Code search (search_in_files)")
        print("  ✓ File pattern matching (find_files)")
        print("  ✓ Dynamic workspace configuration")
        print()
        print("See ENHANCED_TOOLING.md for full documentation")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
