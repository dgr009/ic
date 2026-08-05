# GCP Platform Documentation

This directory contains documentation for the GCP (Google Cloud Platform) integration in IC CLI.

## Available Guides

- [Installation Guide](../installation.md) - How to install and set up GCP integration
- [User & Usage Guide](../user_guide.md) - Complete command reference for GCP commands
- [Troubleshooting Guide](../troubleshooting.md) - Common issues and solutions

## Services Supported

- Compute Engine (Virtual machines)
- Cloud Storage (Buckets and lifecycle)
- VPC (Virtual Private Cloud and subnets)
- Cloud SQL (Managed databases)
- GKE (Google Kubernetes Engine)

## Quick Start Commands

```bash
# List Compute Engine instances
ic gcp compute info

# List Cloud Storage buckets
ic gcp storage info

# List VPC networks & subnets
ic gcp vpc info

# List GKE clusters
ic gcp gke info
```

For more details, refer to the [User Guide](../user_guide.md).