# OCI Platform Documentation

This directory contains documentation for the OCI (Oracle Cloud Infrastructure) integration in IC CLI.

## Available Guides

- [Installation Guide](../installation.md) - How to install and set up OCI integration
- [User & Usage Guide](../user_guide.md) - Complete command reference for OCI commands
- [Troubleshooting Guide](../troubleshooting.md) - Common issues and solutions

## Services Supported

- Compute (VM Instances and Autonomous Container Instances)
- Object Storage & Block Volumes
- VCN & Subnets (Virtual Cloud Network)
- Network Security Groups (NSG)
- Load Balancers
- IAM Compartment hierarchy & Cost Management

## Quick Start Commands

```bash
# List Compute VM instances
ic oci vm info

# List Virtual Cloud Networks
ic oci vcn info

# List Network Security Groups
ic oci nsg info

# Show Cost & Billing usage
ic oci cost usage
```

For more details, refer to the [User Guide](../user_guide.md).