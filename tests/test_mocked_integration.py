#!/usr/bin/env python3
"""
Mocked integration tests for Beyond Compare MCP Server.

These tests use mocking to ensure reliable testing without requiring
Beyond Compare to be installed, which is critical for Gold Standard CI/CD.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Legacy suite (expects compare_files on server class and mcp.tools map); "
    "refresh against FastMCP 3.2 + tests/test_gateway.py."
)

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from beyondcompare_mcp.exceptions import BeyondCompareCommandError, BeyondCompareNotInstalledError
from beyondcompare_mcp.server import BeyondCompareMCP


class TestBeyondCompareMocked(unittest.TestCase):
    """Mocked integration tests for reliable CI/CD."""

    def setUp(self):
        """Set up test environment with mocked Beyond Compare."""
        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="bc_mcp_mocked_"))

        # Create test files
        self.file1 = self.test_dir / "file1.txt"
        self.file2 = self.test_dir / "file2.txt"
        self.file1.write_text("Content 1\nLine 2\n")
        self.file2.write_text("Content 2\nLine 2\n")

        # Mock Beyond Compare executable path
        self.mock_bc_path = "/mock/path/to/BCompare.exe"

    def tearDown(self):
        """Clean up test files."""
        import shutil

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_compare_files_identical_mocked(self, mock_run_bc, mock_find_bc):
        """Test comparing identical files with mocking."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {
            "returncode": 0,  # BC returns 0 for identical files
            "stdout": "Files are identical",
            "stderr": "",
        }

        # Create server and test
        server = BeyondCompareMCP()

        # Access the tool function directly from the registered tools
        compare_files_tool = None
        for tool_name, tool_func in server.mcp.tools.items():
            if tool_name == "compare_files":
                compare_files_tool = tool_func
                break

        self.assertIsNotNone(compare_files_tool, "compare_files tool not found")

        result = compare_files_tool(
            left_path=str(self.file1),
            right_path=str(self.file1),  # Same file = identical
        )

        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["comparison_result"], "identical")
        mock_run_bc.assert_called_once()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_compare_files_different_mocked(self, mock_run_bc, mock_find_bc):
        """Test comparing different files with mocking."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {
            "returncode": 1,  # BC returns 1 for different files
            "stdout": "Files are different",
            "stderr": "",
        }

        # Create server and test
        server = BeyondCompareMCP()
        result = server.compare_files(left_path=str(self.file1), right_path=str(self.file2))

        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["comparison_result"], "different")
        mock_run_bc.assert_called_once()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_compare_files_with_report_mocked(self, mock_run_bc, mock_find_bc):
        """Test comparing files with report generation."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 1, "stdout": "Report generated", "stderr": ""}

        # Create server and test
        server = BeyondCompareMCP()
        report_path = str(self.test_dir / "report.html")

        result = server.compare_files(left_path=str(self.file1), right_path=str(self.file2), output_report=report_path)

        # Verify results
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["report_path"], report_path)
        mock_run_bc.assert_called_once()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_compare_folders_mocked(self, mock_run_bc, mock_find_bc):
        """Test comparing folders with mocking."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 0, "stdout": "Folder comparison complete", "stderr": ""}

        # Create test directories
        dir1 = self.test_dir / "dir1"
        dir2 = self.test_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create server and test
        server = BeyondCompareMCP()
        result = server.compare_folders(left_path=str(dir1), right_path=str(dir2))

        # Verify results
        self.assertTrue(result["success"])
        mock_run_bc.assert_called_once()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_sync_folders_mocked(self, mock_run_bc, mock_find_bc):
        """Test folder synchronization with mocking."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 0, "stdout": "Sync complete", "stderr": ""}

        # Create test directories
        source_dir = self.test_dir / "source"
        target_dir = self.test_dir / "target"
        source_dir.mkdir()
        target_dir.mkdir()

        # Create server and test
        server = BeyondCompareMCP()
        result = server.sync_folders(source_path=str(source_dir), target_path=str(target_dir), dry_run=True)

        # Verify results
        self.assertTrue(result["success"])
        mock_run_bc.assert_called_once()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_path_with_spaces_mocked(self, mock_run_bc, mock_find_bc):
        """Test handling paths with spaces."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 0, "stdout": "Files compared successfully", "stderr": ""}

        # Create files with spaces in path
        space_dir = self.test_dir / "directory with spaces"
        space_dir.mkdir()
        file_with_spaces = space_dir / "file with spaces.txt"
        file_with_spaces.write_text("Content with spaces")

        # Create server and test
        server = BeyondCompareMCP()
        result = server.compare_files(left_path=str(file_with_spaces), right_path=str(file_with_spaces))

        # Verify results
        self.assertTrue(result["success"])
        mock_run_bc.assert_called_once()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_unicode_content_mocked(self, mock_run_bc, mock_find_bc):
        """Test handling Unicode content."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 1, "stdout": "Unicode files compared", "stderr": ""}

        # Create files with Unicode content
        unicode_file1 = self.test_dir / "unicode1.txt"
        unicode_file2 = self.test_dir / "unicode2.txt"
        unicode_file1.write_text("Content with émojis 🚀 and ñoñó", encoding="utf-8")
        unicode_file2.write_text("Different émojis 🎯 and ñañá", encoding="utf-8")

        # Create server and test
        server = BeyondCompareMCP()
        result = server.compare_files(left_path=str(unicode_file1), right_path=str(unicode_file2))

        # Verify results
        self.assertTrue(result["success"])
        mock_run_bc.assert_called_once()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_error_handling_mocked(self, mock_run_bc, mock_find_bc):
        """Test error handling with mocking."""
        # Setup mocks for error scenario
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.side_effect = BeyondCompareCommandError("Mocked error")

        # Create server and test
        server = BeyondCompareMCP()
        result = server.compare_files(left_path=str(self.file1), right_path=str(self.file2))

        # Verify error handling
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    def test_multimedia_tools_mocked(self, mock_find_bc):
        """Test multimedia scanning tools with mocking."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)

        # Create server and test multimedia tools
        server = BeyondCompareMCP()

        # Test detect_usb_drives
        with patch("psutil.disk_partitions") as mock_partitions:
            mock_partitions.return_value = [
                MagicMock(device="E:", mountpoint="E:\\", fstype="NTFS"),
                MagicMock(device="F:", mountpoint="F:\\", fstype="NTFS"),
            ]

            result = server.detect_usb_drives()
            self.assertTrue(result["success"])
            self.assertIn("drives", result["data"])

    def test_server_initialization_mocked(self):
        """Test server initialization with mocked BC path."""
        with patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable") as mock_find_bc:
            mock_find_bc.return_value = Path(self.mock_bc_path)

            # Test successful initialization
            server = BeyondCompareMCP()
            self.assertIsNotNone(server)
            self.assertEqual(str(server.bc_path), self.mock_bc_path)

    def test_bc_not_found_error_mocked(self):
        """Test Beyond Compare not found error."""
        with patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable") as mock_find_bc:
            mock_find_bc.side_effect = BeyondCompareNotInstalledError("Mocked: BC not found")

            # Test error handling
            with self.assertRaises(BeyondCompareNotInstalledError):
                BeyondCompareMCP()


class TestBeyondCompareTools(unittest.TestCase):
    """Test individual tool functions with comprehensive mocking."""

    def setUp(self):
        """Set up mocked server for tool testing."""
        self.patcher = patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
        self.mock_find_bc = self.patcher.start()
        self.mock_find_bc.return_value = Path("/mock/BCompare.exe")

        self.server = BeyondCompareMCP()

    def tearDown(self):
        """Clean up patches."""
        self.patcher.stop()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_all_comparison_results_mocked(self, mock_run_bc):
        """Test all possible comparison results."""
        test_cases = [
            (0, "identical"),
            (1, "different"),
            (2, "binary_different"),
            (11, "left_newer"),
            (12, "right_newer"),
            (13, "left_missing"),
            (14, "right_missing"),
        ]

        for return_code, expected_result in test_cases:
            with self.subTest(return_code=return_code):
                mock_run_bc.return_value = {
                    "returncode": return_code,
                    "stdout": f"Test result: {expected_result}",
                    "stderr": "",
                }

                result = self.server.compare_files(left_path="/mock/file1.txt", right_path="/mock/file2.txt")

                self.assertTrue(result["success"])
                self.assertEqual(result["data"]["comparison_result"], expected_result)


if __name__ == "__main__":
    unittest.main()
