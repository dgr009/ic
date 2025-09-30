#!/usr/bin/env python3
"""
Comprehensive CLI Command Testing Script

This script tests all platform CLI commands to verify:
1. Command discovery and routing work correctly
2. Argument parsing functions properly
3. Error handling is graceful
4. Help messages display correctly
"""

import subprocess
import sys
from typing import List, Dict, Tuple


def run_command(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def test_help_command(cmd: List[str]) -> bool:
    """Test if a help command works correctly."""
    exit_code, stdout, stderr = run_command(cmd + ["--help"])
    
    if exit_code != 0:
        print(f"  ❌ Help command failed: {' '.join(cmd)} --help")
        print(f"     Exit code: {exit_code}")
        if stderr:
            print(f"     Error: {stderr}")
        return False
    
    if "usage:" not in stdout:
        print(f"  ❌ Help output missing usage: {' '.join(cmd)} --help")
        return False
    
    print(f"  ✅ Help works: {' '.join(cmd)}")
    return True


def test_platform_discovery():
    """Test that all platforms are discoverable."""
    print("🔍 Testing Platform Discovery...")
    
    exit_code, stdout, stderr = run_command(["ic", "--help"])
    
    if exit_code != 0:
        print("  ❌ Main CLI help failed")
        return False
    
    expected_platforms = [
        "aws", "oci", "ncp", "ncpgov", "azure", "gcp", 
        "cloudflare", "ssh", "config", "security"
    ]
    
    missing_platforms = []
    for platform in expected_platforms:
        if platform not in stdout:
            missing_platforms.append(platform)
    
    if missing_platforms:
        print(f"  ❌ Missing platforms: {', '.join(missing_platforms)}")
        return False
    
    print("  ✅ All platforms discovered")
    return True


def test_platform_commands():
    """Test platform-specific commands."""
    print("\n🔍 Testing Platform Commands...")
    
    # Define test commands for each platform
    test_commands = {
        "aws": [
            ["ic", "aws", "--help"],
            ["ic", "aws", "ec2", "--help"],
            ["ic", "aws", "ec2", "info", "--help"],
            ["ic", "aws", "s3", "--help"],
            ["ic", "aws", "vpc", "--help"],
        ],
        "oci": [
            ["ic", "oci", "--help"],
            ["ic", "oci", "vm", "--help"],
            ["ic", "oci", "vm", "info", "--help"],
            ["ic", "oci", "vcn", "--help"],
        ],
        "ncp": [
            ["ic", "ncp", "--help"],
            ["ic", "ncp", "ec2", "--help"],
            ["ic", "ncp", "ec2", "info", "--help"],
            ["ic", "ncp", "vpc", "--help"],
        ],
        "ncpgov": [
            ["ic", "ncpgov", "--help"],
            ["ic", "ncpgov", "ec2", "--help"],
            ["ic", "ncpgov", "ec2", "info", "--help"],
        ],
        "azure": [
            ["ic", "azure", "--help"],
        ],
        "gcp": [
            ["ic", "gcp", "--help"],
            ["ic", "gcp", "compute", "--help"],
            ["ic", "gcp", "compute", "info", "--help"],
        ],
        "cloudflare": [
            ["ic", "cloudflare", "--help"],
            ["ic", "cloudflare", "dns", "--help"],
            ["ic", "cloudflare", "dns", "list_info", "--help"],
        ],
        "ssh": [
            ["ic", "ssh", "--help"],
            ["ic", "ssh", "server", "--help"],
            ["ic", "ssh", "server", "info", "--help"],
        ],
        "config": [
            ["ic", "config", "--help"],
            ["ic", "config", "init", "--help"],
            ["ic", "config", "validate", "--help"],
        ],
        "security": [
            ["ic", "security", "--help"],
            ["ic", "security", "scan", "--help"],
            ["ic", "security", "status", "--help"],
        ],
    }
    
    all_passed = True
    
    for platform, commands in test_commands.items():
        print(f"\n  Testing {platform.upper()} platform:")
        platform_passed = True
        
        for cmd in commands:
            if not test_help_command(cmd):
                platform_passed = False
                all_passed = False
        
        if platform_passed:
            print(f"  ✅ {platform.upper()} platform: All commands work")
        else:
            print(f"  ❌ {platform.upper()} platform: Some commands failed")
    
    return all_passed


def test_command_execution():
    """Test actual command execution (without credentials)."""
    print("\n🔍 Testing Command Execution...")
    
    # Test commands that should work without credentials or fail gracefully
    test_commands = [
        # AWS - should fail gracefully without credentials
        (["ic", "aws", "ec2", "info", "--regions", "us-east-1"], "AWS EC2 info"),
        
        # CloudFlare - should work with existing credentials or fail gracefully
        (["ic", "cloudflare", "dns", "list_info"], "CloudFlare DNS list"),
        
        # Config commands - should work
        (["ic", "config", "validate"], "Config validation"),
        (["ic", "security", "status"], "Security status"),
        
        # GCP - should work with MCP or fail gracefully
        (["ic", "gcp", "compute", "info", "--project", "test-project"], "GCP compute info"),
    ]
    
    all_passed = True
    
    for cmd, description in test_commands:
        print(f"  Testing: {description}")
        exit_code, stdout, stderr = run_command(cmd)
        
        # Commands can fail due to missing credentials, but should not crash
        if exit_code == -1:  # Timeout or exception
            print(f"    ❌ Command crashed or timed out: {' '.join(cmd)}")
            if stderr:
                print(f"       Error: {stderr}")
            all_passed = False
        else:
            print(f"    ✅ Command executed (exit code: {exit_code})")
    
    return all_passed


def test_error_handling():
    """Test error handling for invalid commands."""
    print("\n🔍 Testing Error Handling...")
    
    error_test_commands = [
        # Invalid platform
        (["ic", "invalid-platform"], "Invalid platform"),
        
        # Invalid service
        (["ic", "aws", "invalid-service"], "Invalid service"),
        
        # Invalid command
        (["ic", "aws", "ec2", "invalid-command"], "Invalid command"),
    ]
    
    all_passed = True
    
    for cmd, description in error_test_commands:
        print(f"  Testing: {description}")
        exit_code, stdout, stderr = run_command(cmd)
        
        # These should fail with non-zero exit code but not crash
        if exit_code == 0:
            print(f"    ❌ Command should have failed: {' '.join(cmd)}")
            all_passed = False
        elif exit_code == -1:
            print(f"    ❌ Command crashed: {' '.join(cmd)}")
            if stderr:
                print(f"       Error: {stderr}")
            all_passed = False
        else:
            print(f"    ✅ Command failed gracefully (exit code: {exit_code})")
    
    return all_passed


def main():
    """Run all CLI tests."""
    print("🚀 Starting Comprehensive CLI Command Testing\n")
    
    tests = [
        ("Platform Discovery", test_platform_discovery),
        ("Platform Commands", test_platform_commands),
        ("Command Execution", test_command_execution),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! CLI is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())