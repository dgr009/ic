#!/usr/bin/env python3
"""
CI Platform Detection Script
Detects which platforms to test based on commit messages and changed files.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def get_commit_message():
    """Get the latest commit message."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_changed_files(event_name, base_sha=None, head_sha=None):
    """Get list of changed files."""
    try:
        if event_name == "pull_request" and base_sha and head_sha:
            cmd = ["git", "diff", "--name-only", base_sha, head_sha]
        else:
            cmd = ["git", "diff", "--name-only", "HEAD~1", "HEAD"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        return []


def detect_platforms_from_commit(commit_msg, all_platforms):
    """Detect platforms from commit message tags."""
    detected = []
    
    # Check for [all] or [test-all] tag
    if re.search(r'\[(all|test-all)\]', commit_msg, re.IGNORECASE):
        return list(all_platforms)
    
    # Check for platform tags: [platform], (platform), or platform:
    for platform in all_platforms:
        pattern = rf'\[{platform}\]|\({platform}\)|{platform}:'
        if re.search(pattern, commit_msg, re.IGNORECASE):
            detected.append(platform)
    
    return detected


def detect_platforms_from_files(changed_files, all_platforms):
    """Detect platforms from changed files."""
    detected = set()
    
    for file_path in changed_files:
        for platform in all_platforms:
            if f"src/ic/platforms/{platform}/" in file_path or \
               f"tests/platforms/{platform}/" in file_path:
                detected.add(platform)
    
    return list(detected)


def filter_platforms_with_tests(platforms):
    """Filter platforms that have actual test files."""
    platforms_with_tests = []
    
    for platform in platforms:
        test_dir = Path(f"tests/platforms/{platform}")
        if test_dir.exists():
            # Check if there are any test files
            test_files = list(test_dir.rglob("test_*.py"))
            if test_files:
                platforms_with_tests.append(platform)
                print(f"✓ Platform {platform} has {len(test_files)} test files")
            else:
                print(f"⚠ Platform {platform} directory exists but has no test files")
        else:
            print(f"⚠ Platform {platform} has no test directory")
    
    return platforms_with_tests


def main():
    # All available platforms
    ALL_PLATFORMS = ["ncp", "ncpgov", "oci", "azure", "aws", "gcp", "ssh", "cf"]
    
    # Get environment variables
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    base_sha = os.environ.get("BASE_SHA", "")
    head_sha = os.environ.get("HEAD_SHA", "")
    
    # Get commit message
    commit_msg = os.environ.get("COMMIT_MSG", "") or get_commit_message()
    print(f"Commit message: {commit_msg}")
    
    # Detect platforms from commit message
    detected_platforms = detect_platforms_from_commit(commit_msg, ALL_PLATFORMS)
    
    if detected_platforms:
        print(f"✓ Found platforms from commit message: {detected_platforms}")
    else:
        # Detect from changed files
        print("No platform tags in commit message, checking changed files...")
        changed_files = get_changed_files(event_name, base_sha, head_sha)
        if changed_files:
            print(f"Changed files: {len(changed_files)} files")
            detected_platforms = detect_platforms_from_files(changed_files, ALL_PLATFORMS)
            if detected_platforms:
                print(f"✓ Found platforms from changed files: {detected_platforms}")
    
    # Use defaults if nothing detected
    if not detected_platforms:
        print("No platforms detected, using defaults: ncp, ncpgov")
        detected_platforms = ["ncp", "ncpgov"]
    
    # Filter platforms that have tests
    platforms_with_tests = filter_platforms_with_tests(detected_platforms)
    
    # Remove duplicates and sort
    platforms_with_tests = sorted(set(platforms_with_tests))
    
    # Output as JSON (compact, single line)
    platforms_json = json.dumps(platforms_with_tests, separators=(',', ':'))
    print(f"\nFinal platforms to test: {platforms_json}")
    
    # Write to GitHub output if in CI
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"platforms={platforms_json}\n")
            f.write(f"should-run-tests={'true' if platforms_with_tests else 'false'}\n")
    else:
        # For local testing
        print(f"platforms={platforms_json}")
        print(f"should-run-tests={'true' if platforms_with_tests else 'false'}")
    
    return 0 if platforms_with_tests else 1


if __name__ == "__main__":
    sys.exit(main())
