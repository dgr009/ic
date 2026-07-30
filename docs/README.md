# IC Documentation

This directory contains comprehensive documentation for the IC (Infrastructure Resource Management CLI) tool.

## Getting Started

- [Installation Guide](installation.md) - How to install IC CLI
- [User Guide](user_guide.md) - Complete user guide and tutorials
- [General Configuration](general/configuration.md) - General configuration management
- [Security](security.md) - Security best practices

## Platform-Specific Documentation

### AWS (Amazon Web Services)
- [AWS Installation](aws/installation.md) - Install and setup AWS integration
- [AWS Usage Guide](aws/README.md) - ECS, EKS, Fargate, S3, RDS, Security Groups (Ingress & Egress)

### GCP (Google Cloud Platform)
- [GCP Configuration Guide](gcp/GCP_CONFIGURATION_GUIDE.md) - Configure GCP credentials and settings
- [GCP Security Best Practices](gcp/GCP_SECURITY_BEST_PRACTICES.md) - Security guidelines for GCP
- [GCP Platform Overview](gcp/README.md) - Compute, Storage, VPC, GKE, and Cloud SQL

### OCI (Oracle Cloud Infrastructure)
- [OCI Installation](oci/installation.md) - Install and setup OCI integration
- [OCI Usage Guide](oci/README.md) - VM, VCN, LB, NSG, Volumes, and IAM Policies

### CloudFlare
- [CloudFlare Integration Guide](../src/ic/platforms/cloudflare/README.md) - Complete CloudFlare integration guide
- [CloudFlare Configuration Examples](cloudflare_configuration_example.md) - Configuration examples and use cases

### SSH Server Management
- [SSH Configuration Guide](ssh/configuration.md) - Configure SSH key directories, rules, and connection options
- [SSH Integration Guide](../src/ic/platforms/ssh/README.md) - Server discovery and connection management

## Quick Reference

### Platform Commands
```bash
# AWS Services
ic aws ec2 info
ic aws sg info --ingress
ic aws sg info --egress -o tree
ic aws s3 info

# GCP Services
ic gcp compute info
ic gcp storage info
ic gcp vpc info
ic gcp gke info
ic gcp sql info

# OCI Services
ic oci vm info
ic oci vcn info
ic oci lb info

# CloudFlare
ic cf zone info
ic cf dns info

# SSH Server Management
ic ssh info
```

### Configuration Commands
```bash
# Initialize configuration
ic config init

# Validate configuration
ic config validate

# Show configuration
ic config show
```

---

**Last Updated**: 2026  
**Maintainer**: IC CLI Team