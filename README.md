# IC CLI Tool (Infrastructure Commander)

[![PyPI version](https://badge.fury.io/py/ic-code.svg)](https://badge.fury.io/py/ic-code)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive, production-grade Infrastructure Command Line Interface tool for managing multi-cloud infrastructure and server components across multiple platforms. IC CLI provides unified access to **AWS**, **GCP**, **Oracle Cloud Infrastructure (OCI)**, **CloudFlare**, and **SSH** server management with rich progress indicators and secure configuration management.

---

## ✨ Key Features

- **🚀 Multi-Cloud Support**: AWS, GCP, OCI, CloudFlare, and SSH server management
- **📊 Rich Progress Bars**: Real-time progress indicators for all long-running operations across accounts and regions
- **🔒 Secure Configuration**: Modern YAML-based configuration (`~/.ic/config/`) with separate secrets management
- **🌍 Multi-Account / Multi-Region**: Concurrent querying across multiple cloud accounts and regions
- **🎨 Beautiful Terminal UI**: Rich terminal output with tables, colors, JSON formatting, and tree diagrams
- **⚡ High Performance**: Optimized async and concurrent execution for fast resource discovery
- **🛡️ Security First**: Built-in credential masking, secret scanning, and pre-commit hook support

---

## 📦 Supported Platforms & Services

### 1. 🟧 AWS Services (Production Ready)
- **Compute**: EC2 instances, ECS services/tasks, EKS clusters/nodes/pods, Fargate profiles
- **Storage & DB**: S3 buckets (with tagging compliance checks), RDS instances & clusters
- **Networking**: VPC, Subnets, Gateways, Load Balancers (ALB/NLB), Security Groups (with Ingress & Egress rule analysis & tree view), VPN connections
- **Integrations**: CloudFront distributions, MSK Kafka brokers, CodePipeline build/deploy status, Profile management

### 2. 🟩 GCP Services (Production Ready)
- **Compute Engine**: VM instances with status, zone, and network interface details
- **Cloud Storage**: Bucket lists, location, and storage class information
- **VPC Network**: Subnets, routes, and firewall rule visibility
- **GKE**: Kubernetes Engine clusters and node pool configurations
- **Cloud SQL**: Database instances, engines, and status

### 3. 🟥 Oracle Cloud Infrastructure (OCI) (Production Ready)
- **Compute & Containers**: VM instances, Container instances (ACI)
- **Networking**: VCN, Subnets, Load Balancers, Network Security Groups (NSG)
- **Storage**: Block Volumes, Object Storage buckets
- **IAM & Cost**: Compartment hierarchy, IAM Policy search/validation, Cost usage & billing credits

### 4. 🟧 CloudFlare (Production Ready)
- **DNS & Zones**: Zone listings, DNS record management, and account filtering

### 5. 🟦 SSH Server Management (Production Ready)
- **Discovery**: Automatic server registration, connection verification, and security filtering

---

## 📦 Installation

### From PyPI (Recommended)

```bash
# Install the latest stable version (v1.2.6+)
pip install ic-code

# Verify installation
ic --version
ic --help
```

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/dgr009/ic.git
cd ic

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies and local editable package
pip install -e .

# Verify installation
ic --version
```

---

## ⚙️ Configuration Setup

IC CLI uses a modern two-file configuration system located in `~/.ic/config/` for security:

```
~/.ic/config/
├── default.yaml        # Non-sensitive default settings
└── secrets.yaml        # Sensitive API keys, tokens, and profiles
```

### 1. Initialize Configuration

```bash
# Guided interactive configuration setup
ic config init

# Or generate template for specific clouds
ic config init --template aws
ic config init --template multi-cloud
```

### 2. Configure Credentials (`~/.ic/config/secrets.yaml`)

```yaml
# AWS Configuration
aws:
  accounts:
    - "123456789012"
  profiles:
    default: "my-aws-profile"
  regions:
    - "ap-northeast-2"
    - "us-east-1"

# GCP Configuration
gcp:
  project_id: "my-gcp-project-id"
  credentials_file: "~/.config/gcloud/application_default_credentials.json"
  regions:
    - "asia-northeast3"
    - "us-central1"

# Oracle Cloud Infrastructure (OCI)
oci:
  config_file: "~/.oci/config"
  profile: "DEFAULT"
  compartments:
    - "ocid1.compartment.oc1..example"

# CloudFlare Configuration
cloudflare:
  api_token: "your-cloudflare-api-token"

# SSH Configuration
ssh:
  key_dir: "~/.ssh"
  skip_prefixes:
    - "bastion"
    - "jump"
```

### 3. Manage & Validate Config

```bash
# Show configuration (sensitive fields masked automatically)
ic config show

# Validate configuration structure and paths
ic config validate
```

---

## 🚀 Command Usage Examples

### AWS Commands

```bash
# List EC2 instances across configured regions
ic aws ec2 info

# Security Group Info (Shows Ingress & Egress rules by default)
ic aws sg info

# Filter Security Groups for Ingress or Egress rules only
ic aws sg info --ingress    # Show Ingress rules only
ic aws sg info --egress     # Show Egress rules only

# Render Security Groups in visual tree structure with direction arrows (← Ingress, → Egress)
ic aws sg info -o tree

# S3 Bucket details and tag validation
ic aws s3 info
ic aws s3 tag_check

# EKS & ECS Cluster info
ic aws eks info
ic aws ecs info
```

### GCP Commands

```bash
# Compute Engine VM instances
ic gcp compute info

# Cloud Storage buckets
ic gcp storage info

# VPC networks and subnets
ic gcp vpc info

# GKE Clusters
ic gcp gke info

# Cloud SQL databases
ic gcp sql info
```

### OCI Commands

```bash
# Compute VM instances
ic oci vm info

# Virtual Cloud Networks
ic oci vcn info

# Load Balancers & Network Security Groups
ic oci lb info
ic oci nsg info

# Storage & Cost usage
ic oci volume info
ic oci cost usage
```

### CloudFlare & SSH Commands

```bash
# CloudFlare Zones and DNS
ic cf zone info
ic cf dns info

# SSH Server discovery
ic ssh info
```

### Security & Hook Commands

```bash
# Scan codebase for hardcoded secrets
ic security scan

# Install pre-commit security hooks
ic security install-hooks
```

---

## 🧪 Testing & Validation

```bash
# Run unit & integration test suites
pytest tests/unit tests/integration

# Run End-to-End CLI validation
python tests/validation/end_to_end_cli_validation.py
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
