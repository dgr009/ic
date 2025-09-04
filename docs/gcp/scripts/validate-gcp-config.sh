#!/bin/bash
# validate-gcp-config.sh
# Script to validate GCP configuration for IC CLI tool

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

# Function to print colored output
print_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

print_fail() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNING++))
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Load environment variables if .env exists
if [ -f ".env" ]; then
    print_info "Loading configuration from .env file"
    set -a
    source .env
    set +a
else
    print_warning ".env file not found"
fi

print_header "GCP Configuration Validation"

# 1. Check environment variables
print_header "1. Environment Variables"

if [ -n "$GCP_PROJECTS" ]; then
    print_pass "GCP_PROJECTS is set: $GCP_PROJECTS"
else
    print_warning "GCP_PROJECTS not set - will attempt project discovery"
fi

if [ -n "$GCP_DEFAULT_PROJECT" ]; then
    print_pass "GCP_DEFAULT_PROJECT is set: $GCP_DEFAULT_PROJECT"
else
    print_warning "GCP_DEFAULT_PROJECT not set"
fi

if [ -n "$GCP_REGIONS" ]; then
    print_pass "GCP_REGIONS is set: $GCP_REGIONS"
else
    print_warning "GCP_REGIONS not set - using defaults"
fi

if [ -n "$GCP_ZONES" ]; then
    print_pass "GCP_ZONES is set: $GCP_ZONES"
else
    print_warning "GCP_ZONES not set - using defaults"
fi

# Performance settings
if [ -n "$GCP_MAX_WORKERS" ]; then
    if [ "$GCP_MAX_WORKERS" -gt 0 ] && [ "$GCP_MAX_WORKERS" -le 50 ]; then
        print_pass "GCP_MAX_WORKERS is valid: $GCP_MAX_WORKERS"
    else
        print_warning "GCP_MAX_WORKERS should be between 1-50: $GCP_MAX_WORKERS"
    fi
else
    print_warning "GCP_MAX_WORKERS not set - using default"
fi

# 2. Check authentication configuration
print_header "2. Authentication Configuration"

AUTH_METHODS_FOUND=0

# Check MCP configuration
if [ "$MCP_GCP_ENABLED" = "true" ]; then
    print_pass "MCP integration is enabled"
    ((AUTH_METHODS_FOUND++))
    
    if [ -n "$MCP_GCP_ENDPOINT" ]; then
        print_pass "MCP endpoint configured: $MCP_GCP_ENDPOINT"
        
        # Test MCP server connectivity
        if command -v curl &> /dev/null; then
            if curl -f -s --connect-timeout 5 "$MCP_GCP_ENDPOINT/health" > /dev/null 2>&1; then
                print_pass "MCP server is accessible"
            else
                print_fail "MCP server is not accessible: $MCP_GCP_ENDPOINT"
            fi
        else
            print_warning "curl not available - cannot test MCP connectivity"
        fi
    else
        print_fail "MCP enabled but endpoint not configured"
    fi
    
    if [ -n "$MCP_GCP_AUTH_METHOD" ]; then
        case "$MCP_GCP_AUTH_METHOD" in
            service_account|adc|gcloud)
                print_pass "MCP auth method is valid: $MCP_GCP_AUTH_METHOD"
                ;;
            *)
                print_fail "Invalid MCP auth method: $MCP_GCP_AUTH_METHOD"
                ;;
        esac
    else
        print_warning "MCP auth method not specified"
    fi
fi

# Check service account key (inline)
if [ -n "$GCP_SERVICE_ACCOUNT_KEY" ]; then
    print_pass "Service Account Key (inline) is configured"
    ((AUTH_METHODS_FOUND++))
    
    # Validate JSON format
    if echo "$GCP_SERVICE_ACCOUNT_KEY" | python3 -m json.tool > /dev/null 2>&1; then
        print_pass "Service Account Key JSON is valid"
    else
        print_fail "Service Account Key JSON is invalid"
    fi
fi

# Check service account key (file)
if [ -n "$GCP_SERVICE_ACCOUNT_KEY_PATH" ]; then
    if [ -f "$GCP_SERVICE_ACCOUNT_KEY_PATH" ]; then
        print_pass "Service Account Key file exists: $GCP_SERVICE_ACCOUNT_KEY_PATH"
        ((AUTH_METHODS_FOUND++))
        
        # Check file permissions
        PERMS=$(stat -c "%a" "$GCP_SERVICE_ACCOUNT_KEY_PATH" 2>/dev/null || stat -f "%A" "$GCP_SERVICE_ACCOUNT_KEY_PATH" 2>/dev/null)
        if [ "$PERMS" = "600" ] || [ "$PERMS" = "0600" ]; then
            print_pass "Service Account Key file has secure permissions: $PERMS"
        else
            print_warning "Service Account Key file permissions should be 600: $PERMS"
        fi
        
        # Validate JSON format
        if python3 -m json.tool "$GCP_SERVICE_ACCOUNT_KEY_PATH" > /dev/null 2>&1; then
            print_pass "Service Account Key file JSON is valid"
        else
            print_fail "Service Account Key file JSON is invalid"
        fi
    else
        print_fail "Service Account Key file not found: $GCP_SERVICE_ACCOUNT_KEY_PATH"
    fi
fi

# Check Application Default Credentials
if [ -n "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    if [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        print_pass "Application Default Credentials file exists: $GOOGLE_APPLICATION_CREDENTIALS"
        ((AUTH_METHODS_FOUND++))
    else
        print_fail "Application Default Credentials file not found: $GOOGLE_APPLICATION_CREDENTIALS"
    fi
elif [ -f "$HOME/.config/gcloud/application_default_credentials.json" ]; then
    print_pass "Application Default Credentials found in default location"
    ((AUTH_METHODS_FOUND++))
fi

# Check gcloud CLI authentication
if command -v gcloud &> /dev/null; then
    if gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null 2>&1; then
        ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
        print_pass "gcloud CLI authentication active: $ACTIVE_ACCOUNT"
        ((AUTH_METHODS_FOUND++))
    else
        print_warning "gcloud CLI not authenticated"
    fi
else
    print_warning "gcloud CLI not installed"
fi

# Summary of authentication methods
if [ $AUTH_METHODS_FOUND -eq 0 ]; then
    print_fail "No authentication methods configured"
elif [ $AUTH_METHODS_FOUND -eq 1 ]; then
    print_pass "One authentication method configured"
else
    print_pass "$AUTH_METHODS_FOUND authentication methods configured"
fi

# 3. Check gcloud CLI installation and configuration
print_header "3. gcloud CLI Configuration"

if command -v gcloud &> /dev/null; then
    print_pass "gcloud CLI is installed"
    
    # Check gcloud version
    GCLOUD_VERSION=$(gcloud version --format="value(Google Cloud SDK)" 2>/dev/null)
    if [ -n "$GCLOUD_VERSION" ]; then
        print_pass "gcloud version: $GCLOUD_VERSION"
    fi
    
    # Check default project
    DEFAULT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ -n "$DEFAULT_PROJECT" ]; then
        print_pass "gcloud default project: $DEFAULT_PROJECT"
    else
        print_warning "gcloud default project not set"
    fi
else
    print_fail "gcloud CLI is not installed"
fi

# 4. Test project access
print_header "4. Project Access Validation"

if command -v gcloud &> /dev/null; then
    if [ -n "$GCP_PROJECTS" ]; then
        IFS=',' read -ra PROJECTS <<< "$GCP_PROJECTS"
        for project in "${PROJECTS[@]}"; do
            project=$(echo "$project" | xargs)  # Trim whitespace
            if gcloud projects describe "$project" > /dev/null 2>&1; then
                print_pass "Project accessible: $project"
            else
                print_fail "Project not accessible: $project"
            fi
        done
    elif [ -n "$GCP_DEFAULT_PROJECT" ]; then
        if gcloud projects describe "$GCP_DEFAULT_PROJECT" > /dev/null 2>&1; then
            print_pass "Default project accessible: $GCP_DEFAULT_PROJECT"
        else
            print_fail "Default project not accessible: $GCP_DEFAULT_PROJECT"
        fi
    else
        print_warning "No projects configured for testing"
    fi
else
    print_warning "Cannot test project access - gcloud CLI not available"
fi

# 5. Check API enablement
print_header "5. API Enablement Check"

REQUIRED_APIS=(
    "compute.googleapis.com"
    "container.googleapis.com"
    "storage.googleapis.com"
    "sqladmin.googleapis.com"
    "cloudfunctions.googleapis.com"
    "run.googleapis.com"
    "cloudbilling.googleapis.com"
)

if command -v gcloud &> /dev/null && [ -n "$GCP_DEFAULT_PROJECT" ]; then
    for api in "${REQUIRED_APIS[@]}"; do
        if gcloud services list --enabled --filter="name:$api" --format="value(name)" --project="$GCP_DEFAULT_PROJECT" 2>/dev/null | grep -q "$api"; then
            print_pass "API enabled: $api"
        else
            print_warning "API not enabled: $api"
        fi
    done
else
    print_warning "Cannot check API enablement - gcloud CLI or project not available"
fi

# 6. Test IC CLI integration
print_header "6. IC CLI Integration Test"

if command -v ic &> /dev/null; then
    print_pass "IC CLI is installed"
    
    # Test GCP module availability
    if ic gcp compute info --help > /dev/null 2>&1; then
        print_pass "IC CLI GCP module is accessible"
    else
        print_fail "IC CLI GCP module is not accessible"
    fi
    
    # Test basic functionality (if project is available)
    if [ -n "$GCP_DEFAULT_PROJECT" ]; then
        print_info "Testing basic GCP functionality..."
        if timeout 30 ic gcp compute info --project "$GCP_DEFAULT_PROJECT" > /dev/null 2>&1; then
            print_pass "Basic GCP functionality test passed"
        else
            print_warning "Basic GCP functionality test failed or timed out"
        fi
    fi
else
    print_fail "IC CLI is not installed - run: pip install -e ."
fi

# 7. Performance and configuration validation
print_header "7. Performance Configuration"

# Check worker configuration
if [ -n "$GCP_MAX_WORKERS" ]; then
    CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "unknown")
    if [ "$CORES" != "unknown" ]; then
        RECOMMENDED_WORKERS=$((CORES * 2))
        if [ "$GCP_MAX_WORKERS" -le "$RECOMMENDED_WORKERS" ]; then
            print_pass "Worker count is reasonable for system: $GCP_MAX_WORKERS (cores: $CORES)"
        else
            print_warning "Worker count may be too high: $GCP_MAX_WORKERS (recommended: $RECOMMENDED_WORKERS for $CORES cores)"
        fi
    fi
fi

# Check timeout configuration
if [ -n "$GCP_REQUEST_TIMEOUT" ]; then
    if [ "$GCP_REQUEST_TIMEOUT" -ge 10 ] && [ "$GCP_REQUEST_TIMEOUT" -le 300 ]; then
        print_pass "Request timeout is reasonable: ${GCP_REQUEST_TIMEOUT}s"
    else
        print_warning "Request timeout should be between 10-300 seconds: ${GCP_REQUEST_TIMEOUT}s"
    fi
fi

# 8. Security validation
print_header "8. Security Configuration"

# Check for inline service account keys (security risk)
if [ -n "$GCP_SERVICE_ACCOUNT_KEY" ]; then
    print_warning "Using inline service account key - consider using key file for better security"
fi

# Check file permissions for key files
if [ -n "$GCP_SERVICE_ACCOUNT_KEY_PATH" ] && [ -f "$GCP_SERVICE_ACCOUNT_KEY_PATH" ]; then
    PERMS=$(stat -c "%a" "$GCP_SERVICE_ACCOUNT_KEY_PATH" 2>/dev/null || stat -f "%A" "$GCP_SERVICE_ACCOUNT_KEY_PATH" 2>/dev/null)
    if [ "$PERMS" = "600" ] || [ "$PERMS" = "0600" ]; then
        print_pass "Service account key file has secure permissions"
    else
        print_warning "Service account key file should have 600 permissions"
    fi
fi

# Check for MCP HTTPS in production
if [ "$MCP_GCP_ENABLED" = "true" ] && [ -n "$MCP_GCP_ENDPOINT" ]; then
    if echo "$MCP_GCP_ENDPOINT" | grep -q "^https://"; then
        print_pass "MCP endpoint uses HTTPS"
    elif echo "$MCP_GCP_ENDPOINT" | grep -q "^http://localhost"; then
        print_warning "MCP endpoint uses HTTP (acceptable for localhost)"
    else
        print_warning "MCP endpoint should use HTTPS for production"
    fi
fi

# Final summary
print_header "Validation Summary"

TOTAL_CHECKS=$((CHECKS_PASSED + CHECKS_FAILED + CHECKS_WARNING))

echo -e "${GREEN}Passed: $CHECKS_PASSED${NC}"
echo -e "${YELLOW}Warnings: $CHECKS_WARNING${NC}"
echo -e "${RED}Failed: $CHECKS_FAILED${NC}"
echo -e "Total: $TOTAL_CHECKS"

if [ $CHECKS_FAILED -eq 0 ]; then
    if [ $CHECKS_WARNING -eq 0 ]; then
        print_info "✅ Configuration validation completed successfully!"
        exit 0
    else
        print_info "⚠️  Configuration validation completed with warnings."
        print_info "Review the warnings above and consider addressing them."
        exit 0
    fi
else
    print_info "❌ Configuration validation failed."
    print_info "Please address the failed checks above."
    exit 1
fi