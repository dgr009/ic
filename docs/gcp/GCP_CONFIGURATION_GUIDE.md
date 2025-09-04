# GCP Configuration Guide

This guide provides comprehensive configuration examples and best practices for setting up GCP services integration with the IC CLI tool.

## 📋 Table of Contents

- [Environment Configuration Examples](#environment-configuration-examples)
- [Authentication Setup](#authentication-setup)
- [IAM Permissions Guide](#iam-permissions-guide)
- [MCP Server Configuration](#mcp-server-configuration)
- [Security Best Practices](#security-best-practices)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting Configuration Issues](#troubleshooting-configuration-issues)

## 🔧 Environment Configuration Examples

### Basic Development Setup

```bash
# .env file for development environment
# --------- GCP Development Configuration ------------

# MCP Server Configuration (Recommended)
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp
MCP_GCP_AUTH_METHOD=adc
GCP_PREFER_MCP=true

# Fallback Authentication
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

# Project Configuration
GCP_PROJECTS=my-dev-project
GCP_DEFAULT_PROJECT=my-dev-project

# Regional Configuration
GCP_REGIONS=us-central1
GCP_ZONES=us-central1-a,us-central1-b

# Performance Settings
GCP_MAX_WORKERS=5
GCP_REQUEST_TIMEOUT=30
GCP_RETRY_ATTEMPTS=3

# Service Configuration
GCP_ENABLE_BILLING_API=false  # Often not needed in dev
GCP_ENABLE_COMPUTE_API=true
GCP_ENABLE_CONTAINER_API=true
GCP_ENABLE_STORAGE_API=true
GCP_ENABLE_SQLADMIN_API=true
GCP_ENABLE_CLOUDFUNCTIONS_API=true
GCP_ENABLE_RUN_API=true
```

### Production Environment Setup

```bash
# .env file for production environment
# --------- GCP Production Configuration ------------

# MCP Server Configuration (Highly Recommended for Production)
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=https://mcp-server.company.com/gcp
MCP_GCP_AUTH_METHOD=service_account
GCP_PREFER_MCP=true

# Service Account Authentication (Fallback)
GCP_SERVICE_ACCOUNT_KEY_PATH=/secure/path/to/prod-service-account.json

# Multi-Project Configuration
GCP_PROJECTS=prod-project-1,prod-project-2,prod-project-3
GCP_DEFAULT_PROJECT=prod-project-1

# Multi-Regional Configuration
GCP_REGIONS=us-central1,us-east1,europe-west1,asia-northeast1
GCP_ZONES=us-central1-a,us-central1-b,us-east1-a,us-east1-b,europe-west1-a,asia-northeast1-a

# Production Performance Settings
GCP_MAX_WORKERS=20
GCP_REQUEST_TIMEOUT=60
GCP_RETRY_ATTEMPTS=5

# All Services Enabled
GCP_ENABLE_BILLING_API=true
GCP_ENABLE_COMPUTE_API=true
GCP_ENABLE_CONTAINER_API=true
GCP_ENABLE_STORAGE_API=true
GCP_ENABLE_SQLADMIN_API=true
GCP_ENABLE_CLOUDFUNCTIONS_API=true
GCP_ENABLE_RUN_API=true

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Multi-Environment Setup

```bash
# .env file for multi-environment management
# --------- GCP Multi-Environment Configuration ------------

# MCP Server Configuration
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp
MCP_GCP_AUTH_METHOD=service_account
GCP_PREFER_MCP=true

# Service Account for Cross-Environment Access
GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/cross-env-service-account.json

# All Environment Projects
GCP_PROJECTS=dev-project,staging-project,prod-project-1,prod-project-2
GCP_DEFAULT_PROJECT=dev-project

# Global Regional Coverage
GCP_REGIONS=us-central1,us-east1,us-west1,europe-west1,europe-west2,asia-northeast1,asia-southeast1
GCP_ZONES=us-central1-a,us-central1-b,us-east1-a,us-east1-b,europe-west1-a,asia-northeast1-a

# High Performance Settings
GCP_MAX_WORKERS=30
GCP_REQUEST_TIMEOUT=45
GCP_RETRY_ATTEMPTS=4

# All Services Enabled
GCP_ENABLE_BILLING_API=true
GCP_ENABLE_COMPUTE_API=true
GCP_ENABLE_CONTAINER_API=true
GCP_ENABLE_STORAGE_API=true
GCP_ENABLE_SQLADMIN_API=true
GCP_ENABLE_CLOUDFUNCTIONS_API=true
GCP_ENABLE_RUN_API=true
```

### CI/CD Pipeline Setup

```bash
# .env file for CI/CD environments
# --------- GCP CI/CD Configuration ------------

# MCP Server Configuration (if available in CI/CD)
MCP_GCP_ENABLED=false  # Often not available in CI/CD
GCP_PREFER_MCP=false

# Service Account Key for CI/CD
GCP_SERVICE_ACCOUNT_KEY=${GCP_CI_SERVICE_ACCOUNT_KEY}  # From CI/CD secrets

# Target Projects for Deployment Validation
GCP_PROJECTS=${DEPLOY_TARGET_PROJECTS}  # From CI/CD variables
GCP_DEFAULT_PROJECT=${PRIMARY_PROJECT}

# Regional Configuration for Deployment
GCP_REGIONS=${DEPLOY_REGIONS}
GCP_ZONES=${DEPLOY_ZONES}

# Conservative Performance Settings for CI/CD
GCP_MAX_WORKERS=5
GCP_REQUEST_TIMEOUT=120  # Longer timeout for CI/CD
GCP_RETRY_ATTEMPTS=3

# Service Configuration Based on Pipeline Needs
GCP_ENABLE_BILLING_API=false
GCP_ENABLE_COMPUTE_API=true
GCP_ENABLE_CONTAINER_API=true
GCP_ENABLE_STORAGE_API=true
GCP_ENABLE_SQLADMIN_API=false
GCP_ENABLE_CLOUDFUNCTIONS_API=true
GCP_ENABLE_RUN_API=true

# CI/CD Specific Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json
```

## 🔐 Authentication Setup

### 1. MCP Server Authentication (Recommended)

#### MCP Server Configuration
```bash
# Enable MCP integration
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp

# Authentication method for MCP server to use
MCP_GCP_AUTH_METHOD=service_account  # Options: service_account, adc, gcloud

# MCP connection settings
MCP_GCP_TIMEOUT=30
MCP_GCP_RETRY_ATTEMPTS=3
MCP_GCP_CONNECTION_POOL_SIZE=10

# Fallback configuration
MCP_GCP_FALLBACK_ENABLED=true
MCP_GCP_FALLBACK_TIMEOUT=10
```

#### MCP Server Setup Script
```bash
#!/bin/bash
# setup-mcp-server.sh

# Install MCP server dependencies
pip install mcp-server-gcp

# Configure MCP server
cat > mcp-server-config.json << EOF
{
  "gcp": {
    "auth_method": "service_account",
    "service_account_path": "/path/to/service-account.json",
    "projects": ["project-1", "project-2"],
    "regions": ["us-central1", "us-east1"],
    "cache_ttl": 300,
    "max_workers": 10
  }
}
EOF

# Start MCP server
mcp-server --config mcp-server-config.json --port 8080
```

### 2. Service Account Key Authentication

#### Creating Service Account
```bash
#!/bin/bash
# create-service-account.sh

PROJECT_ID="your-project-id"
SA_NAME="ic-cli-service-account"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Create service account
gcloud iam service-accounts create $SA_NAME \
    --description="Service account for IC CLI tool" \
    --display-name="IC CLI Service Account" \
    --project=$PROJECT_ID

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/compute.viewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/container.clusterViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectViewer"

# Create and download key
gcloud iam service-accounts keys create ~/gcp-key/ic-cli-key.json \
    --iam-account=$SA_EMAIL \
    --project=$PROJECT_ID

echo "Service account key created: ~/gcp-key/ic-cli-key.json"
```

#### Environment Configuration
```bash
# Method 1: File path
GCP_SERVICE_ACCOUNT_KEY_PATH=~/gcp-key/ic-cli-key.json

# Method 2: Inline JSON (not recommended for production)
GCP_SERVICE_ACCOUNT_KEY='{"type": "service_account", "project_id": "your-project", ...}'

# Method 3: Standard Google Cloud environment variable
GOOGLE_APPLICATION_CREDENTIALS=~/gcp-key/ic-cli-key.json
```

### 3. Application Default Credentials

#### Setup ADC
```bash
# For user accounts (development)
gcloud auth application-default login

# For service accounts on compute instances
# ADC is automatically available

# Verify ADC setup
gcloud auth application-default print-access-token
```

#### Environment Configuration
```bash
# ADC is automatically discovered, but you can specify the path
GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

# MCP server can use ADC
MCP_GCP_AUTH_METHOD=adc
```

### 4. gcloud CLI Authentication

#### Setup gcloud
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Initialize gcloud
gcloud init

# Authenticate
gcloud auth login

# Set default project
gcloud config set project your-project-id

# Verify authentication
gcloud auth list
gcloud projects list
```

#### Environment Configuration
```bash
# gcloud CLI is automatically discovered
# MCP server can use gcloud credentials
MCP_GCP_AUTH_METHOD=gcloud

# No additional environment variables needed
```

## 🛡️ IAM Permissions Guide

### Service-Specific IAM Roles

#### Compute Engine
```json
{
  "bindings": [
    {
      "role": "roles/compute.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/compute.instanceAdmin.v1",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Custom Role for Compute Engine:**
```yaml
title: "IC CLI Compute Viewer"
description: "Custom role for IC CLI Compute Engine access"
stage: "GA"
includedPermissions:
- compute.instances.list
- compute.instances.get
- compute.zones.list
- compute.machineTypes.list
- compute.disks.list
- compute.networks.list
- compute.subnetworks.list
```

#### VPC Networks
```json
{
  "bindings": [
    {
      "role": "roles/compute.networkViewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Custom Role for VPC:**
```yaml
title: "IC CLI Network Viewer"
description: "Custom role for IC CLI VPC access"
stage: "GA"
includedPermissions:
- compute.networks.list
- compute.networks.get
- compute.subnetworks.list
- compute.subnetworks.get
- compute.firewalls.list
- compute.firewalls.get
- compute.routes.list
```

#### Google Kubernetes Engine
```json
{
  "bindings": [
    {
      "role": "roles/container.clusterViewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/container.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

#### Cloud Storage
```json
{
  "bindings": [
    {
      "role": "roles/storage.objectViewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/storage.legacyBucketReader",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

#### Cloud SQL
```json
{
  "bindings": [
    {
      "role": "roles/cloudsql.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

#### Cloud Functions
```json
{
  "bindings": [
    {
      "role": "roles/cloudfunctions.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

#### Cloud Run
```json
{
  "bindings": [
    {
      "role": "roles/run.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

#### Load Balancing
```json
{
  "bindings": [
    {
      "role": "roles/compute.loadBalancerServiceUser",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/compute.networkViewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

#### Billing
```json
{
  "bindings": [
    {
      "role": "roles/billing.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/billing.projectManager",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"]
    }
  ]
}
```

### Comprehensive IAM Setup Script

```bash
#!/bin/bash
# setup-iam-permissions.sh

PROJECT_ID="your-project-id"
SA_EMAIL="ic-cli@${PROJECT_ID}.iam.gserviceaccount.com"

# Compute Engine permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/compute.viewer"

# VPC Network permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/compute.networkViewer"

# GKE permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/container.clusterViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/container.viewer"

# Cloud Storage permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/storage.legacyBucketReader"

# Cloud SQL permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/cloudsql.viewer"

# Cloud Functions permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/cloudfunctions.viewer"

# Cloud Run permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.viewer"

# Load Balancing permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/compute.loadBalancerServiceUser"

# Billing permissions (optional)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/billing.viewer"

echo "IAM permissions configured for $SA_EMAIL"
```

## 🚀 MCP Server Configuration

### MCP Server Setup

#### Docker Compose Configuration
```yaml
# docker-compose.yml for MCP server
version: '3.8'
services:
  mcp-server:
    image: mcp-server:latest
    ports:
      - "8080:8080"
    environment:
      - MCP_GCP_AUTH_METHOD=service_account
      - MCP_GCP_SERVICE_ACCOUNT_PATH=/app/credentials/service-account.json
      - MCP_GCP_PROJECTS=project-1,project-2,project-3
      - MCP_GCP_REGIONS=us-central1,us-east1,europe-west1
      - MCP_CACHE_TTL=300
      - MCP_MAX_WORKERS=20
    volumes:
      - ./credentials:/app/credentials:ro
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### MCP Server Configuration File
```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "workers": 4
  },
  "gcp": {
    "auth": {
      "method": "service_account",
      "service_account_path": "/app/credentials/service-account.json",
      "scopes": [
        "https://www.googleapis.com/auth/cloud-platform.read-only",
        "https://www.googleapis.com/auth/compute.readonly",
        "https://www.googleapis.com/auth/container.readonly"
      ]
    },
    "projects": {
      "default": "my-default-project",
      "allowed": ["project-1", "project-2", "project-3"],
      "discovery": true
    },
    "regions": {
      "default": ["us-central1", "us-east1"],
      "allowed": ["us-central1", "us-east1", "us-west1", "europe-west1", "asia-northeast1"]
    },
    "services": {
      "compute": {
        "enabled": true,
        "cache_ttl": 300
      },
      "vpc": {
        "enabled": true,
        "cache_ttl": 600
      },
      "gke": {
        "enabled": true,
        "cache_ttl": 300
      },
      "storage": {
        "enabled": true,
        "cache_ttl": 900
      },
      "sql": {
        "enabled": true,
        "cache_ttl": 600
      },
      "functions": {
        "enabled": true,
        "cache_ttl": 300
      },
      "run": {
        "enabled": true,
        "cache_ttl": 300
      },
      "lb": {
        "enabled": true,
        "cache_ttl": 600
      },
      "firewall": {
        "enabled": true,
        "cache_ttl": 900
      },
      "billing": {
        "enabled": true,
        "cache_ttl": 3600
      }
    },
    "performance": {
      "max_workers": 20,
      "request_timeout": 30,
      "retry_attempts": 3,
      "connection_pool_size": 10
    },
    "logging": {
      "level": "INFO",
      "format": "json",
      "file": "/app/logs/mcp-server.log"
    }
  }
}
```

#### Client Configuration for MCP
```bash
# .env configuration for MCP client
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp
MCP_GCP_AUTH_METHOD=service_account
MCP_GCP_TIMEOUT=30
MCP_GCP_RETRY_ATTEMPTS=3
MCP_GCP_CONNECTION_POOL_SIZE=10
MCP_GCP_FALLBACK_ENABLED=true
MCP_GCP_FALLBACK_TIMEOUT=10
GCP_PREFER_MCP=true
```

## 🔒 Security Best Practices

### Credential Management

#### 1. Service Account Key Security
```bash
# Secure key storage
mkdir -p ~/.gcp/keys
chmod 700 ~/.gcp/keys

# Store key securely
cp service-account.json ~/.gcp/keys/
chmod 600 ~/.gcp/keys/service-account.json

# Use in environment
export GCP_SERVICE_ACCOUNT_KEY_PATH=~/.gcp/keys/service-account.json
```

#### 2. Environment Variable Security
```bash
# .env.example (template file - safe to commit)
GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/your/service-account.json
GCP_PROJECTS=your-project-1,your-project-2

# .env (actual file - never commit)
GCP_SERVICE_ACCOUNT_KEY_PATH=/home/user/.gcp/keys/prod-key.json
GCP_PROJECTS=prod-project-1,prod-project-2
```

#### 3. Key Rotation Script
```bash
#!/bin/bash
# rotate-service-account-keys.sh

PROJECT_ID="your-project-id"
SA_EMAIL="ic-cli@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_DIR="~/.gcp/keys"
BACKUP_DIR="~/.gcp/keys/backup"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup current key
if [ -f "$KEY_DIR/service-account.json" ]; then
    cp "$KEY_DIR/service-account.json" "$BACKUP_DIR/service-account-$(date +%Y%m%d).json"
fi

# Create new key
gcloud iam service-accounts keys create "$KEY_DIR/service-account-new.json" \
    --iam-account=$SA_EMAIL \
    --project=$PROJECT_ID

# Test new key
export GCP_SERVICE_ACCOUNT_KEY_PATH="$KEY_DIR/service-account-new.json"
if ic gcp compute info --project $PROJECT_ID > /dev/null 2>&1; then
    # New key works, replace old key
    mv "$KEY_DIR/service-account-new.json" "$KEY_DIR/service-account.json"
    echo "Key rotation successful"
else
    # New key failed, keep old key
    rm "$KEY_DIR/service-account-new.json"
    echo "Key rotation failed, keeping old key"
    exit 1
fi

# Clean up old keys (keep last 3)
find $BACKUP_DIR -name "service-account-*.json" -type f | sort -r | tail -n +4 | xargs rm -f
```

### Network Security

#### 1. MCP Server Security
```bash
# Use HTTPS for production MCP server
MCP_GCP_ENDPOINT=https://mcp-server.company.com/gcp

# Configure SSL/TLS
MCP_GCP_SSL_VERIFY=true
MCP_GCP_SSL_CERT_PATH=/path/to/cert.pem
MCP_GCP_SSL_KEY_PATH=/path/to/key.pem
```

#### 2. Firewall Configuration
```bash
# Allow only necessary traffic to MCP server
# Example iptables rules
iptables -A INPUT -p tcp --dport 8080 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP
```

### Access Control

#### 1. Principle of Least Privilege
```bash
# Create minimal custom role
gcloud iam roles create icCliMinimalRole \
    --project=$PROJECT_ID \
    --title="IC CLI Minimal Role" \
    --description="Minimal permissions for IC CLI" \
    --permissions="compute.instances.list,compute.zones.list,storage.buckets.list"
```

#### 2. Conditional IAM Policies
```json
{
  "bindings": [
    {
      "role": "roles/compute.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"],
      "condition": {
        "title": "Time-based access",
        "description": "Only allow access during business hours",
        "expression": "request.time.getHours() >= 9 && request.time.getHours() <= 17"
      }
    }
  ]
}
```

## ⚡ Performance Optimization

### Parallel Processing Configuration

#### 1. Worker Thread Optimization
```bash
# Calculate optimal worker count based on system resources
CORES=$(nproc)
OPTIMAL_WORKERS=$((CORES * 2))

# Configure based on system capacity
if [ $CORES -le 2 ]; then
    GCP_MAX_WORKERS=5
elif [ $CORES -le 4 ]; then
    GCP_MAX_WORKERS=10
elif [ $CORES -le 8 ]; then
    GCP_MAX_WORKERS=20
else
    GCP_MAX_WORKERS=30
fi

export GCP_MAX_WORKERS
```

#### 2. Memory-Based Configuration
```bash
# Configure based on available memory
MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')

if [ $MEMORY_GB -le 4 ]; then
    GCP_MAX_WORKERS=5
    GCP_REQUEST_TIMEOUT=60
elif [ $MEMORY_GB -le 8 ]; then
    GCP_MAX_WORKERS=10
    GCP_REQUEST_TIMEOUT=45
else
    GCP_MAX_WORKERS=20
    GCP_REQUEST_TIMEOUT=30
fi
```

### Caching Configuration

#### 1. MCP Server Caching
```json
{
  "gcp": {
    "cache": {
      "enabled": true,
      "backend": "redis",
      "redis_url": "redis://localhost:6379/0",
      "ttl": {
        "compute_instances": 300,
        "vpc_networks": 600,
        "gke_clusters": 300,
        "storage_buckets": 900,
        "sql_instances": 600,
        "functions": 300,
        "run_services": 300,
        "load_balancers": 600,
        "firewall_rules": 900,
        "billing_info": 3600
      }
    }
  }
}
```

#### 2. Client-Side Caching
```bash
# Enable client-side caching
GCP_ENABLE_CACHE=true
GCP_CACHE_DIR=~/.cache/ic-cli/gcp
GCP_CACHE_TTL=300  # 5 minutes

# Cache cleanup script
find ~/.cache/ic-cli/gcp -type f -mmin +60 -delete
```

### Regional Optimization

#### 1. Region-Specific Configuration
```bash
# Configure regions based on resource location
# US-based resources
GCP_REGIONS_US=us-central1,us-east1,us-west1,us-west2

# Europe-based resources
GCP_REGIONS_EU=europe-west1,europe-west2,europe-west3,europe-north1

# Asia-based resources
GCP_REGIONS_ASIA=asia-northeast1,asia-southeast1,asia-east1

# Use appropriate region set
export GCP_REGIONS=$GCP_REGIONS_US
```

#### 2. Zone Optimization
```bash
# Configure zones for better performance
# High-availability zones
GCP_ZONES_HA=us-central1-a,us-central1-b,us-central1-c

# Single-zone for testing
GCP_ZONES_TEST=us-central1-a

# Use appropriate zone set
export GCP_ZONES=$GCP_ZONES_HA
```

## 🔍 Troubleshooting Configuration Issues

### Common Configuration Problems

#### 1. Authentication Issues
```bash
# Debug authentication
export LOG_LEVEL=DEBUG
ic gcp compute info --project test-project

# Check authentication method priority
echo "Checking authentication methods..."
if [ -n "$GCP_SERVICE_ACCOUNT_KEY" ]; then
    echo "✓ Service Account Key (inline) found"
elif [ -f "$GCP_SERVICE_ACCOUNT_KEY_PATH" ]; then
    echo "✓ Service Account Key (file) found: $GCP_SERVICE_ACCOUNT_KEY_PATH"
elif [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "✓ Application Default Credentials found: $GOOGLE_APPLICATION_CREDENTIALS"
elif gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null; then
    echo "✓ gcloud CLI authentication found"
else
    echo "✗ No authentication method found"
fi
```

#### 2. Project Access Issues
```bash
# Verify project access
gcloud projects list --format="table(projectId,name,lifecycleState)"

# Test project access with service account
gcloud auth activate-service-account --key-file=$GCP_SERVICE_ACCOUNT_KEY_PATH
gcloud projects list

# Check project permissions
gcloud projects get-iam-policy $PROJECT_ID --flatten="bindings[].members" \
    --format="table(bindings.role)" \
    --filter="bindings.members:serviceAccount:$SA_EMAIL"
```

#### 3. API Enablement Issues
```bash
# Check enabled APIs
gcloud services list --enabled --project=$PROJECT_ID

# Enable required APIs
REQUIRED_APIS=(
    "compute.googleapis.com"
    "container.googleapis.com"
    "storage.googleapis.com"
    "sqladmin.googleapis.com"
    "cloudfunctions.googleapis.com"
    "run.googleapis.com"
    "cloudbilling.googleapis.com"
)

for api in "${REQUIRED_APIS[@]}"; do
    echo "Enabling $api..."
    gcloud services enable $api --project=$PROJECT_ID
done
```

#### 4. MCP Server Connection Issues
```bash
# Test MCP server connectivity
curl -f $MCP_GCP_ENDPOINT/health

# Check MCP server logs
docker logs mcp-server

# Test MCP server endpoints
curl -X POST $MCP_GCP_ENDPOINT/compute/instances \
    -H "Content-Type: application/json" \
    -d '{"project": "test-project"}'
```

### Configuration Validation Script

```bash
#!/bin/bash
# validate-gcp-config.sh

echo "=== GCP Configuration Validation ==="

# Check environment variables
echo "1. Checking environment variables..."
if [ -n "$GCP_PROJECTS" ]; then
    echo "✓ GCP_PROJECTS: $GCP_PROJECTS"
else
    echo "⚠ GCP_PROJECTS not set, will discover projects"
fi

if [ -n "$GCP_REGIONS" ]; then
    echo "✓ GCP_REGIONS: $GCP_REGIONS"
else
    echo "⚠ GCP_REGIONS not set, using defaults"
fi

# Check authentication
echo "2. Checking authentication..."
if [ "$MCP_GCP_ENABLED" = "true" ]; then
    echo "✓ MCP integration enabled"
    if curl -f $MCP_GCP_ENDPOINT/health > /dev/null 2>&1; then
        echo "✓ MCP server accessible"
    else
        echo "✗ MCP server not accessible: $MCP_GCP_ENDPOINT"
    fi
elif [ -n "$GCP_SERVICE_ACCOUNT_KEY" ]; then
    echo "✓ Service Account Key (inline) configured"
elif [ -f "$GCP_SERVICE_ACCOUNT_KEY_PATH" ]; then
    echo "✓ Service Account Key (file) found: $GCP_SERVICE_ACCOUNT_KEY_PATH"
elif [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "✓ Application Default Credentials found"
elif gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 > /dev/null 2>&1; then
    echo "✓ gcloud CLI authentication active"
else
    echo "✗ No authentication method configured"
    exit 1
fi

# Test basic functionality
echo "3. Testing basic functionality..."
if ic gcp compute info --help > /dev/null 2>&1; then
    echo "✓ IC CLI GCP module accessible"
else
    echo "✗ IC CLI GCP module not accessible"
    exit 1
fi

# Test project access
echo "4. Testing project access..."
if [ -n "$GCP_PROJECTS" ]; then
    IFS=',' read -ra PROJECTS <<< "$GCP_PROJECTS"
    for project in "${PROJECTS[@]}"; do
        if gcloud projects describe $project > /dev/null 2>&1; then
            echo "✓ Project accessible: $project"
        else
            echo "✗ Project not accessible: $project"
        fi
    done
fi

echo "=== Configuration validation complete ==="
```

### Performance Monitoring Script

```bash
#!/bin/bash
# monitor-gcp-performance.sh

echo "=== GCP Performance Monitoring ==="

# Test single service performance
echo "1. Testing single service performance..."
time ic gcp compute info --project $GCP_DEFAULT_PROJECT > /dev/null

# Test multi-service performance
echo "2. Testing multi-service performance..."
time ic gcp compute,vpc,gke info --project $GCP_DEFAULT_PROJECT > /dev/null

# Test multi-project performance
echo "3. Testing multi-project performance..."
time ic gcp compute info --project $GCP_PROJECTS > /dev/null

# Monitor resource usage
echo "4. Resource usage during operation..."
(
    while true; do
        echo "$(date): CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}'), Memory: $(free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}')"
        sleep 1
    done
) &
MONITOR_PID=$!

# Run test operation
ic gcp compute,vpc,gke,storage info --project $GCP_PROJECTS > /dev/null

# Stop monitoring
kill $MONITOR_PID

echo "=== Performance monitoring complete ==="
```

---

## 📞 Support

For configuration issues or questions:

1. Check the [troubleshooting section](#troubleshooting-configuration-issues)
2. Review the [GCP README](../gcp/README.md) for service-specific guidance
3. Validate your configuration using the provided scripts
4. Open an issue on the project repository with configuration details

**Maintainer:** SangYun Kim (cruiser594@gmail.com)