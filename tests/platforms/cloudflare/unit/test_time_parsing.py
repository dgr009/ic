"""Unit tests for CloudFlare traffic analytics time parsing.

Tests the parse_time_window() function to ensure it correctly parses
time window strings into timedelta objects.
"""

import pytest
from datetime import timedelta
from src.ic.platforms.cloudflare.traffic.info import parse_time_window


class TestParseTimeWindow:
    """Test suite for parse_time_window() function."""
    
    def test_parse_minutes_valid(self):
        """Test parsing valid minute formats."""
        assert parse_time_window("5m") == timedelta(minutes=5)
        assert parse_time_window("1m") == timedelta(minutes=1)
        assert parse_time_window("30m") == timedelta(minutes=30)
        assert parse_time_window("60m") == timedelta(minutes=60)
    
    def test_parse_hours_valid(self):
        """Test parsing valid hour formats."""
        assert parse_time_window("8h") == timedelta(hours=8)
        assert parse_time_window("1h") == timedelta(hours=1)
        assert parse_time_window("24h") == timedelta(hours=24)
        assert parse_time_window("48h") == timedelta(hours=48)
    
    def test_parse_days_valid(self):
        """Test parsing valid day formats."""
        assert parse_time_window("1d") == timedelta(days=1)
        assert parse_time_window("7d") == timedelta(days=7)
        assert parse_time_window("30d") == timedelta(days=30)
    
    def test_case_insensitive(self):
        """Test that parsing is case-insensitive."""
        assert parse_time_window("5M") == timedelta(minutes=5)
        assert parse_time_window("8H") == timedelta(hours=8)
        assert parse_time_window("1D") == timedelta(days=1)
        assert parse_time_window("5m") == parse_time_window("5M")
    
    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled."""
        assert parse_time_window(" 5m ") == timedelta(minutes=5)
        assert parse_time_window("  8h  ") == timedelta(hours=8)
        assert parse_time_window("\t1d\t") == timedelta(days=1)
    
    def test_edge_case_zero(self):
        """Test edge case with zero value."""
        assert parse_time_window("0m") == timedelta(minutes=0)
        assert parse_time_window("0h") == timedelta(hours=0)
        assert parse_time_window("0d") == timedelta(days=0)
    
    def test_edge_case_large_numbers(self):
        """Test edge cases with large numbers."""
        assert parse_time_window("999d") == timedelta(days=999)
        assert parse_time_window("1000h") == timedelta(hours=1000)
        assert parse_time_window("10000m") == timedelta(minutes=10000)
    
    def test_invalid_format_no_unit(self):
        """Test that missing unit raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("5")
        assert "Invalid time format" in str(exc_info.value)
        assert "5" in str(exc_info.value)
    
    def test_invalid_format_no_number(self):
        """Test that missing number raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("m")
        assert "Invalid time format" in str(exc_info.value)
    
    def test_invalid_format_wrong_unit(self):
        """Test that invalid unit raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("5s")  # seconds not supported
        assert "Invalid time format" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("5w")  # weeks not supported
        assert "Invalid time format" in str(exc_info.value)
    
    def test_invalid_format_multiple_units(self):
        """Test that multiple units raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("5m10h")
        assert "Invalid time format" in str(exc_info.value)
    
    def test_invalid_format_decimal(self):
        """Test that decimal numbers raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("5.5h")
        assert "Invalid time format" in str(exc_info.value)
    
    def test_invalid_format_negative(self):
        """Test that negative numbers raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("-5h")
        assert "Invalid time format" in str(exc_info.value)
    
    def test_invalid_format_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("")
        assert "Invalid time format" in str(exc_info.value)
    
    def test_invalid_format_spaces_in_middle(self):
        """Test that spaces in the middle raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("5 h")
        assert "Invalid time format" in str(exc_info.value)
    
    def test_error_message_includes_examples(self):
        """Test that error messages include helpful examples."""
        with pytest.raises(ValueError) as exc_info:
            parse_time_window("invalid")
        error_msg = str(exc_info.value)
        assert "5m" in error_msg or "8h" in error_msg or "1d" in error_msg
        assert "Examples:" in error_msg or "examples:" in error_msg.lower()
    
    def test_common_use_cases(self):
        """Test common real-world use cases."""
        # Default value from requirements
        assert parse_time_window("8h") == timedelta(hours=8)
        
        # Common monitoring windows
        assert parse_time_window("5m") == timedelta(minutes=5)
        assert parse_time_window("15m") == timedelta(minutes=15)
        assert parse_time_window("1h") == timedelta(hours=1)
        assert parse_time_window("24h") == timedelta(hours=24)
        assert parse_time_window("7d") == timedelta(days=7)


class TestMainFunction:
    """Test suite for main() function with time parsing."""
    
    def test_main_with_invalid_time(self):
        """Test main function with invalid time window."""
        from argparse import Namespace
        from src.ic.platforms.cloudflare.traffic.info import main
        
        args = Namespace(time="invalid", account=None, zone=None)
        result = main(args)
        
        assert result["success"] is False
        assert "error" in result
        assert "Invalid time format" in result["error"]
