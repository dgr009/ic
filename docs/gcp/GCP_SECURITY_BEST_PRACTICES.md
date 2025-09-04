# GCP Security Best Practices for IC CLI

This document outlines security best practices for configuring and using GCP services integration with the IC CLI tool.

## 🔐 Authentication Security

### Service Account Management

#### 1. Create Dedicated Service Accounts
```bash
# Create a dedicated service account for IC CLI
gcloud iam service-accounts create ic-cli-service-account \
    --description="Dedicated service account for IC CLI tool" \
    --display-name="IC CLI Service Account"
```

#### 2. Apply Principle of Least Privilege
```bash
# Grant only necessary permissions
PROJECT_ID="your-project-id"
SA_EMAIL="ic-cli-service-account@${PROJECT_ID}.iam.gserviceaccount.com"

# Compute Engine - read-only access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/compute.viewer"

# Avoid broad permissions like roles/editor or roles/owner
```

#### 3. Custom IAM Roles
Create custom roles with minimal required permissions:

```yaml
# custom-ic-cli-role.yaml
title: "IC CLI Custom Role"
description: "Minimal permissions for IC CLI operations"
stage: "GA"
includedPermissions:
- compute.instances.list
- compute.instances.get
- compute.zones.list
- compute.machineTypes.list
- compute.networks.list
- compute.subnetworks.list
- container.clusters.list
- container.clusters.get
- storage.buckets.list
- storage.buckets.get
```

```bash
# Create and assign custom role
gcloud iam roles create icCliCustomRole \
    --project=$PROJECT_ID \
    --file=custom-ic-cli-role.yaml

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="projects/$PROJECT_ID/roles/icCliCustomRole"
```

### Key Management

#### 1. Secure Key Storage
```bash
# Create secure directory for keys
mkdir -p ~/.gcp/keys
chmod 700 ~/.gcp/keys

# Store keys with restrictive permissions
chmod 600 ~/.gcp/keys/service-account.json

# Never store keys in version control
echo "*.json" >> ~/.gitignore
echo ".gcp/" >> ~/.gitignore
```

#### 2. Key Rotation
```bash
#!/bin/bash
# rotate-keys.sh - Automated key rotation script

PROJECT_ID="your-project-id"
SA_EMAIL="ic-cli-service-account@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_DIR="$HOME/.gcp/keys"

# Create new key
gcloud iam service-accounts keys create "$KEY_DIR/new-key.json" \
    --iam-account=$SA_EMAIL

# Test new key
export GOOGLE_APPLICATION_CREDENTIALS="$KEY_DIR/new-key.json"
if gcloud projects list > /dev/null 2>&1; then
    # New key works, replace old key
    mv "$KEY_DIR/service-account.json" "$KEY_DIR/old-key.json"
    mv "$KEY_DIR/new-key.json" "$KEY_DIR/service-account.json"
    
    # Delete old key from GCP (get key ID first)
    OLD_KEY_ID=$(gcloud iam service-accounts keys list \
        --iam-account=$SA_EMAIL \
        --format="value(name)" \
        --filter="validAfterTime<$(date -d '1 day ago' --iso-8601)")
    
    if [ -n "$OLD_KEY_ID" ]; then
        gcloud iam service-accounts keys delete $OLD_KEY_ID \
            --iam-account=$SA_EMAIL --quiet
    fi
    
    # Clean up local old key
    rm "$KEY_DIR/old-key.json"
    echo "Key rotation completed successfully"
else
    echo "New key validation failed"
    rm "$KEY_DIR/new-key.json"
    exit 1
fi
```

#### 3. Environment Variable Security
```bash
# Use file paths instead of inline JSON
export GCP_SERVICE_ACCOUNT_KEY_PATH="$HOME/.gcp/keys/service-account.json"

# Avoid inline keys in environment variables
# DON'T DO THIS:
# export GCP_SERVICE_ACCOUNT_KEY='{"type": "service_account", ...}'

# Use .env files with proper permissions
chmod 600 .env

# Never commit .env files
echo ".env" >> .gitignore
```

## 🌐 Network Security

### MCP Server Security

#### 1. Use HTTPS in Production
```bash
# Production MCP server configuration
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=https://mcp-server.company.com/gcp  # Use HTTPS
MCP_GCP_SSL_VERIFY=true
```

#### 2. Network Isolation
```bash
# Docker network isolation
docker network create --driver bridge mcp-secure-network

# Run MCP server in isolated network
docker run -d \
    --name mcp-gcp-server \
    --network mcp-secure-network \
    -p 127.0.0.1:8080:8080 \  # Bind to localhost only
    mcp-server:latest
```

#### 3. Firewall Configuration
```bash
# Allow only necessary traffic
# Example iptables rules for MCP server
iptables -A INPUT -p tcp --dport 8080 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -s 172.16.0.0/12 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -s 192.168.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP
```

### API Security

#### 1. Request Validation
```bash
# Enable SSL verification
GCP_SSL_VERIFY=true

# Set reasonable timeouts
GCP_REQUEST_TIMEOUT=30
GCP_RETRY_ATTEMPTS=3

# Limit concurrent connections
GCP_MAX_WORKERS=10
```

#### 2. Rate Limiting
```bash
# Configure rate limiting in MCP server
# config.json
{
  "gcp": {
    "rate_limiting": {
      "enabled": true,
      "requests_per_minute": 100,
      "burst_size": 20
    }
  }
}
```

## 🔒 Access Control

### Conditional IAM Policies

#### 1. Time-Based Access
```json
{
  "bindings": [
    {
      "role": "roles/compute.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"],
      "condition": {
        "title": "Business hours only",
        "description": "Allow access only during business hours",
        "expression": "request.time.getHours() >= 9 && request.time.getHours() <= 17"
      }
    }
  ]
}
```

#### 2. IP-Based Access
```json
{
  "bindings": [
    {
      "role": "roles/compute.viewer",
      "members": ["serviceAccount:ic-cli@project.iam.gserviceaccount.com"],
      "condition": {
        "title": "Office IP only",
        "description": "Allow access only from office IP range",
        "expression": "inIpRange(origin.ip, '203.0.113.0/24')"
      }
    }
  ]
}
```

### Resource-Level Permissions

#### 1. Project-Specific Access
```bash
# Grant access to specific projects only
for project in "dev-project" "staging-project"; do
    gcloud projects add-iam-policy-binding $project \
        --member="serviceAccount:$SA_EMAIL" \
        --role="roles/compute.viewer"
done
```

#### 2. Resource Labels for Access Control
```bash
# Create resources with security labels
gcloud compute instances create my-instance \
    --labels=environment=production,team=devops,security-level=high

# Use IAM conditions based on labels
# condition: "resource.labels.security-level == 'high'"
```

## 📊 Monitoring and Auditing

### Audit Logging

#### 1. Enable Cloud Audit Logs
```bash
# Enable audit logs for all services
gcloud logging sinks create ic-cli-audit-sink \
    bigquery.googleapis.com/projects/$PROJECT_ID/datasets/audit_logs \
    --log-filter='protoPayload.serviceName="compute.googleapis.com" OR 
                  protoPayload.serviceName="container.googleapis.com" OR
                  protoPayload.serviceName="storage.googleapis.com"'
```

#### 2. Monitor Service Account Usage
```bash
# Query audit logs for service account activity
gcloud logging read '
    protoPayload.authenticationInfo.principalEmail="ic-cli@project.iam.gserviceaccount.com"
    AND timestamp>="2024-01-01T00:00:00Z"
' --limit=100 --format=json
```

### Security Monitoring

#### 1. Unusual Activity Detection
```bash
# Monitor for unusual API patterns
# Create alerting policy for high API usage
gcloud alpha monitoring policies create \
    --policy-from-file=high-api-usage-policy.yaml
```

```yaml
# high-api-usage-policy.yaml
displayName: "High GCP API Usage"
conditions:
  - displayName: "High API request rate"
    conditionThreshold:
      filter: 'resource.type="gce_instance"'
      comparison: COMPARISON_GREATER_THAN
      thresholdValue: 1000
      duration: 300s
```

#### 2. Failed Authentication Monitoring
```bash
# Monitor failed authentication attempts
gcloud logging read '
    protoPayload.authenticationInfo.principalEmail="ic-cli@project.iam.gserviceaccount.com"
    AND protoPayload.status.code!=0
    AND timestamp>="2024-01-01T00:00:00Z"
' --limit=50
```

## 🛡️ Data Protection

### Sensitive Data Handling

#### 1. Output Filtering
```bash
# Configure output filtering for sensitive data
GCP_FILTER_SENSITIVE_DATA=true
GCP_REDACT_FIELDS="privateIpAddress,internalIpAddress,serviceAccountEmail"

# Custom filtering in .env
GCP_OUTPUT_FILTERS="email,key,secret,password,token"
```

#### 2. Logging Security
```bash
# Secure log configuration
LOG_LEVEL=INFO  # Avoid DEBUG in production
LOG_FORMAT=json
LOG_FILE=/secure/logs/ic-cli.log

# Set secure log file permissions
chmod 640 /secure/logs/ic-cli.log
chown ic-cli:log-readers /secure/logs/ic-cli.log
```

### Encryption

#### 1. Data in Transit
```bash
# Ensure HTTPS for all API calls
GCP_USE_HTTPS=true
GCP_SSL_VERIFY=true

# MCP server with TLS
MCP_GCP_ENDPOINT=https://mcp-server.company.com/gcp
MCP_GCP_SSL_CERT_PATH=/path/to/cert.pem
MCP_GCP_SSL_KEY_PATH=/path/to/key.pem
```

#### 2. Data at Rest
```bash
# Encrypt configuration files
gpg --symmetric --cipher-algo AES256 .env
# Creates .env.gpg

# Decrypt when needed
gpg --decrypt .env.gpg > .env.tmp
source .env.tmp
rm .env.tmp
```

## 🔧 Configuration Security

### Secure Configuration Management

#### 1. Environment-Specific Configurations
```bash
# Development environment
# .env.development
GCP_ENABLE_DEBUG=true
GCP_LOG_LEVEL=DEBUG
GCP_ENABLE_BILLING_API=false

# Production environment
# .env.production
GCP_ENABLE_DEBUG=false
GCP_LOG_LEVEL=INFO
GCP_ENABLE_BILLING_API=true
GCP_SSL_VERIFY=true
```

#### 2. Configuration Validation
```bash
#!/bin/bash
# validate-security-config.sh

# Check for insecure configurations
if [ "$GCP_SSL_VERIFY" != "true" ]; then
    echo "WARNING: SSL verification disabled"
fi

if [ -n "$GCP_SERVICE_ACCOUNT_KEY" ]; then
    echo "WARNING: Using inline service account key"
fi

if [ "$LOG_LEVEL" = "DEBUG" ] && [ "$ENVIRONMENT" = "production" ]; then
    echo "WARNING: Debug logging enabled in production"
fi

# Check file permissions
if [ -f ".env" ]; then
    PERMS=$(stat -c "%a" .env)
    if [ "$PERMS" != "600" ]; then
        echo "WARNING: .env file permissions should be 600, found: $PERMS"
    fi
fi
```

### Secrets Management

#### 1. External Secrets Management
```bash
# Use Google Secret Manager
gcloud secrets create ic-cli-service-account \
    --data-file=service-account.json

# Access secret in application
SECRET_VALUE=$(gcloud secrets versions access latest \
    --secret="ic-cli-service-account")
```

#### 2. Kubernetes Secrets (if running in K8s)
```yaml
# k8s-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: gcp-service-account
type: Opaque
data:
  service-account.json: <base64-encoded-key>
```

## 🚨 Incident Response

### Security Incident Procedures

#### 1. Key Compromise Response
```bash
#!/bin/bash
# key-compromise-response.sh

PROJECT_ID="your-project-id"
SA_EMAIL="ic-cli@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Responding to key compromise..."

# 1. Disable the service account
gcloud iam service-accounts disable $SA_EMAIL

# 2. Delete all keys
gcloud iam service-accounts keys list --iam-account=$SA_EMAIL \
    --format="value(name)" | while read key_id; do
    gcloud iam service-accounts keys delete $key_id \
        --iam-account=$SA_EMAIL --quiet
done

# 3. Remove IAM bindings
gcloud projects get-iam-policy $PROJECT_ID \
    --format=json > current-policy.json

# Remove service account from policy (manual step)
echo "Manual step: Remove $SA_EMAIL from current-policy.json"
echo "Then run: gcloud projects set-iam-policy $PROJECT_ID current-policy.json"

# 4. Create new service account
NEW_SA_NAME="ic-cli-service-account-$(date +%Y%m%d)"
gcloud iam service-accounts create $NEW_SA_NAME \
    --description="Replacement service account for IC CLI"

echo "Key compromise response completed"
echo "New service account: ${NEW_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
```

#### 2. Suspicious Activity Response
```bash
#!/bin/bash
# suspicious-activity-response.sh

# Check recent activity
gcloud logging read '
    protoPayload.authenticationInfo.principalEmail="ic-cli@project.iam.gserviceaccount.com"
    AND timestamp>="'$(date -d '1 hour ago' --iso-8601)'"
' --format=json > recent-activity.json

# Analyze activity patterns
echo "Recent API calls:"
jq -r '.[] | "\(.timestamp) \(.protoPayload.methodName) \(.protoPayload.resourceName)"' \
    recent-activity.json

# Check for unusual patterns
UNUSUAL_CALLS=$(jq '[.[] | select(.protoPayload.methodName | contains("delete") or contains("create"))] | length' recent-activity.json)

if [ "$UNUSUAL_CALLS" -gt 0 ]; then
    echo "WARNING: Found $UNUSUAL_CALLS potentially dangerous API calls"
    echo "Consider temporarily disabling the service account"
fi
```

## 📋 Security Checklist

### Pre-Deployment Security Checklist

- [ ] Service account created with minimal permissions
- [ ] Custom IAM roles defined and applied
- [ ] Service account keys stored securely (600 permissions)
- [ ] No inline keys in environment variables
- [ ] .env file excluded from version control
- [ ] HTTPS enabled for all external communications
- [ ] SSL verification enabled
- [ ] MCP server secured with proper network isolation
- [ ] Audit logging enabled
- [ ] Monitoring and alerting configured
- [ ] Key rotation schedule established
- [ ] Incident response procedures documented

### Runtime Security Checklist

- [ ] Regular key rotation performed
- [ ] Audit logs reviewed monthly
- [ ] No suspicious activity detected
- [ ] Configuration validated for security
- [ ] Dependencies updated regularly
- [ ] Access patterns monitored
- [ ] Error logs reviewed for security issues
- [ ] Performance metrics within normal ranges

### Compliance Checklist

- [ ] Data residency requirements met
- [ ] Encryption in transit and at rest
- [ ] Access controls documented
- [ ] Audit trail maintained
- [ ] Privacy requirements satisfied
- [ ] Regulatory compliance verified
- [ ] Security policies enforced
- [ ] Regular security assessments conducted

## 🔍 Security Testing

### Automated Security Testing

```bash
#!/bin/bash
# security-test.sh

echo "Running security tests..."

# Test 1: Check file permissions
echo "1. Checking file permissions..."
if [ -f ".env" ]; then
    PERMS=$(stat -c "%a" .env 2>/dev/null || stat -f "%A" .env 2>/dev/null)
    if [ "$PERMS" = "600" ]; then
        echo "✓ .env file permissions are secure"
    else
        echo "✗ .env file permissions are insecure: $PERMS"
    fi
fi

# Test 2: Check for inline secrets
echo "2. Checking for inline secrets..."
if grep -q "GCP_SERVICE_ACCOUNT_KEY=" .env 2>/dev/null; then
    echo "✗ Inline service account key found"
else
    echo "✓ No inline service account keys"
fi

# Test 3: Check SSL configuration
echo "3. Checking SSL configuration..."
if [ "$GCP_SSL_VERIFY" = "true" ]; then
    echo "✓ SSL verification enabled"
else
    echo "✗ SSL verification disabled"
fi

# Test 4: Check MCP server security
echo "4. Checking MCP server security..."
if [[ "$MCP_GCP_ENDPOINT" =~ ^https:// ]]; then
    echo "✓ MCP server uses HTTPS"
elif [[ "$MCP_GCP_ENDPOINT" =~ ^http://localhost ]]; then
    echo "⚠ MCP server uses HTTP (localhost only)"
else
    echo "✗ MCP server uses insecure HTTP"
fi

echo "Security test completed"
```

---

## 📞 Security Support

For security-related questions or to report security issues:

1. Review this security guide thoroughly
2. Check the [configuration guide](GCP_CONFIGURATION_GUIDE.md) for secure setup
3. Use the provided security scripts for validation
4. Report security vulnerabilities through proper channels

**Security Contact:** Follow responsible disclosure practices for security issues.

**Maintainer:** SangYun Kim (cruiser594@gmail.com)