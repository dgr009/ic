#!/bin/bash
# Test CI platform detection logic locally

set -e

echo "🔍 Testing CI Platform Detection Logic"
echo "========================================"
echo ""

# All available platforms
ALL_PLATFORMS=("ncp" "ncpgov" "oci" "azure" "aws" "gcp" "ssh" "cf")

# Test function
test_detection() {
    local commit_msg="$1"
    local expected="$2"
    
    echo "Test: $commit_msg"
    echo "Expected: $expected"
    
    DETECTED_PLATFORMS=()
    
    # Check for platform tags in commit message
    for platform in "${ALL_PLATFORMS[@]}"; do
        if echo "$commit_msg" | grep -iE "\[${platform}\]|\(${platform}\)|${platform}:" > /dev/null; then
            DETECTED_PLATFORMS+=("$platform")
        fi
    done
    
    # Check for [all] tag
    if echo "$commit_msg" | grep -iE "\[all\]|\[test-all\]" > /dev/null; then
        DETECTED_PLATFORMS=("${ALL_PLATFORMS[@]}")
    fi
    
    # If no platforms detected, use defaults
    if [ ${#DETECTED_PLATFORMS[@]} -eq 0 ]; then
        DETECTED_PLATFORMS=("ncp" "ncpgov")
    fi
    
    # Remove duplicates
    UNIQUE_PLATFORMS=($(echo "${DETECTED_PLATFORMS[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))
    
    echo "Detected: ${UNIQUE_PLATFORMS[*]}"
    
    if [ "${UNIQUE_PLATFORMS[*]}" = "$expected" ]; then
        echo "✅ PASS"
    else
        echo "❌ FAIL"
    fi
    echo ""
}

# Run tests
echo "Test 1: Single platform tag"
test_detection "[ncp] Fix EC2 listing" "ncp"

echo "Test 2: Multiple platform tags"
test_detection "[ncp][oci] Update auth" "ncp oci"

echo "Test 3: All platforms tag"
test_detection "[all] Major refactor" "aws azure cf gcp ncp ncpgov oci ssh"

echo "Test 4: Platform in parentheses"
test_detection "(oci) Add compartment support" "oci"

echo "Test 5: Platform with colon"
test_detection "aws: Add S3 support" "aws"

echo "Test 6: No platform tag (should use defaults)"
test_detection "Fix typo in README" "ncp ncpgov"

echo "Test 7: Case insensitive"
test_detection "[NCP] Fix bug" "ncp"

echo "Test 8: Multiple platforms mixed format"
test_detection "[ncp] (oci) aws: Update all" "aws ncp oci"

echo ""
echo "🔍 Checking test directory structure"
echo "====================================="
echo ""

for platform in "${ALL_PLATFORMS[@]}"; do
    if [ -d "tests/platforms/$platform" ]; then
        test_count=$(find "tests/platforms/$platform" -name "test_*.py" -type f 2>/dev/null | wc -l)
        if [ "$test_count" -gt 0 ]; then
            echo "✅ $platform: $test_count test files"
        else
            echo "⚠️  $platform: directory exists but no test files"
        fi
    else
        echo "❌ $platform: no test directory"
    fi
done

echo ""
echo "🔍 Checking platform source directories"
echo "========================================"
echo ""

for platform in "${ALL_PLATFORMS[@]}"; do
    if [ -d "src/ic/platforms/$platform" ]; then
        service_count=$(find "src/ic/platforms/$platform" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
        echo "✅ $platform: $service_count services"
    else
        echo "❌ $platform: no source directory"
    fi
done

echo ""
echo "✅ Detection logic test complete!"
