# OCI Installation Guide

This guide covers the installation and initial setup of OCI (Oracle Cloud Infrastructure) integration for the IC CLI tool.

## Prerequisites

- Python 3.9 or higher
- IC CLI tool installed
- OCI account with appropriate permissions
- Internet access to OCI APIs

## Installation Steps

### 1. Install Dependencies

```bash
# Install the IC CLI tool if not already installed
pip install ic-code

# Verify OCI support is available
ic oci --help        # Should show OCI commands
```

### 2. Verify Installation

```bash
# Test OCI module imports
python -c "from oci_module.common.utils import OCIClient; print('OCI client: OK')"

# Verify core dependencies
python -c "import oci, requests, yaml; print('OCI dependencies: OK')"
```

### 3. Initial Configuration

After installation, you'll need to configure your OCI credentials. See the [Configuration Guide](configuration.md) for detailed instructions.

## Platform-Specific Requirements

### System Requirements

- Operating System: Linux, macOS, or Windows
- Memory: Minimum 512MB RAM
- Disk Space: 100MB free space

### OCI Requirements

- Valid OCI account
- API access enabled
- Required permissions for services you plan to use
- OCI CLI configuration (optional but recommended)

## Troubleshooting Installation

### Common Issues

#### Issue: Command not found
```bash
ic: oci: command not found
```
**Solution**: Ensure OCI integration is properly installed and in your PATH.

#### Issue: Missing dependencies
```bash
ModuleNotFoundError: No module named 'oci'
```
**Solution**: Install missing dependencies using pip.

### Getting Help

If you encounter issues during installation:

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Verify all prerequisites are met
3. Check the main project documentation
4. Report issues on the project repository

## Next Steps

After successful installation:

1. Configure your OCI credentials using the [Configuration Guide](configuration.md)
2. Learn how to use OCI commands in the [Usage Guide](usage.md)
3. Test your setup with basic commands