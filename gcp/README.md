# GCP Services Integration

This module provides comprehensive Google Cloud Platform (GCP) service integration for the IC CLI tool. It supports 10 core GCP services with unified authentication, filtering, and output formatting capabilities.

## 🚀 Supported Services

| Service | Description | Key Features |
|---------|-------------|--------------|
| **Compute Engine** | Virtual machine instances | Instance metadata, disks, network interfaces, labels |
| **VPC Networks** | Virtual networks and subnets | Network topology, firewall rules, peering connections |
| **Google Kubernetes Engine (GKE)** | Kubernetes clusters | Cluster configuration, node pools, add-ons |
| **Cloud Storage** | Object storage buckets | Bucket policies, lifecycle rules, versioning |
| **Cloud SQL** | Managed database instances | Backup settings, replicas, maintenance windows |
| **Cloud Functions** | Serverless functions | Runtime configuration, triggers, environment variables |
| **Cloud Run** | Containerized services | Scaling settings, revisions, traffic allocation |
| **Load Balancing** | HTTP(S), TCP, UDP load balancers | Frontend/backend config, health checks, SSL certificates |
| **Firewall Rules** | Network security rules | Priority, direction, source/target ranges |
| **Billing & Cost** | Cost management and budgets | Spending analysis, budget alerts, service breakdown |

## 🔐 Authentication Methods

The GCP integration supports multiple authentication methods with the following priority:

### 1. MCP Server Authentication (Recommended)
```bash
# Enable MCP server integration
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp
MCP_GCP_AUTH_METHOD=service_account
```

**Benefits:**
- Centralized credential management
- Enhanced security through controlled API access
- Consistent authentication across all cloud platforms
- Automatic credential validation and refresh
- Standardized error handling and retry logic

### 2. Service Account Key (Fallback)
```bash
# JSON string in environment variable
export GCP_SERVICE_ACCOUNT_KEY='{"type": "service_account", "project_id": "..."}'

# Or path to JSON file
export GCP_SERVICE_ACCOUNT_KEY_PATH="/path/to/service-account.json"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### 3. Application Default Credentials (Fallback)
```bash
# Set up ADC
gcloud auth application-default login

# For compute instances with attached service accounts
# ADC is automatically available
```

### 4. gcloud CLI Authentication (Fallback)
```bash
# User authentication for development
gcloud auth login

# Set default project
gcloud config set project my-project-id
```

## 🛠️ Configuration

### Environment Variables

#### Project Configuration
```bash
# Specify target projects (comma-separated)
GCP_PROJECTS=project-1,project-2,project-3

# Default project for single-project operations
GCP_DEFAULT_PROJECT=my-default-project
```

#### Regional Configuration
```bash
# Target regions for regional resources
GCP_REGIONS=us-central1,us-east1,asia-northeast1

# Target zones for zonal resources
GCP_ZONES=us-central1-a,us-central1-b,asia-northeast1-a
```

#### Performance Tuning
```bash
# Maximum concurrent workers for parallel processing
GCP_MAX_WORKERS=10

# Request timeout in seconds
GCP_REQUEST_TIMEOUT=30

# Maximum retry attempts for failed requests
GCP_RETRY_ATTEMPTS=3

# Prefer MCP server over direct API access
GCP_PREFER_MCP=true
```

#### Service-Specific Configuration
```bash
# Enable/disable specific APIs
GCP_ENABLE_COMPUTE_API=true
GCP_ENABLE_CONTAINER_API=true
GCP_ENABLE_STORAGE_API=true
GCP_ENABLE_SQLADMIN_API=true
GCP_ENABLE_CLOUDFUNCTIONS_API=true
GCP_ENABLE_RUN_API=true
GCP_ENABLE_BILLING_API=true
```

## 📋 Usage Examples

### Basic Service Queries

#### Compute Engine
```bash
# List all instances across configured projects
ic gcp compute info

# Filter by specific project
ic gcp compute info --project my-project

# Filter by zone and instance name
ic gcp compute info --zone us-central1-a --name web-server

# Output in different formats
ic gcp compute info --output json
ic gcp compute info --output yaml
ic gcp compute info --output tree
```

#### VPC Networks
```bash
# List all VPC networks
ic gcp vpc info

# Filter by region and network name
ic gcp vpc info --region us-central1 --name production-vpc

# Tree view showing network hierarchy
ic gcp vpc info --output tree
```

#### Google Kubernetes Engine
```bash
# List all GKE clusters
ic gcp gke info

# Filter by specific cluster and location
ic gcp gke info --cluster production --location us-central1-a

# Show detailed cluster configuration
ic gcp gke info --cluster my-cluster --output yaml
```

#### Cloud Storage
```bash
# List all storage buckets
ic gcp storage info

# Filter by bucket name
ic gcp storage info --bucket my-data-bucket

# Show bucket details with policies
ic gcp storage info --bucket my-bucket --output tree
```

#### Cloud SQL
```bash
# List all SQL instances
ic gcp sql info

# Filter by instance name
ic gcp sql info --instance prod-database

# Show instance configuration and replicas
ic gcp sql info --instance my-db --output yaml
```

#### Cloud Functions
```bash
# List all functions
ic gcp functions info

# Filter by region and function name
ic gcp functions info --region us-central1 --function my-function

# Show function triggers and configuration
ic gcp functions info --function my-func --output tree
```

#### Cloud Run
```bash
# List all Cloud Run services
ic gcp run info

# Filter by service name and region
ic gcp run info --service my-api --region us-central1

# Show service revisions and traffic split
ic gcp run info --service my-service --output yaml
```

#### Load Balancing
```bash
# List all load balancers
ic gcp lb info

# Filter by load balancer name
ic gcp lb info --lb-name production-lb

# Show backend services and health checks
ic gcp lb info --lb-name my-lb --output tree
```

#### Firewall Rules
```bash
# List all firewall rules
ic gcp firewall info

# Filter by rule name
ic gcp firewall info --rule-name allow-https

# Show rules organized by network
ic gcp firewall info --output tree
```

#### Billing & Cost
```bash
# Show current billing information
ic gcp billing info

# Filter by date range
ic gcp billing info --start-date 2024-01-01 --end-date 2024-01-31

# Show cost breakdown by service
ic gcp billing info --output tree
```

### Advanced Usage

#### Multi-Service Queries
```bash
# Query multiple services simultaneously
ic gcp compute,vpc,gke info --project production

# All services with tree output
ic gcp compute,vpc,gke,storage,sql,functions,run,lb,firewall,billing info --output tree

# Specific services with JSON output for automation
ic gcp compute,storage,sql info --output json > gcp-resources.json
```

#### Multi-Project Operations
```bash
# Query across multiple projects
ic gcp compute info --project project-1,project-2,project-3

# All configured projects (from GCP_PROJECTS env var)
ic gcp vpc info

# Override project configuration
GCP_PROJECTS=dev-project,staging-project ic gcp gke info
```

#### Regional and Zonal Filtering
```bash
# Specific regions
ic gcp compute info --region us-central1,us-east1

# Specific zones
ic gcp compute info --zone us-central1-a,us-central1-b

# Regional services with zone filtering
ic gcp gke info --location us-central1-a
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### Authentication Errors

**Issue**: `Authentication failed: Could not load credentials`
```bash
# Solution 1: Check MCP server configuration
curl -f http://localhost:8080/gcp/health

# Solution 2: Set up Application Default Credentials
gcloud auth application-default login

# Solution 3: Use service account key
export GCP_SERVICE_ACCOUNT_KEY_PATH="/path/to/key.json"
```

**Issue**: `Permission denied for project`
```bash
# Check project access
gcloud projects list

# Verify service account permissions
gcloud projects get-iam-policy PROJECT_ID
```

#### API Errors

**Issue**: `API not enabled: compute.googleapis.com`
```bash
# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable container.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbilling.googleapis.com
```

**Issue**: `Quota exceeded for quota metric`
```bash
# Check current quotas
gcloud compute project-info describe --project PROJECT_ID

# Request quota increase through Google Cloud Console
# https://console.cloud.google.com/iam-admin/quotas
```

#### Network and Timeout Errors

**Issue**: `Request timeout after 30 seconds`
```bash
# Increase timeout
export GCP_REQUEST_TIMEOUT=60

# Reduce concurrent workers
export GCP_MAX_WORKERS=5
```

**Issue**: `Connection refused to MCP server`
```bash
# Check MCP server status
curl -f http://localhost:8080/health

# Disable MCP and use direct API access
export MCP_GCP_ENABLED=false
```

#### Data and Filtering Issues

**Issue**: `No resources found`
```bash
# Check project configuration
echo $GCP_PROJECTS

# Verify project access
gcloud projects list --filter="projectId:($GCP_PROJECTS)"

# Check regional filters
echo $GCP_REGIONS
```

**Issue**: `Invalid project ID format`
```bash
# Verify project ID format (lowercase, numbers, hyphens only)
gcloud projects list --format="value(projectId)"
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
ic gcp compute info -v

# Check logs
tail -f logs/ic_$(date +%Y%m%d).log
```

## 🔒 Security Best Practices

### Credential Management

1. **Use MCP Server** (Recommended)
   - Centralized credential management
   - Reduced credential exposure
   - Automatic credential rotation support

2. **Service Account Keys**
   - Store keys securely (not in version control)
   - Use least-privilege principle
   - Rotate keys regularly
   - Monitor key usage

3. **Application Default Credentials**
   - Preferred for compute instances
   - Automatic credential discovery
   - No manual key management

### IAM Permissions

#### Minimum Required Permissions

**Compute Engine:**
```json
{
  "bindings": [
    {
      "role": "roles/compute.viewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**VPC Networks:**
```json
{
  "bindings": [
    {
      "role": "roles/compute.networkViewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**GKE:**
```json
{
  "bindings": [
    {
      "role": "roles/container.clusterViewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Cloud Storage:**
```json
{
  "bindings": [
    {
      "role": "roles/storage.objectViewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Cloud SQL:**
```json
{
  "bindings": [
    {
      "role": "roles/cloudsql.viewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Cloud Functions:**
```json
{
  "bindings": [
    {
      "role": "roles/cloudfunctions.viewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Cloud Run:**
```json
{
  "bindings": [
    {
      "role": "roles/run.viewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Load Balancing:**
```json
{
  "bindings": [
    {
      "role": "roles/compute.loadBalancerServiceUser",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

**Billing:**
```json
{
  "bindings": [
    {
      "role": "roles/billing.viewer",
      "members": ["serviceAccount:your-sa@project.iam.gserviceaccount.com"]
    }
  ]
}
```

### Network Security

1. **API Endpoints**
   - Use HTTPS for all API calls
   - Validate SSL certificates
   - Implement proper timeout handling

2. **MCP Server Security**
   - Use secure communication protocols
   - Implement authentication for MCP endpoints
   - Monitor MCP server access logs

3. **Data Privacy**
   - No sensitive data in logs
   - Configurable output filtering
   - Secure credential storage

## 🚀 Performance Optimization

### Parallel Processing

The GCP integration uses parallel processing for optimal performance:

```bash
# Configure worker threads
export GCP_MAX_WORKERS=10

# Monitor performance
time ic gcp compute,vpc,gke info --project project-1,project-2,project-3
```

### Caching Strategy

- **Credential Caching**: Automatic credential reuse within session
- **Project Metadata**: Cached project information with TTL
- **API Response Caching**: Optional caching for static data (regions, zones)

### Memory Management

- **Streaming Processing**: Large result sets processed in chunks
- **Pagination Handling**: Automatic pagination for API responses
- **Garbage Collection**: Optimized for long-running operations

## 🔄 MCP Server Integration

### Benefits of MCP Integration

1. **Centralized Authentication**
   - Single point of credential management
   - Automatic credential validation and refresh
   - Cross-platform authentication consistency

2. **Enhanced Security**
   - Reduced credential exposure
   - Centralized access control
   - Audit logging for all operations

3. **Improved Performance**
   - Connection pooling and reuse
   - Intelligent caching strategies
   - Optimized API call patterns

4. **Standardized Operations**
   - Consistent error handling across services
   - Unified retry logic with exponential backoff
   - Standardized data transformation

### MCP Configuration

#### Basic Setup
```bash
# Enable MCP integration
MCP_GCP_ENABLED=true
MCP_GCP_ENDPOINT=http://localhost:8080/gcp

# Authentication method for MCP server
MCP_GCP_AUTH_METHOD=service_account  # or adc, gcloud
```

#### Advanced Configuration
```bash
# MCP connection settings
MCP_GCP_TIMEOUT=30
MCP_GCP_RETRY_ATTEMPTS=3
MCP_GCP_CONNECTION_POOL_SIZE=10

# Fallback behavior
MCP_GCP_FALLBACK_ENABLED=true
MCP_GCP_FALLBACK_TIMEOUT=10
```

### MCP vs Direct API Access

| Feature | MCP Server | Direct API |
|---------|------------|------------|
| **Authentication** | Centralized | Per-service |
| **Caching** | Intelligent | Basic |
| **Error Handling** | Standardized | Service-specific |
| **Performance** | Optimized | Standard |
| **Security** | Enhanced | Standard |
| **Maintenance** | Centralized | Distributed |

## 📊 Output Formats

### Table Format (Default)
```bash
ic gcp compute info --output table
```
- Clean, readable columns
- Color-coded status indicators
- Truncated values for readability

### Tree Format
```bash
ic gcp vpc info --output tree
```
- Hierarchical display
- Shows relationships between resources
- Expandable sections for complex data

### JSON Format
```bash
ic gcp storage info --output json
```
- Complete data structure
- Machine-readable format
- Suitable for automation and scripting

### YAML Format
```bash
ic gcp gke info --output yaml
```
- Human-readable structure
- Preserves data types
- Good for configuration files

## 🧪 Testing and Validation

### Unit Tests
```bash
# Run GCP-specific unit tests
python -m pytest tests/test_gcp_*.py -v

# Test with mock data
python -m pytest tests/test_gcp_mock_data.py
```

### Integration Tests
```bash
# Run integration tests with real GCP APIs
python -m pytest tests/integration/test_gcp_integration.py -v

# Test MCP server integration
python -m pytest tests/test_mcp_gcp_connector.py -v
```

### Performance Tests
```bash
# Run performance benchmarks
python -m pytest tests/performance/test_gcp_performance.py -v

# Benchmark parallel processing
python tests/performance/benchmark_runner.py --service gcp
```

## 📈 Monitoring and Logging

### Structured Logging
```bash
# Enable structured logging
export LOG_FORMAT=json
export LOG_LEVEL=INFO

# View logs
tail -f logs/ic_$(date +%Y%m%d).log | jq '.'
```

### Performance Metrics
- API call duration and success rates
- Parallel processing efficiency
- Memory usage and resource consumption
- MCP server connection health

### Health Checks
```bash
# Check GCP service health
ic gcp compute info --project test-project --dry-run

# Validate MCP server connection
curl -f http://localhost:8080/gcp/health
```

## 🔮 Future Enhancements

### Planned Features
- **Additional Services**: Cloud Pub/Sub, Cloud Datastore, Cloud Memorystore
- **Advanced Filtering**: Label-based filtering, resource state filtering
- **Export Capabilities**: Excel, CSV export for reporting
- **Real-time Monitoring**: Resource change tracking and alerts
- **Cost Optimization**: Resource utilization analysis and recommendations

### Integration Roadmap
- **Terraform Integration**: Import existing resources to Terraform
- **CI/CD Integration**: Automated resource validation in pipelines
- **Alerting System**: Integration with monitoring and alerting platforms
- **Multi-Cloud Comparison**: Cross-platform resource comparison and migration planning

---

## 📞 Support and Contributing

### Getting Help
- Check the [troubleshooting section](#troubleshooting) for common issues
- Review the [main README.md](../README.md) for general usage
- Open an issue on the project repository for bugs or feature requests

### Contributing
- Follow the existing code patterns and conventions
- Add comprehensive tests for new features
- Update documentation for any changes
- Ensure MCP integration compatibility

### Maintainer
- **SangYun Kim** (cruiser594@gmail.com)
- License: MIT