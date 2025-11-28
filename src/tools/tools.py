#!/usr/bin/env python3
"""
CLI Tools for MemGPT agents
Tools that agents can invoke to manipulate files, run commands, etc.
"""

import os
import re
import shlex
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional


class AgentTools:
    """Collection of tools agents can use"""

    def __init__(self, workspace_dir: Optional[str] = None):
        """Initialize tools with a sandboxed workspace directory

        Args:
            workspace_dir: Workspace path. If None, uses current working directory.
        """
        if workspace_dir is None:
            # Use current working directory
            workspace_dir = os.getcwd()

        self.workspace = Path(workspace_dir)
        self.workspace.mkdir(parents=True, exist_ok=True)
        print(f"[Tools] Workspace: {self.workspace}")

    def _safe_path(self, path: str) -> Path:
        """Ensure path is within workspace"""
        full_path = (self.workspace / path).resolve()
        if not str(full_path).startswith(str(self.workspace.resolve())):
            raise ValueError(f"Path outside workspace: {path}")
        return full_path

    # File Operations

    def read_file(self, path: str) -> str:
        """Read contents of a file

        Args:
            path: Path to file (relative to workspace)

        Returns:
            File contents as string
        """
        file_path = self._safe_path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"

        try:
            with open(file_path) as f:
                content = f.read()
            return f"✓ Read {len(content)} chars from {path}\n\n{content}"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file

        Args:
            path: Path to file (relative to workspace)
            content: Content to write

        Returns:
            Success message
        """
        file_path = self._safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, 'w') as f:
                f.write(content)
            return f"✓ Wrote {len(content)} chars to {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def append_file(self, path: str, content: str) -> str:
        """Append content to a file

        Args:
            path: Path to file (relative to workspace)
            content: Content to append

        Returns:
            Success message
        """
        file_path = self._safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, 'a') as f:
                f.write(content)
            return f"✓ Appended {len(content)} chars to {path}"
        except Exception as e:
            return f"Error appending to {path}: {e}"

    def list_files(self, path: str = ".") -> str:
        """List files in a directory

        Args:
            path: Directory path (relative to workspace)

        Returns:
            List of files and directories
        """
        dir_path = self._safe_path(path)
        if not dir_path.exists():
            return f"Error: Directory not found: {path}"

        try:
            items = sorted(dir_path.iterdir())
            lines = [f"Contents of {path}:"]
            for item in items:
                if item.is_dir():
                    lines.append(f"  📁 {item.name}/")
                else:
                    size = item.stat().st_size
                    lines.append(f"  📄 {item.name} ({size} bytes)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing {path}: {e}"

    def delete_file(self, path: str) -> str:
        """Delete a file

        Args:
            path: Path to file (relative to workspace)

        Returns:
            Success message
        """
        file_path = self._safe_path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"

        try:
            file_path.unlink()
            return f"✓ Deleted {path}"
        except Exception as e:
            return f"Error deleting {path}: {e}"

    def edit_file(self, path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
        """Edit a file by replacing text (like Claude Code's Edit tool)

        Args:
            path: Path to file (relative to workspace)
            old_string: Text to find and replace
            new_string: Replacement text
            replace_all: If True, replace all occurrences. If False, must be unique.

        Returns:
            Success message with line numbers
        """
        file_path = self._safe_path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"

        try:
            # Read file
            with open(file_path) as f:
                content = f.read()

            # Check if old_string exists
            count = content.count(old_string)
            if count == 0:
                return f"Error: String not found in {path}"

            if not replace_all and count > 1:
                return f"Error: String appears {count} times in {path}. Use replace_all=True to replace all occurrences."

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                msg = f"✓ Replaced {count} occurrence(s) in {path}"
            else:
                new_content = content.replace(old_string, new_string, 1)
                msg = f"✓ Replaced 1 occurrence in {path}"

            # Write back
            with open(file_path, 'w') as f:
                f.write(new_content)

            # Show context
            lines_changed = new_content[:new_content.find(new_string) + len(new_string)].count('\n') + 1
            return f"{msg} (around line {lines_changed})"

        except Exception as e:
            return f"Error editing {path}: {e}"

    def search_in_files(self, pattern: str, file_pattern: str = "*.py", max_results: int = 20) -> str:
        """Search for pattern in files (like grep)

        Args:
            pattern: Regular expression pattern to search for
            file_pattern: Glob pattern for files to search (e.g., "*.py", "*.txt")
            max_results: Maximum number of results to return

        Returns:
            Search results with file paths and line numbers
        """
        try:
            results = []
            # Find matching files
            for file_path in self.workspace.rglob(file_pattern):
                if not file_path.is_file():
                    continue

                try:
                    with open(file_path, encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                rel_path = file_path.relative_to(self.workspace)
                                results.append(f"{rel_path}:{line_num}: {line.rstrip()}")

                                if len(results) >= max_results:
                                    break
                except Exception:
                    # Skip files that can't be read
                    continue

                if len(results) >= max_results:
                    break

            if not results:
                return f"No matches found for pattern: {pattern}"

            header = f"Found {len(results)} matches (showing first {max_results}):\n"
            return header + "\n".join(results)

        except Exception as e:
            return f"Error searching: {e}"

    def find_files(self, pattern: str) -> str:
        """Find files by name pattern (like glob)

        Args:
            pattern: Glob pattern (e.g., "*.py", "test_*.txt", "**/*.md")

        Returns:
            List of matching file paths
        """
        try:
            matches = list(self.workspace.glob(pattern))
            # Also try rglob for recursive patterns
            if '**' in pattern:
                matches = list(self.workspace.rglob(pattern.replace('**/', '')))

            if not matches:
                return f"No files found matching: {pattern}"

            # Sort by modification time (most recent first)
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            lines = [f"Found {len(matches)} files matching '{pattern}':"]
            for match in matches[:50]:  # Limit to 50 results
                rel_path = match.relative_to(self.workspace)
                size = match.stat().st_size
                lines.append(f"  {rel_path} ({size} bytes)")

            if len(matches) > 50:
                lines.append(f"  ... and {len(matches) - 50} more")

            return "\n".join(lines)

        except Exception as e:
            return f"Error finding files: {e}"

    # Command Execution

    def run_command(self, command: str, timeout: int = 30) -> str:
        """Run a shell command from whitelist (restricted to workspace)

        Args:
            command: Shell command to run
            timeout: Timeout in seconds

        Returns:
            Command output

        Note:
            Shell features (pipes, redirects) are not supported for security.
            Use dedicated helpers for complex operations.
        """
        # Security: Only allow certain safe commands (whitelist)
        safe_commands = {'ls', 'cat', 'grep', 'find', 'wc', 'head', 'tail', 'tree', 'python3', 'pytest'}

        try:
            # Check for shell operators (additional security layer)
            dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>']
            for char in dangerous_chars:
                if char in command:
                    return f"✗ Error: Shell operators not allowed (found: '{char}')"

            # Parse command safely
            try:
                argv = shlex.split(command)
            except ValueError as e:
                return f"Error: Invalid command syntax: {e}"

            if not argv:
                return "Error: Empty command"

            executable = argv[0]

            # Validate executable is in whitelist
            if executable not in safe_commands:
                return f"Error: Command '{executable}' not allowed. Safe commands: {', '.join(sorted(safe_commands))}"

            # Execute command without shell (no injection possible)
            result = subprocess.run(
                argv,
                shell=False,
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = []
            if result.stdout:
                output.append("STDOUT:")
                output.append(result.stdout)
            if result.stderr:
                output.append("STDERR:")
                output.append(result.stderr)
            output.append(f"Exit code: {result.returncode}")

            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error running command: {e}"

    # Code Execution

    def run_python(self, code: str) -> str:
        """Run Python code in the workspace

        Args:
            code: Python code to execute

        Returns:
            Output from code execution
        """
        script_path = self.workspace / "_temp_script.py"

        try:
            # Write code to temp file
            with open(script_path, 'w') as f:
                f.write(code)

            # Run it
            result = subprocess.run(
                ['python3', str(script_path)],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = []
            if result.stdout:
                output.append("Output:")
                output.append(result.stdout)
            if result.stderr:
                output.append("Errors:")
                output.append(result.stderr)

            # Clean up
            script_path.unlink()

            return "\n".join(output) if output else "Code executed successfully (no output)"
        except Exception as e:
            return f"✗ Error executing Python: {e}"

    # Web Access

    def fetch_url(self, url: str, timeout: int = 30, max_size: int = 1024 * 1024) -> str:
        """Fetch content from a URL (HTTP/HTTPS only)

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            max_size: Maximum response size in bytes (default 1MB)

        Returns:
            URL content or error message

        Security:
            - Only HTTP/HTTPS protocols allowed
            - Size limited to prevent memory issues
            - Timeout to prevent hanging
            - No authentication (public URLs only)
        """
        try:
            # Validate URL
            if not url.startswith(('http://', 'https://')):
                return f"✗ Error: File/FTP URLs not allowed, only HTTP/HTTPS. Got: {url[:50]}"

            # Create request
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'MemGPT-Agent/1.0'}
            )

            # Fetch content
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # Check content length
                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > max_size:
                    return f"✗ Error: Content too large ({content_length} bytes, max {max_size})"

                # Read with size limit
                content = response.read(max_size)

                # Decode
                encoding = response.headers.get_content_charset('utf-8')
                text = content.decode(encoding, errors='ignore')

                # Truncate if needed
                if len(text) > 10000:
                    text = text[:10000] + f"\n\n[... truncated, total size: {len(content)} bytes]"

                return f"✓ Fetched {url}\n\nContent:\n{text}"

        except urllib.error.HTTPError as e:
            return f"HTTP Error {e.code}: {e.reason} for URL: {url}"
        except urllib.error.URLError as e:
            return f"URL Error: {e.reason} for URL: {url}"
        except Exception as e:
            return f"Error fetching URL: {e}"

    # Information

    def get_workspace_info(self) -> str:
        """Get information about the workspace

        Returns:
            Workspace statistics
        """
        total_files = sum(1 for _ in self.workspace.rglob('*') if _.is_file())
        total_dirs = sum(1 for _ in self.workspace.rglob('*') if _.is_dir())
        total_size = sum(f.stat().st_size for f in self.workspace.rglob('*') if f.is_file())

        return f"""Workspace: {self.workspace}
Files: {total_files}
Directories: {total_dirs}
Total size: {total_size:,} bytes ({total_size / 1024:.1f} KB)
"""


# Function schemas for the agent
TOOL_SCHEMAS = [
    {
        "name": "read_file",
        "description": "Read contents of a file in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file (relative to workspace)",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file (relative to workspace)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "append_file",
        "description": "Append content to a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "content": {"type": "string", "description": "Content to append"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (default: current directory)",
                }
            },
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file to delete"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_python",
        "description": "Execute Python code in the workspace",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a safe shell command (ls, cat, grep, find, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run"}
            },
            "required": ["command"],
        },
    },
    {
        "name": "get_workspace_info",
        "description": "Get statistics about the workspace",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "edit_file",
        "description": "Edit a file by finding and replacing text (precise modifications without rewriting entire file)",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file to edit"},
                "old_string": {"type": "string", "description": "Exact text to find and replace"},
                "new_string": {"type": "string", "description": "Replacement text"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences (default: False)"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "search_in_files",
        "description": "Search for pattern in files using regex (like grep)",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regular expression pattern to search"},
                "file_pattern": {"type": "string", "description": "Glob pattern for files (e.g., '*.py', '*.txt')"},
                "max_results": {"type": "integer", "description": "Maximum results to return (default: 20)"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "find_files",
        "description": "Find files by name pattern (like glob)",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g., '*.py', 'test_*.txt', '**/*.md')"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch content from a URL (HTTP/HTTPS, read-only access to public internet)",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch (must start with http:// or https://)"},
                "timeout": {"type": "integer", "description": "Request timeout in seconds (default: 30)"},
            },
            "required": ["url"],
        },
    },
]


if __name__ == "__main__":
    # Test the tools
    print("Testing AgentTools...")
    tools = AgentTools()

    # Test file operations
    print("\n1. Write file:")
    print(tools.write_file("test.txt", "Hello from agent tools!"))

    print("\n2. Read file:")
    print(tools.read_file("test.txt"))

    print("\n3. List files:")
    print(tools.list_files("."))

    print("\n4. Append to file:")
    print(tools.append_file("test.txt", "\nAppended line!"))
    print(tools.read_file("test.txt"))

    print("\n5. Run Python:")
    code = """
print("Hello from Python!")
result = 2 + 2
print(f"2 + 2 = {result}")
"""
    print(tools.run_python(code))

    print("\n6. Workspace info:")
    print(tools.get_workspace_info())

    print("\n7. Delete file:")
    print(tools.delete_file("test.txt"))
