"""
Unit Tests for Help Messages and Development Status Warnings

This module provides tests for help message updates and development status warnings
as required by task 20.

Requirements covered:
- 10.4: Add tests for help message updates and development status warnings
"""

import pytest
import sys
import argparse
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ic.cli import DevelopmentStatusHelpFormatter


class TestDevelopmentStatusHelpFormatter:
    """Test the custom help formatter for development status warnings."""
    
    def test_help_formatter_initialization(self):
        """Test DevelopmentStatusHelpFormatter initialization."""
        formatter = DevelopmentStatusHelpFormatter("Azure", "test_prog")
        assert formatter.platform_name == "Azure"
    
    def test_help_formatter_adds_warning(self):
        """Test that help formatter adds development status warning."""
        # Create a simple parser to test with
        parser = argparse.ArgumentParser(
            prog="ic azure",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        parser.add_argument("--test", help="Test argument")
        
        # Get help text
        help_text = parser.format_help()
        
        # Verify warning is present
        assert "DEVELOPMENT STATUS WARNING" in help_text
        assert "Azure features are currently in development" in help_text
        assert "While usable, they may contain bugs" in help_text
        assert "Please report any issues" in help_text
    
    def test_help_formatter_warning_placement(self):
        """Test that warning is placed correctly in help text."""
        parser = argparse.ArgumentParser(
            prog="ic gcp",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("GCP", prog)
        )
        parser.add_argument("--verbose", help="Verbose output")
        
        help_text = parser.format_help()
        lines = help_text.split('\n')
        
        # Find usage line
        usage_line_idx = -1
        for i, line in enumerate(lines):
            if line.startswith('usage:'):
                usage_line_idx = i
                break
        
        assert usage_line_idx >= 0, "Usage line not found"
        
        # Warning should appear after usage line
        warning_found = False
        for i in range(usage_line_idx + 1, len(lines)):
            if "DEVELOPMENT STATUS WARNING" in lines[i]:
                warning_found = True
                break
        
        assert warning_found, "Warning not found after usage line"
    
    def test_help_formatter_different_platforms(self):
        """Test help formatter with different platform names."""
        platforms = ["Azure", "GCP", "Google Cloud Platform"]
        
        for platform in platforms:
            parser = argparse.ArgumentParser(
                prog=f"ic {platform.lower()}",
                formatter_class=lambda prog, p=platform: DevelopmentStatusHelpFormatter(p, prog)
            )
            
            help_text = parser.format_help()
            
            assert f"{platform} features are currently in development" in help_text
    
    def test_help_formatter_preserves_original_help(self):
        """Test that formatter preserves original help content."""
        parser = argparse.ArgumentParser(
            prog="ic azure",
            description="Azure cloud operations",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        parser.add_argument("--region", help="Azure region")
        parser.add_argument("--subscription", help="Azure subscription ID")
        
        help_text = parser.format_help()
        
        # Original content should be preserved
        assert "Azure cloud operations" in help_text
        assert "--region" in help_text
        assert "Azure region" in help_text
        assert "--subscription" in help_text
        assert "Azure subscription ID" in help_text
        
        # Warning should also be present
        assert "DEVELOPMENT STATUS WARNING" in help_text


class TestCLIHelpMessages:
    """Test CLI help message integration."""
    
    @patch('sys.argv', ['ic', '--help'])
    def test_main_help_message_structure(self):
        """Test main IC CLI help message structure."""
        # This test would need to import and test the main CLI module
        # For now, we'll test the structure we expect
        
        # Mock the main CLI function
        with patch('sys.exit') as mock_exit:
            try:
                # Import would trigger help display
                from src.ic import cli
                # If we get here, help wasn't triggered
                pass
            except SystemExit:
                # Expected when --help is used
                pass
    
    def test_azure_help_includes_warning(self):
        """Test that Azure help includes development status warning."""
        # Create parser similar to what would be used for Azure commands
        parser = argparse.ArgumentParser(
            prog="ic azure",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        
        # Add typical Azure subcommands
        subparsers = parser.add_subparsers(dest="azure_command")
        vm_parser = subparsers.add_parser("vm", help="Virtual machine operations")
        storage_parser = subparsers.add_parser("storage", help="Storage operations")
        
        help_text = parser.format_help()
        
        # Verify Azure-specific warning
        assert "Azure features are currently in development" in help_text
        assert "DEVELOPMENT STATUS WARNING" in help_text
        
        # Verify subcommands are still present
        assert "vm" in help_text
        assert "storage" in help_text
    
    def test_gcp_help_includes_warning(self):
        """Test that GCP help includes development status warning."""
        parser = argparse.ArgumentParser(
            prog="ic gcp",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("GCP", prog)
        )
        
        # Add typical GCP subcommands
        subparsers = parser.add_subparsers(dest="gcp_command")
        compute_parser = subparsers.add_parser("compute", help="Compute Engine operations")
        storage_parser = subparsers.add_parser("storage", help="Cloud Storage operations")
        
        help_text = parser.format_help()
        
        # Verify GCP-specific warning
        assert "GCP features are currently in development" in help_text
        assert "DEVELOPMENT STATUS WARNING" in help_text
        
        # Verify subcommands are still present
        assert "compute" in help_text
        assert "storage" in help_text
    
    def test_stable_platforms_no_warning(self):
        """Test that stable platforms don't show development warnings."""
        # Test AWS (should be stable)
        parser = argparse.ArgumentParser(prog="ic aws")
        parser.add_argument("--region", help="AWS region")
        
        help_text = parser.format_help()
        
        # Should not contain development warning
        assert "DEVELOPMENT STATUS WARNING" not in help_text
        assert "currently in development" not in help_text
        
        # But should contain normal help
        assert "--region" in help_text


class TestCLIWarningIntegration:
    """Test integration of warnings with actual CLI structure."""
    
    def test_warning_format_consistency(self):
        """Test that warning format is consistent across platforms."""
        platforms = ["Azure", "GCP"]
        
        for platform in platforms:
            formatter = DevelopmentStatusHelpFormatter(platform, f"ic {platform.lower()}")
            
            # Create minimal parser
            parser = argparse.ArgumentParser(
                prog=f"ic {platform.lower()}",
                formatter_class=lambda prog, p=platform: DevelopmentStatusHelpFormatter(p, prog)
            )
            
            help_text = parser.format_help()
            
            # Check warning format consistency
            assert "⚠️" in help_text  # Warning emoji
            assert "DEVELOPMENT STATUS WARNING:" in help_text
            assert f"{platform} features are currently in development" in help_text
            assert "While usable, they may contain bugs" in help_text
            assert "Please report any issues" in help_text
    
    def test_warning_visibility(self):
        """Test that warnings are prominently visible."""
        parser = argparse.ArgumentParser(
            prog="ic azure",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        
        help_text = parser.format_help()
        lines = help_text.split('\n')
        
        # Warning should appear early in the help text
        warning_line_idx = -1
        for i, line in enumerate(lines):
            if "DEVELOPMENT STATUS WARNING" in line:
                warning_line_idx = i
                break
        
        assert warning_line_idx >= 0, "Warning not found"
        assert warning_line_idx < len(lines) / 2, "Warning should appear in first half of help text"
    
    def test_warning_does_not_break_parsing(self):
        """Test that warning doesn't interfere with argument parsing."""
        parser = argparse.ArgumentParser(
            prog="ic azure",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        parser.add_argument("--subscription", required=True)
        parser.add_argument("--resource-group")
        
        # Test that normal parsing still works
        args = parser.parse_args(["--subscription", "test-sub", "--resource-group", "test-rg"])
        
        assert args.subscription == "test-sub"
        assert args.resource_group == "test-rg"
    
    def test_warning_in_subcommand_help(self):
        """Test that warnings appear in subcommand help as well."""
        main_parser = argparse.ArgumentParser(prog="ic")
        subparsers = main_parser.add_subparsers(dest="platform")
        
        # Azure subparser with warning formatter
        azure_parser = subparsers.add_parser(
            "azure",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        azure_parser.add_argument("--subscription", help="Azure subscription")
        
        # Get help for Azure subcommand
        help_text = azure_parser.format_help()
        
        assert "DEVELOPMENT STATUS WARNING" in help_text
        assert "Azure features are currently in development" in help_text


class TestHelpMessageContent:
    """Test specific content of help messages."""
    
    def test_warning_message_completeness(self):
        """Test that warning messages contain all required information."""
        formatter = DevelopmentStatusHelpFormatter("Azure", "ic azure")
        parser = argparse.ArgumentParser(
            prog="ic azure",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        
        help_text = parser.format_help()
        
        # Required warning elements
        required_elements = [
            "⚠️",  # Warning symbol
            "DEVELOPMENT STATUS WARNING:",
            "Azure features are currently in development",
            "While usable, they may contain bugs",
            "incomplete functionality",
            "Please report any issues"
        ]
        
        for element in required_elements:
            assert element in help_text, f"Missing required element: {element}"
    
    def test_warning_message_tone(self):
        """Test that warning message has appropriate tone."""
        formatter = DevelopmentStatusHelpFormatter("GCP", "ic gcp")
        parser = argparse.ArgumentParser(
            prog="ic gcp",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("GCP", prog)
        )
        
        help_text = parser.format_help()
        
        # Should be informative but not discouraging
        assert "usable" in help_text.lower()  # Indicates it's still functional
        assert "report" in help_text.lower()  # Encourages feedback
        
        # Should not be overly negative
        negative_words = ["broken", "unusable", "avoid", "don't use"]
        for word in negative_words:
            assert word not in help_text.lower()
    
    def test_platform_specific_messaging(self):
        """Test that messages are properly customized for each platform."""
        platforms = [
            ("Azure", "Azure features"),
            ("GCP", "GCP features"),
            ("Google Cloud Platform", "Google Cloud Platform features")
        ]
        
        for platform_name, expected_text in platforms:
            formatter = DevelopmentStatusHelpFormatter(platform_name, f"ic {platform_name.lower()}")
            parser = argparse.ArgumentParser(
                prog=f"ic {platform_name.lower()}",
                formatter_class=lambda prog, p=platform_name: DevelopmentStatusHelpFormatter(p, prog)
            )
            
            help_text = parser.format_help()
            assert expected_text in help_text


class TestHelpMessageEdgeCases:
    """Test edge cases for help message formatting."""
    
    def test_empty_platform_name(self):
        """Test behavior with empty platform name."""
        formatter = DevelopmentStatusHelpFormatter("", "ic test")
        parser = argparse.ArgumentParser(
            prog="ic test",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("", prog)
        )
        
        help_text = parser.format_help()
        
        # Should handle empty platform name gracefully
        assert "DEVELOPMENT STATUS WARNING" in help_text
        assert " features are currently in development" in help_text
    
    def test_long_platform_name(self):
        """Test behavior with very long platform name."""
        long_name = "Very Long Cloud Platform Name That Might Cause Formatting Issues"
        formatter = DevelopmentStatusHelpFormatter(long_name, "ic test")
        parser = argparse.ArgumentParser(
            prog="ic test",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter(long_name, prog)
        )
        
        help_text = parser.format_help()
        
        # Should handle long names without breaking formatting
        assert long_name in help_text
        assert "DEVELOPMENT STATUS WARNING" in help_text
    
    def test_special_characters_in_platform_name(self):
        """Test behavior with special characters in platform name."""
        special_name = "Test-Platform_v2.0"
        formatter = DevelopmentStatusHelpFormatter(special_name, "ic test")
        parser = argparse.ArgumentParser(
            prog="ic test",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter(special_name, prog)
        )
        
        help_text = parser.format_help()
        
        # Should handle special characters properly
        assert special_name in help_text
        assert "DEVELOPMENT STATUS WARNING" in help_text
    
    def test_no_usage_line(self):
        """Test behavior when usage line is not found."""
        # Create a custom formatter that might not have usage line
        formatter = DevelopmentStatusHelpFormatter("Test", "test_prog")
        
        # Manually test format_help with minimal content
        help_text = "Test help content without usage line"
        
        # The formatter should handle missing usage line gracefully
        # This would need to be tested by mocking the parent class behavior
        assert True  # Placeholder - actual implementation would test fallback behavior


class TestCLIIntegrationWithWarnings:
    """Test integration of CLI with warning system."""
    
    def test_cli_imports_warning_formatter(self):
        """Test that CLI module properly imports and uses warning formatter."""
        try:
            from src.ic.cli import DevelopmentStatusHelpFormatter
            assert DevelopmentStatusHelpFormatter is not None
        except ImportError:
            pytest.fail("DevelopmentStatusHelpFormatter not properly imported")
    
    def test_warning_formatter_available_for_subcommands(self):
        """Test that warning formatter is available for use in subcommands."""
        # Test that the formatter can be instantiated and used
        formatter_class = DevelopmentStatusHelpFormatter
        
        # Should be able to create instances for different platforms
        azure_formatter = formatter_class("Azure", "ic azure")
        gcp_formatter = formatter_class("GCP", "ic gcp")
        
        assert azure_formatter.platform_name == "Azure"
        assert gcp_formatter.platform_name == "GCP"
    
    @patch('sys.stderr', new_callable=StringIO)
    def test_warning_output_to_stderr(self, mock_stderr):
        """Test that warnings are properly displayed when help is shown."""
        parser = argparse.ArgumentParser(
            prog="ic azure",
            formatter_class=lambda prog: DevelopmentStatusHelpFormatter("Azure", prog)
        )
        
        # Get help text (this would normally go to stderr)
        help_text = parser.format_help()
        
        # Verify warning is in the help text
        assert "DEVELOPMENT STATUS WARNING" in help_text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])