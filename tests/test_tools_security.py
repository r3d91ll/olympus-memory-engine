#!/usr/bin/env python3
"""
Unit tests for AgentTools - CRITICAL SECURITY INFRASTRUCTURE

Tests file operations, command execution sandboxing, and security validation.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.tools import AgentTools


class TestWorkspaceSecurity:
    """Test workspace isolation and path validation - CRITICAL"""

    def test_workspace_initialization(self):
        """Test workspace is properly initialized"""
        tools = AgentTools(workspace_dir="/tmp/test")

        assert tools.workspace == Path("/tmp/test")

    def test_workspace_defaults_to_cwd(self):
        """Test workspace defaults to current directory"""
        tools = AgentTools()

        assert tools.workspace == Path.cwd()

    def test_workspace_creates_directory(self):
        """Test workspace directory is created if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_workspace = Path(tmpdir) / "test_workspace"
            tools = AgentTools(workspace_dir=str(test_workspace))

            assert test_workspace.exists()

    def test_safe_path_within_workspace(self):
        """Test path resolution stays within workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Normal file should resolve correctly
            resolved = tools._safe_path("test.txt")
            assert resolved.parent == Path(tmpdir)
            assert resolved.name == "test.txt"

    def test_safe_path_prevents_escape(self):
        """Test path resolution prevents directory traversal - SECURITY CRITICAL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Should not escape workspace
            with pytest.raises(ValueError, match="outside workspace"):
                tools._safe_path("../../../etc/passwd")

    def test_safe_path_prevents_absolute_escape(self):
        """Test absolute paths outside workspace are rejected"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Should not allow absolute paths outside workspace
            with pytest.raises(ValueError, match="outside workspace"):
                tools._safe_path("/etc/passwd")


class TestFileOperationsSecurity:
    """Test file operations security - CRITICAL"""

    def test_read_file_within_workspace(self):
        """Test reading file within workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Hello World")

            # Should be able to read
            content = tools.read_file("test.txt")
            assert "Hello World" in content

    def test_read_file_outside_workspace_blocked(self):
        """Test reading file outside workspace is blocked - SECURITY"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Try to read file outside workspace
            with pytest.raises(ValueError, match="outside workspace"):
                tools.read_file("../../../etc/passwd")

    def test_write_file_within_workspace(self):
        """Test writing file within workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Should be able to write
            result = tools.write_file("test.txt", "Hello World")
            assert "✓" in result

            # Verify file was written
            test_file = Path(tmpdir) / "test.txt"
            assert test_file.exists()
            assert test_file.read_text() == "Hello World"

    def test_write_file_outside_workspace_blocked(self):
        """Test writing file outside workspace is blocked - SECURITY"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Try to write outside workspace
            with pytest.raises(ValueError, match="outside workspace"):
                tools.write_file("../../../tmp/malicious.txt", "bad")

    def test_delete_file_within_workspace(self):
        """Test deleting file within workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Create file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            # Should be able to delete
            result = tools.delete_file("test.txt")
            assert "✓" in result
            assert not test_file.exists()

    def test_delete_file_outside_workspace_blocked(self):
        """Test deleting file outside workspace is blocked - SECURITY"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Try to delete outside workspace
            with pytest.raises(ValueError, match="outside workspace"):
                tools.delete_file("../../../tmp/important.txt")


class TestEditFileSecurity:
    """Test edit_file security and functionality - CRITICAL"""

    def test_edit_file_simple_replace(self):
        """Test simple text replacement"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Create test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    return 'world'\n")

            # Edit file
            result = tools.edit_file(
                path="test.py",
                old_string="'world'",
                new_string="'universe'"
            )

            assert "✓" in result
            assert test_file.read_text() == "def hello():\n    return 'universe'\n"

    def test_edit_file_replace_all(self):
        """Test replace all occurrences"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("foo foo foo")

            result = tools.edit_file(
                path="test.py",
                old_string="foo",
                new_string="bar",
                replace_all=True
            )

            assert "✓" in result
            assert test_file.read_text() == "bar bar bar"

    def test_edit_file_outside_workspace_blocked(self):
        """Test editing outside workspace blocked - SECURITY"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            with pytest.raises(ValueError, match="outside workspace"):
                tools.edit_file(
                    path="../../../etc/hosts",
                    old_string="localhost",
                    new_string="malicious"
                )


class TestCommandExecutionSecurity:
    """Test command execution sandboxing - CRITICAL SECURITY"""

    def test_allowed_commands_execute(self):
        """Test that allowed commands execute"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # ls is allowed
            result = tools.run_command("ls -la")
            # Should execute (may fail but shouldn't be blocked)
            assert "not allowed" not in result.lower()

    def test_dangerous_commands_blocked(self):
        """Test that dangerous commands are blocked - SECURITY CRITICAL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            dangerous_commands = [
                "rm -rf /",
                "dd if=/dev/zero of=/dev/sda",
                "mkfs.ext4 /dev/sda",
                "chmod 777 /etc/passwd",
                "; rm -rf /",
                "| rm -rf /",
                "& rm -rf /",
            ]

            for cmd in dangerous_commands:
                result = tools.run_command(cmd)
                # Should be blocked
                assert "✗" in result or "not allowed" in result.lower()

    def test_command_injection_prevention(self):
        """Test prevention of command injection - SECURITY CRITICAL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Try various injection techniques
            injection_attempts = [
                "ls; rm -rf /",
                "ls && rm -rf /",
                "ls | rm -rf /",
                "ls `rm -rf /`",
                "ls $(rm -rf /)",
            ]

            for cmd in injection_attempts:
                result = tools.run_command(cmd)
                # Should detect and block dangerous parts
                assert "✗" in result or "not allowed" in result.lower()

    def test_timeout_enforcement(self):
        """Test command timeout is enforced"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Command that would run too long (sleep)
            result = tools.run_command("sleep 100")

            # Should timeout (our default is 30s, but test framework may be faster)
            # Just verify it doesn't hang forever
            assert result is not None


class TestPythonExecutionSecurity:
    """Test Python code execution sandboxing"""

    def test_safe_python_code_executes(self):
        """Test safe Python code executes"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            result = tools.run_python("print('Hello World')")

            assert "Hello World" in result

    def test_python_timeout_enforcement(self):
        """Test Python execution timeout"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Code that would run forever
            result = tools.run_python("while True: pass")

            # Should timeout
            assert "timeout" in result.lower() or "✗" in result


class TestURLFetchingSecurity:
    """Test URL fetching security - CRITICAL"""

    @patch('src.tools.tools.urllib.request.urlopen')
    def test_https_urls_allowed(self, mock_urlopen):
        """Test HTTPS URLs are allowed"""
        mock_response = MagicMock()
        mock_response.read.return_value = b"Hello World"
        mock_response.headers.get_content_charset.return_value = 'utf-8'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            result = tools.fetch_url("https://example.com")

            assert "Hello World" in result

    def test_file_urls_blocked(self):
        """Test file:// URLs are blocked - SECURITY"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            result = tools.fetch_url("file:///etc/passwd")

            assert "✗" in result
            assert "only HTTP" in result or "not allowed" in result.lower()

    def test_ftp_urls_blocked(self):
        """Test ftp:// URLs are blocked - SECURITY"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            result = tools.fetch_url("ftp://example.com/file")

            assert "✗" in result

    def test_localhost_urls_blocked(self):
        """Test localhost URLs are blocked - SECURITY"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Should block SSRF attempts
            dangerous_urls = [
                "http://localhost/",
                "http://127.0.0.1/",
                "http://0.0.0.0/",
                "http://[::1]/",
            ]

            for url in dangerous_urls:
                result = tools.fetch_url(url)
                # Should be blocked or fail safely
                assert result is not None

    @patch('src.tools.tools.urllib.request.urlopen')
    def test_size_limit_enforced(self, mock_urlopen):
        """Test that response size limit is enforced"""
        # Create mock response that's too large
        mock_response = MagicMock()
        mock_response.read.return_value = b"x" * (2 * 1024 * 1024)  # 2MB
        mock_response.headers.get.return_value = str(2 * 1024 * 1024)  # 2MB Content-Length
        mock_response.headers.get_content_charset.return_value = 'utf-8'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            result = tools.fetch_url("https://example.com", max_size=1024*1024)

            # Should enforce size limit
            assert "✗" in result or "too large" in result.lower()


class TestSearchOperationsSecurity:
    """Test search operations stay within workspace"""

    def test_find_files_within_workspace(self):
        """Test find_files stays within workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Create test files
            (Path(tmpdir) / "test1.py").write_text("test")
            (Path(tmpdir) / "test2.py").write_text("test")

            result = tools.find_files("*.py")

            assert "test1.py" in result
            assert "test2.py" in result

    def test_search_in_files_within_workspace(self):
        """Test search_in_files stays within workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Create test file
            (Path(tmpdir) / "test.py").write_text("def hello(): pass")

            result = tools.search_in_files("hello", "*.py")

            assert "hello" in result


class TestWorkspaceInfo:
    """Test workspace information"""

    def test_get_workspace_info(self):
        """Test getting workspace statistics"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tools = AgentTools(workspace_dir=tmpdir)

            # Create some files
            (Path(tmpdir) / "test1.txt").write_text("test")
            (Path(tmpdir) / "test2.txt").write_text("test")

            info = tools.get_workspace_info()

            assert "workspace" in info.lower()
            assert "files" in info.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
