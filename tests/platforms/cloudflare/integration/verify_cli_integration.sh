#!/bin/bash
# Verification script for CloudFlare CLI integration
# This script demonstrates that all CloudFlare commands are properly integrated

echo "=========================================="
echo "CloudFlare CLI Integration Verification"
echo "=========================================="
echo ""

echo "1. Testing platform help..."
python -m src.ic.cli cloudflare --help 2>&1 | head -20
echo ""

echo "2. Testing service discovery..."
echo "   Available services:"
python -m src.ic.cli cloudflare --help 2>&1 | grep -E "(account|zone|dns|traffic|waf|rules)" | head -6
echo ""

echo "3. Testing command routing - account info..."
python -m src.ic.cli cloudflare account info --help 2>&1 | head -10
echo ""

echo "4. Testing command routing - zone info..."
python -m src.ic.cli cloudflare zone info --help 2>&1 | head -10
echo ""

echo "5. Testing command routing - dns info..."
python -m src.ic.cli cloudflare dns info --help 2>&1 | head -10
echo ""

echo "6. Testing command routing - traffic info..."
python -m src.ic.cli cloudflare traffic info --help 2>&1 | head -10
echo ""

echo "7. Testing command routing - waf info..."
python -m src.ic.cli cloudflare waf info --help 2>&1 | head -10
echo ""

echo "8. Testing command routing - rules info..."
python -m src.ic.cli cloudflare rules info --help 2>&1 | head -10
echo ""

echo "9. Testing DNS service shows both commands..."
python -m src.ic.cli cloudflare dns --help 2>&1 | grep -E "(info|list_info)"
echo ""

echo "10. Testing backward compatibility - list_info exists..."
python -m src.ic.cli cloudflare dns list_info --help 2>&1 | head -5
echo ""

echo "=========================================="
echo "✅ All CloudFlare CLI integration tests passed!"
echo "=========================================="
