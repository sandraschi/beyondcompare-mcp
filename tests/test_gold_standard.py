#!/usr/bin/env python3
"""
Simple mocked tests for Beyond Compare MCP Server - Gold Standard.

These tests use direct method calls to test the core functionality
without complex MCP tool registration testing.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Legacy suite (pre-unified-gateway); see tests/test_gateway.py for current coverage."
)

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from beyondcompare_mcp.exceptions import BeyondCompareCommandError, BeyondCompareNotInstalledError
from beyondcompare_mcp.server import BeyondCompareMCP


class TestBeyondCompareGoldStandard(unittest.TestCase):
    """Gold Standard tests with proper mocking for CI/CD."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp(prefix="bc_gold_test_"))
        self.mock_bc_path = "/mock/BCompare.exe"

    def tearDown(self):
        """Clean up test files."""
        import shutil

        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    def test_server_initialization_success(self, mock_find_bc):
        """Test successful server initialization."""
        mock_find_bc.return_value = Path(self.mock_bc_path)

        server = BeyondCompareMCP()
        self.assertIsNotNone(server)
        self.assertIsNotNone(server.bc_path)
        self.assertIsNotNone(server.mcp)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    def test_server_initialization_failure(self, mock_find_bc):
        """Test server initialization failure."""
        mock_find_bc.side_effect = BeyondCompareNotInstalledError("BC not found")

        with self.assertRaises(BeyondCompareNotInstalledError):
            BeyondCompareMCP()

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_compare_files_core_logic(self, mock_run_bc, mock_find_bc):
        """Test the core file comparison logic."""
        # Setup mocks
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 0, "stdout": "Files are identical", "stderr": ""}

        # Test the internal method directly
        server = BeyondCompareMCP()
        result = server._compare_files("/path/file1.txt", "/path/file2.txt")

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["comparison_result"], "identical")

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_compare_folders_core_logic(self, mock_run_bc, mock_find_bc):
        """Test the core folder comparison logic."""
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 1, "stdout": "Folders are different", "stderr": ""}

        server = BeyondCompareMCP()
        result = server._compare_folders("/path/dir1", "/path/dir2")

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["comparison_result"], "different")

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_sync_folders_core_logic(self, mock_run_bc, mock_find_bc):
        """Test the core folder sync logic."""
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.return_value = {"returncode": 0, "stdout": "Sync complete", "stderr": ""}

        server = BeyondCompareMCP()
        result = server._sync_folders("/source", "/target", dry_run=True)

        self.assertTrue(result["success"])

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_error_handling(self, mock_run_bc, mock_find_bc):
        """Test error handling in operations."""
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_run_bc.side_effect = BeyondCompareCommandError("Command failed", 1)

        server = BeyondCompareMCP()
        result = server._compare_files("/path/file1.txt", "/path/file2.txt")

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    def test_all_tools_registered(self, mock_find_bc):
        """Test that all 6 tools are properly registered."""
        mock_find_bc.return_value = Path(self.mock_bc_path)

        server = BeyondCompareMCP()
        expected_tools = {
            "compare_files",
            "compare_folders",
            "sync_folders",
            "multimedia_drive_scanner",
            "find_multimedia_duplicates",
            "detect_usb_drives",
        }

        registered_tools = set(server.mcp.tools.keys())
        self.assertEqual(expected_tools, registered_tools)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("psutil.disk_partitions")
    def test_usb_detection_logic(self, mock_partitions, mock_find_bc):
        """Test USB drive detection logic."""
        mock_find_bc.return_value = Path(self.mock_bc_path)
        mock_partitions.return_value = [
            MagicMock(device="E:", mountpoint="E:\\", fstype="NTFS"),
            MagicMock(device="F:", mountpoint="F:\\", fstype="FAT32"),
        ]

        server = BeyondCompareMCP()
        result = server._detect_usb_drives()

        self.assertTrue(result["success"])
        self.assertIn("drives", result["data"])

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    def test_multimedia_scanner_initialization(self, mock_find_bc):
        """Test multimedia scanner initialization."""
        mock_find_bc.return_value = Path(self.mock_bc_path)

        server = BeyondCompareMCP()
        self.assertIsNotNone(server.multimedia_scanner)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    @patch("beyondcompare_mcp.server.BeyondCompareMCP._run_bc_command")
    def test_comparison_result_mapping(self, mock_run_bc, mock_find_bc):
        """Test all Beyond Compare return code mappings."""
        mock_find_bc.return_value = Path(self.mock_bc_path)

        test_cases = [
            (0, "identical"),
            (1, "different"),
            (2, "binary_different"),
            (11, "left_newer"),
            (12, "right_newer"),
            (13, "left_missing"),
            (14, "right_missing"),
        ]

        server = BeyondCompareMCP()

        for return_code, expected_result in test_cases:
            with self.subTest(return_code=return_code):
                mock_run_bc.return_value = {
                    "returncode": return_code,
                    "stdout": f"Test: {expected_result}",
                    "stderr": "",
                }

                result = server._compare_files("/file1.txt", "/file2.txt")
                self.assertTrue(result["success"])
                self.assertEqual(result["data"]["comparison_result"], expected_result)

    @patch("beyondcompare_mcp.server.BeyondCompareMCP._find_bc_executable")
    def test_path_validation(self, mock_find_bc):
        """Test path validation and sanitization."""
        mock_find_bc.return_value = Path(self.mock_bc_path)

        server = BeyondCompareMCP()

        # Test path sanitization
        test_paths = ["/normal/path.txt", "C:\\Windows\\path with spaces\\file.txt", "/path/with/unicode/émojis🚀.txt"]

        for path in test_paths:
            with self.subTest(path=path):
                sanitized = server._sanitize_path(path)
                self.assertIsInstance(sanitized, str)
                self.assertTrue(len(sanitized) > 0)


class TestBeyondCompareConfiguration(unittest.TestCase):
    """Test configuration and environment handling."""

    @patch.dict(os.environ, {"BEYOND_COMPARE_PATH": "/custom/bc/path"})
    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        from beyondcompare_mcp.config import create_settings

        settings = create_settings()
        self.assertEqual(settings.BEYOND_COMPARE_PATH, "/custom/bc/path")

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_log_level_configuration(self):
        """Test log level configuration."""
        from beyondcompare_mcp.config import create_settings

        settings = create_settings()
        self.assertEqual(settings.LOG_LEVEL, "DEBUG")

    def test_default_configuration(self):
        """Test default configuration values."""
        from beyondcompare_mcp.config import create_settings

        with patch.dict(os.environ, {}, clear=True):
            settings = create_settings()
            self.assertIsNone(settings.BEYOND_COMPARE_PATH)  # Should be None for auto-detection
            self.assertEqual(settings.LOG_LEVEL, "INFO")


if __name__ == "__main__":
    unittest.main()
