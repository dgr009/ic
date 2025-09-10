# IC CLI Dependency Management

This document describes the comprehensive dependency management system implemented for IC CLI, ensuring Python 3.9-3.12 compatibility and reliable package installation.

## Overview

The IC CLI dependency management system provides:

- **Automatic dependency validation** on CLI startup
- **Clear error messages** for missing or incompatible packages
- **Python version compatibility** checking (3.9-3.12)
- **Comprehensive testing tools** for dependency validation
- **Consistent package versions** across requirements.txt, pyproject.toml, and setup.py

## Python Version Support

| Python Version | Support Status | Notes |
|----------------|----------------|-------|
| 3.8 and below | ❌ Not Supported | Minimum version is 3.9 |
| 3.9 | ✅ Supported | Minimum supported version |
| 3.10 | ✅ Fully Supported | Tested and validated |
| 3.11 | ✅ Recommended | Optimal performance (3.11.13) |
| 3.12 | ✅ Fully Supported | Latest tested version |
| 3.13+ | ⚠️ Not Tested | May work but not guaranteed |

## Dependency Categories

### Core Dependencies
Required for basic IC CLI functionality:
- `boto3` - AWS SDK
- `requests` - HTTP library
- `rich` - Terminal formatting
- `PyYAML` - YAML parsing
- `paramiko` - SSH client
- `python-dotenv` - Environment variables
- `cryptography` - Security functions
- `tqdm` - Progress bars
- `jsonschema` - JSON validation
- `pydantic` - Data validation

### Platform-Specific Dependencies
Optional dependencies for specific cloud platforms:

#### AWS
- `awscli` - AWS CLI tools
- `kubernetes` - Kubernetes client

#### OCI (Oracle Cloud)
- `oci` - OCI SDK

#### Google Cloud Platform
- `google-cloud-*` packages
- `google-auth` - Authentication

#### Azure
- `azure-identity` - Authentication
- `azure-mgmt-*` - Management SDKs

#### Configuration System
- `watchdog` - File monitoring
- `cerberus` - Schema validation

## Validation Tools

### Automatic Validation
The CLI automatically validates dependencies on startup:

```bash
ic --help  # Shows dependency errors if any exist
```

### Manual Validation Scripts

#### Basic Dependency Validation
```bash
python scripts/validate_dependencies.py
```

Options:
- `--platforms aws oci` - Validate specific platforms
- `--install-missing` - Automatically install missing packages
- `--test-requirements` - Test requirements.txt installation
- `--quiet` - Suppress detailed output

#### Comprehensive Compatibility Testing
```bash
python scripts/test_dependency_compatibility.py --report
```

Tests:
- Python version compatibility
- Requirements.txt installation
- Dependency conflicts
- Core package imports
- Version constraints

### Integration with CLI
The main CLI includes dependency validation that:
- Checks Python version compatibility
- Validates core dependencies
- Provides clear error messages
- Suggests installation commands
- Links to documentation

## Configuration Files

### requirements.txt
Production dependencies with version ranges for Python 3.9-3.12 compatibility:
```
boto3>=1.26.0,<2.0.0
requests>=2.28.0,<3.0.0
rich>=12.0.0,<15.0.0
# ... etc
```

### pyproject.toml
Modern Python packaging configuration:
```toml
requires-python = ">=3.9,<3.13"
dependencies = [
    "boto3>=1.26.0,<2.0.0",
    # ... aligned with requirements.txt
]
```

### setup.py
Backward compatibility configuration:
```python
python_requires=">=3.9,<3.13"
install_requires=[
    "boto3>=1.26.0,<2.0.0",
    # ... aligned with requirements.txt
]
```

## Version Constraint Strategy

### Core Principles
1. **Minimum versions** ensure required features are available
2. **Maximum versions** prevent breaking changes
3. **Compatibility ranges** accommodate existing installations
4. **Security updates** are allowed within ranges

### Constraint Examples
```
# Flexible range for active development
boto3>=1.26.0,<2.0.0

# Strict range for compatibility
PyYAML>=6.0,<=6.0.2

# Security-focused range
cryptography>=3.4.8,<46.0.0
```

## Troubleshooting

### Common Issues

#### Python Version Too Old
```
❌ Python 3.8.10 is not supported. Minimum required version is 3.9
```
**Solution**: Upgrade Python to 3.9 or newer

#### Missing Dependencies
```
❌ Missing packages (2):
  - PyYAML
  - python-dotenv
```
**Solution**: Run `pip install PyYAML>=6.0 python-dotenv>=0.19.0`

#### Version Conflicts
```
❌ cryptography v45.0.7 (required: >=3.4.8,<44.0.0)
```
**Solution**: Update version constraints or downgrade package

#### Import Errors
```
❌ Package not found: No module named 'yaml'
```
**Solution**: Install missing package or check import name mapping

### Automated Fixes
```bash
# Install missing dependencies automatically
python scripts/validate_dependencies.py --install-missing

# Reinstall all dependencies
pip install --upgrade -r requirements.txt

# Force reinstall with no cache
pip install --no-cache-dir --force-reinstall -r requirements.txt
```

## Development Guidelines

### Adding New Dependencies
1. Add to `requirements.txt` with version range
2. Update `pyproject.toml` dependencies
3. Update `setup.py` install_requires
4. Test with `python scripts/validate_dependencies.py`
5. Update dependency validator if needed

### Version Updates
1. Test compatibility across Python 3.9-3.12
2. Check for dependency conflicts
3. Update all three configuration files
4. Run comprehensive compatibility tests
5. Update documentation

### Testing Dependencies
```bash
# Test specific platforms
python scripts/validate_dependencies.py --platforms aws oci

# Test installation
python scripts/validate_dependencies.py --test-requirements

# Full compatibility report
python scripts/test_dependency_compatibility.py --report
```

## CI/CD Integration

The dependency validation system is designed for CI/CD environments:

- **No external dependencies** for core validation
- **Graceful handling** of missing configuration files
- **Clear exit codes** for automation
- **Detailed logging** for debugging
- **Mock-friendly** for testing environments

### GitHub Actions Example
```yaml
- name: Validate Dependencies
  run: |
    python scripts/validate_dependencies.py --quiet
    python scripts/test_dependency_compatibility.py
```

## Security Considerations

### Version Pinning
- **Security updates** are allowed within version ranges
- **Breaking changes** are prevented by maximum versions
- **Known vulnerabilities** are avoided by minimum versions

### Validation Security
- **No network access** required for basic validation
- **Local package checking** only
- **Safe error handling** prevents information leakage

## Performance Optimization

### Lazy Loading
- Optional dependencies are not imported unless needed
- Platform-specific modules are loaded on demand
- Validation is cached where possible

### Minimal Core
- Core dependencies are kept minimal
- Optional features use optional dependencies
- Installation time is optimized

## Future Enhancements

### Planned Improvements
1. **Dependency caching** for faster validation
2. **Platform detection** for automatic dependency selection
3. **Version recommendation** system
4. **Conflict resolution** suggestions
5. **Performance monitoring** for dependency loading

### Compatibility Roadmap
- **Python 3.13** support when released
- **Package ecosystem** updates
- **Security vulnerability** monitoring
- **Performance optimization** for large installations