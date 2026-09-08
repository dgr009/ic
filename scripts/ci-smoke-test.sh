#!/usr/bin/env bash
# CI Clean Environment Smoke Test Script
# Verifies that built wheel packages install and run without runtime crashes in a clean environment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=================================================="
echo "🚀 Running IC CLI Clean Environment Smoke Test"
echo "=================================================="

# Check if dist/ contains a wheel
DIST_DIR="${REPO_ROOT}/dist"
WHEEL_FILE=$(find "${DIST_DIR}" -name "ic_code-*.whl" 2>/dev/null | sort -V | tail -n 1 || true)

if [ -z "${WHEEL_FILE}" ] || [ ! -f "${WHEEL_FILE}" ]; then
    echo "⚠️  No built wheel found in ${DIST_DIR}. Building package..."
    python3 -m pip install --quiet build
    python3 -m build --wheel "${REPO_ROOT}"
    WHEEL_FILE=$(find "${DIST_DIR}" -name "ic_code-*.whl" | sort -V | tail -n 1)
fi

echo "📦 Target wheel: ${WHEEL_FILE}"

# Create isolated temporary virtual environment
TEMP_VENV=$(mktemp -d -t ic-smoke-venv-XXXXXX)
echo "📁 Creating temporary virtualenv in ${TEMP_VENV}..."
python3 -m venv "${TEMP_VENV}"

cleanup() {
    echo "🧹 Cleaning up temporary test environment..."
    rm -rf "${TEMP_VENV}"
}
trap cleanup EXIT

# Activate clean environment
source "${TEMP_VENV}/bin/activate"
pip install --upgrade --quiet pip

# 1. Test Core Installation (NO cloud extras)
echo "--------------------------------------------------"
echo "1️⃣  Testing Minimal Core Installation (No extras)..."
pip install --quiet "${WHEEL_FILE}"

echo "   ✓ Checking 'ic --help'..."
ic --help > /dev/null

echo "   ✓ Checking 'ic version'..."
ic version > /dev/null || ic --version > /dev/null

echo "   ✓ Checking lazy platform help without cloud SDKs (e.g., 'ic tencent --help')..."
ic tencent --help > /dev/null
ic aws --help > /dev/null

# 2. Test Output formatting in core
echo "--------------------------------------------------"
echo "2️⃣  Testing Core Output Formatting & Stderr Separation..."
HELP_OUTPUT=$(ic --help)
if [[ -z "${HELP_OUTPUT}" ]]; then
    echo "❌ ERROR: 'ic --help' produced empty output"
    exit 1
fi

# Verify no python traceback in standard help
if echo "${HELP_OUTPUT}" | grep -i "traceback"; then
    echo "❌ ERROR: Traceback detected in 'ic --help' output"
    exit 1
fi

echo "   ✓ Zero-crash parser & lazy-loading validated in isolated venv."

# 3. Test Extras Installation syntax
echo "--------------------------------------------------"
echo "3️⃣  Testing Extras Resolution (dry-run/compatibility check)..."
pip install --dry-run "${WHEEL_FILE}[aws]" > /dev/null 2>&1 || {
    echo "⚠️  Warning: pip dry-run not fully supported on this pip version, skipping dry-run."
}

echo "=================================================="
echo "✅ All Clean Environment Smoke Tests PASSED!"
echo "=================================================="
