#!/usr/bin/env python3
"""
CI Matrix Generation Script
Generates test matrix for GitHub Actions.
"""

import json
import os
import sys


def main():
    # Get inputs
    test_types_str = os.environ.get("TEST_TYPES", '["unit", "integration", "performance"]')
    platforms_str = os.environ.get("PLATFORMS", '["ncp", "ncpgov"]')
    
    try:
        test_types = json.loads(test_types_str)
        platforms = json.loads(platforms_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        return 1
    
    # Python versions to test
    python_versions = ["3.11", "3.12"]
    
    # Generate matrix
    matrix = []
    for python_version in python_versions:
        for platform in platforms:
            for test_type in test_types:
                matrix.append({
                    "python-version": python_version,
                    "platform": platform,
                    "test-type": test_type,
                    "os": "ubuntu-latest"
                })
    
    # Output as compact JSON
    matrix_json = json.dumps({"include": matrix}, separators=(',', ':'))
    
    print(f"Generated matrix with {len(matrix)} jobs")
    print(f"Platforms: {platforms}")
    print(f"Test types: {test_types}")
    print(f"Python versions: {python_versions}")
    
    # Write to GitHub output if in CI
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"matrix={matrix_json}\n")
            f.write(f"test-types={json.dumps(test_types, separators=(',', ':'))}\n")
            f.write(f"platforms={json.dumps(platforms, separators=(',', ':'))}\n")
    else:
        # For local testing
        print(f"\nmatrix={matrix_json}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
