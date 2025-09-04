#!/bin/bash
# setup-gcp-auth.sh
# Script to set up GCP authentication for IC CLI tool

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=""
SA_NAME="ic-cli-service-account"
KEY_DIR="$HOME/.gcp/keys"
AUTH_METHOD=""

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -p, --project PROJECT_ID    GCP Project ID (required)"
    echo "  -m, --method METHOD          Authentication method: sa|adc|gcloud (default: sa)"
    echo "  -n, --name SA_NAME           Service account name (default: ic-cli-service-account)"
    echo "  -d, --key-dir DIR            Key storage directory (default: ~/.gcp/keys)"
    echo "  -h, --help                   Show this help message"
    echo ""
    echo "Authentication methods:"
    echo "  sa      - Service Account Key (recommended for production)"
    echo "  adc     - Application Default Credentials (good for development)"
    echo "  gcloud  - gcloud CLI authentication (good for development)"
    echo ""
    echo "Examples:"
    echo "  $0 -p my-project-id -m sa"
    echo "  $0 -p my-project-id -m adc"
    echo "  $0 --project my-project --method gcloud"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -m|--method)
            AUTH_METHOD="$2"
            shift 2
            ;;
        -n|--name)
            SA_NAME="$2"
            shift 2
            ;;
        -d|--key-dir)
            KEY_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$PROJECT_ID" ]; then
    print_error "Project ID is required. Use -p or --project option."
    show_usage
    exit 1
fi

# Set default authentication method
if [ -z "$AUTH_METHOD" ]; then
    AUTH_METHOD="sa"
fi

# Validate authentication method
case $AUTH_METHOD in
    sa|adc|gcloud)
        ;;
    *)
        print_error "Invalid authentication method: $AUTH_METHOD"
        print_error "Valid methods: sa, adc, gcloud"
        exit 1
        ;;
esac

print_header "GCP Authentication Setup for IC CLI"
print_status "Project ID: $PROJECT_ID"
print_status "Authentication Method: $AUTH_METHOD"
print_status "Service Account Name: $SA_NAME"
print_status "Key Directory: $KEY_DIR"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed. Please install it first:"
    print_error "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated with gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null 2>&1; then
    print_warning "No active gcloud authentication found."
    print_status "Please run: gcloud auth login"
    exit 1
fi

# Verify project access
print_status "Verifying project access..."
if ! gcloud projects describe "$PROJECT_ID" > /dev/null 2>&1; then
    print_error "Cannot access project: $PROJECT_ID"
    print_error "Please check project ID and permissions."
    exit 1
fi

print_status "Project access verified: $PROJECT_ID"

# Setup authentication based on method
case $AUTH_METHOD in
    sa)
        print_header "Setting up Service Account Authentication"
        
        SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
        
        # Create key directory
        mkdir -p "$KEY_DIR"
        chmod 700 "$KEY_DIR"
        
        # Check if service account exists
        if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" > /dev/null 2>&1; then
            print_status "Service account already exists: $SA_EMAIL"
        else
            print_status "Creating service account: $SA_EMAIL"
            gcloud iam service-accounts create "$SA_NAME" \
                --description="Service account for IC CLI tool" \
                --display-name="IC CLI Service Account" \
                --project="$PROJECT_ID"
        fi
        
        # Grant necessary IAM roles
        print_status "Granting IAM roles..."
        
        ROLES=(
            "roles/compute.viewer"
            "roles/compute.networkViewer"
            "roles/container.clusterViewer"
            "roles/container.viewer"
            "roles/storage.objectViewer"
            "roles/storage.legacyBucketReader"
            "roles/cloudsql.viewer"
            "roles/cloudfunctions.viewer"
            "roles/run.viewer"
            "roles/compute.loadBalancerServiceUser"
            "roles/billing.viewer"
        )
        
        for role in "${ROLES[@]}"; do
            print_status "Granting role: $role"
            gcloud projects add-iam-policy-binding "$PROJECT_ID" \
                --member="serviceAccount:$SA_EMAIL" \
                --role="$role" \
                --quiet
        done
        
        # Create and download key
        KEY_FILE="$KEY_DIR/ic-cli-key.json"
        print_status "Creating service account key: $KEY_FILE"
        
        gcloud iam service-accounts keys create "$KEY_FILE" \
            --iam-account="$SA_EMAIL" \
            --project="$PROJECT_ID"
        
        chmod 600 "$KEY_FILE"
        
        # Update .env file
        print_status "Updating .env configuration..."
        
        if [ -f ".env" ]; then
            # Backup existing .env
            cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
            print_status "Backed up existing .env file"
        fi
        
        # Add or update GCP configuration
        {
            echo ""
            echo "# --------- GCP Configuration (Generated by setup-gcp-auth.sh) ------------"
            echo "GCP_SERVICE_ACCOUNT_KEY_PATH=$KEY_FILE"
            echo "GCP_PROJECTS=$PROJECT_ID"
            echo "GCP_DEFAULT_PROJECT=$PROJECT_ID"
            echo "GCP_REGIONS=us-central1"
            echo "GCP_ZONES=us-central1-a,us-central1-b"
            echo "GCP_MAX_WORKERS=10"
            echo "GCP_REQUEST_TIMEOUT=30"
            echo "GCP_RETRY_ATTEMPTS=3"
            echo "GCP_ENABLE_COMPUTE_API=true"
            echo "GCP_ENABLE_CONTAINER_API=true"
            echo "GCP_ENABLE_STORAGE_API=true"
            echo "GCP_ENABLE_SQLADMIN_API=true"
            echo "GCP_ENABLE_CLOUDFUNCTIONS_API=true"
            echo "GCP_ENABLE_RUN_API=true"
            echo "GCP_ENABLE_BILLING_API=true"
        } >> .env
        
        print_status "Service account authentication setup complete!"
        print_status "Key file: $KEY_FILE"
        print_status "Service account: $SA_EMAIL"
        ;;
        
    adc)
        print_header "Setting up Application Default Credentials"
        
        print_status "Setting up ADC..."
        gcloud auth application-default login --project="$PROJECT_ID"
        
        ADC_FILE="$HOME/.config/gcloud/application_default_credentials.json"
        
        # Update .env file
        print_status "Updating .env configuration..."
        
        if [ -f ".env" ]; then
            cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
            print_status "Backed up existing .env file"
        fi
        
        {
            echo ""
            echo "# --------- GCP Configuration (Generated by setup-gcp-auth.sh) ------------"
            echo "GOOGLE_APPLICATION_CREDENTIALS=$ADC_FILE"
            echo "GCP_PROJECTS=$PROJECT_ID"
            echo "GCP_DEFAULT_PROJECT=$PROJECT_ID"
            echo "GCP_REGIONS=us-central1"
            echo "GCP_ZONES=us-central1-a,us-central1-b"
            echo "GCP_MAX_WORKERS=10"
            echo "GCP_REQUEST_TIMEOUT=30"
            echo "GCP_RETRY_ATTEMPTS=3"
            echo "GCP_ENABLE_COMPUTE_API=true"
            echo "GCP_ENABLE_CONTAINER_API=true"
            echo "GCP_ENABLE_STORAGE_API=true"
            echo "GCP_ENABLE_SQLADMIN_API=true"
            echo "GCP_ENABLE_CLOUDFUNCTIONS_API=true"
            echo "GCP_ENABLE_RUN_API=true"
            echo "GCP_ENABLE_BILLING_API=true"
        } >> .env
        
        print_status "Application Default Credentials setup complete!"
        print_status "Credentials file: $ADC_FILE"
        ;;
        
    gcloud)
        print_header "Setting up gcloud CLI Authentication"
        
        # Set default project
        print_status "Setting default project..."
        gcloud config set project "$PROJECT_ID"
        
        # Update .env file
        print_status "Updating .env configuration..."
        
        if [ -f ".env" ]; then
            cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
            print_status "Backed up existing .env file"
        fi
        
        {
            echo ""
            echo "# --------- GCP Configuration (Generated by setup-gcp-auth.sh) ------------"
            echo "# Using gcloud CLI authentication (no additional auth config needed)"
            echo "GCP_PROJECTS=$PROJECT_ID"
            echo "GCP_DEFAULT_PROJECT=$PROJECT_ID"
            echo "GCP_REGIONS=us-central1"
            echo "GCP_ZONES=us-central1-a,us-central1-b"
            echo "GCP_MAX_WORKERS=10"
            echo "GCP_REQUEST_TIMEOUT=30"
            echo "GCP_RETRY_ATTEMPTS=3"
            echo "GCP_ENABLE_COMPUTE_API=true"
            echo "GCP_ENABLE_CONTAINER_API=true"
            echo "GCP_ENABLE_STORAGE_API=true"
            echo "GCP_ENABLE_SQLADMIN_API=true"
            echo "GCP_ENABLE_CLOUDFUNCTIONS_API=true"
            echo "GCP_ENABLE_RUN_API=true"
            echo "GCP_ENABLE_BILLING_API=true"
        } >> .env
        
        print_status "gcloud CLI authentication setup complete!"
        ;;
esac

# Test authentication
print_header "Testing Authentication"
print_status "Testing GCP authentication..."

# Test with gcloud
if gcloud projects describe "$PROJECT_ID" > /dev/null 2>&1; then
    print_status "✓ gcloud authentication working"
else
    print_warning "✗ gcloud authentication issue"
fi

# Test with IC CLI (if available)
if command -v ic &> /dev/null; then
    print_status "Testing IC CLI GCP integration..."
    if ic gcp compute info --project "$PROJECT_ID" --help > /dev/null 2>&1; then
        print_status "✓ IC CLI GCP module accessible"
    else
        print_warning "✗ IC CLI GCP module not accessible"
    fi
else
    print_warning "IC CLI not found. Install with: pip install -e ."
fi

print_header "Setup Complete"
print_status "GCP authentication has been configured successfully!"
print_status "Configuration added to .env file"
print_status ""
print_status "Next steps:"
print_status "1. Review the .env file and adjust settings as needed"
print_status "2. Test the configuration: ic gcp compute info"
print_status "3. Enable additional APIs if needed:"
print_status "   gcloud services enable compute.googleapis.com"
print_status "   gcloud services enable container.googleapis.com"
print_status "   gcloud services enable storage.googleapis.com"
print_status ""
print_status "For more information, see: docs/gcp/GCP_CONFIGURATION_GUIDE.md"