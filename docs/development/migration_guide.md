# IC CLI Migration Guide

## Overview

This guide provides instructions for migrating code and configurations when the IC CLI project structure changes. It covers the recent major migration from root-level platform directories to the consolidated `src/ic/platforms/` structure and provides patterns for future migrations.

## Recent Migration (2024): Platform Consolidation

### What Changed

The project underwent a major restructuring where platform modules were moved from root-level directories to a consolidated structure:

**Before (Legacy Structure):**
```
aws/
oci_module/
azure_module/
ncp/
ncpgov/
gcp/
cf/
ssh/
common/
```

**After (New Structure):**
```
src/ic/
├── platforms/
│   ├── aws/
│   ├── oci/          # renamed from oci_module
│   ├── azure/        # renamed from azure_module
│   ├── ncp/
│   ├── ncpgov/
│   ├── gcp/
│   ├── cf/
│   └── ssh/
├── config/
├── core/
└── security/
src/common/           # moved from root level
```

### Migration Steps Completed

1. **Platform Module Relocation**: All platform modules moved to `src/ic/platforms/`
2. **Module Renaming**: Removed unnecessary `_module` suffixes
3. **Import Path Updates**: Updated all import statements to use new paths
4. **CLI Integration Fix**: Updated CLI discovery and routing
5. **Package Configuration**: Updated `pyproject.toml` and `setup.py`
6. **Test Updates**: Updated all test imports and references

## Import Migration Patterns

### Legacy Import Patterns (Deprecated)

```python
# Old patterns - DO NOT USE
from aws.ec2 import info
from oci_module.vm import info
from azure_module.vm import info
from ncp.ec2 import info
from common.utils import format_output
```

### New Import Patterns (Current)

```python
# New patterns - USE THESE
try:
    from src.ic.platforms.aws.ec2 import info as aws_ec2_info
    from src.ic.platforms.oci.vm import info as oci_vm_info
    from src.ic.platforms.azure.vm import info as azure_vm_info
    from src.ic.platforms.ncp.ec2 import info as ncp_ec2_info
    from src.common.utils import format_output
except ImportError:
    # Fallback for installed package
    from ic.platforms.aws.ec2 import info as aws_ec2_info
    from ic.platforms.oci.vm import info as oci_vm_info
    from ic.platforms.azure.vm import info as azure_vm_info
    from ic.platforms.ncp.ec2 import info as ncp_ec2_info
    from common.utils import format_output
```

## Automated Migration Tools

### Import Update Script

A script was created to automatically update import statements:

```python
# fix_import_syntax.py - Available in project root
import re
import os
from pathlib import Path

def update_imports_in_file(file_path):
    """Update import statements in a Python file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define replacement patterns
    replacements = [
        (r'from aws\.', 'from src.ic.platforms.aws.'),
        (r'from oci_module\.', 'from src.ic.platforms.oci.'),
        (r'from azure_module\.', 'from src.ic.platforms.azure.'),
        (r'from ncp\.', 'from src.ic.platforms.ncp.'),
        (r'from ncpgov\.', 'from src.ic.platforms.ncpgov.'),
        (r'from gcp\.', 'from src.ic.platforms.gcp.'),
        (r'from cf\.', 'from src.ic.platforms.cf.'),
        (r'from ssh\.', 'from src.ic.platforms.ssh.'),
        (r'from common\.', 'from src.common.'),
    ]
    
    # Apply replacements
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Write back to file
    with open(file_path, 'w') as f:
        f.write(content)

# Usage
for py_file in Path('src').rglob('*.py'):
    update_imports_in_file(py_file)
```

### Configuration Migration

Configuration files were also updated to reflect the new structure:

```yaml
# Before (legacy config)
platforms:
  aws:
    module_path: "aws"
  oci:
    module_path: "oci_module"

# After (new config)
platforms:
  aws:
    module_path: "src.ic.platforms.aws"
  oci:
    module_path: "src.ic.platforms.oci"
```

## Testing Migration

### Test File Updates

Test files required updates to import paths and module references:

```python
# Before
from aws.ec2 import info
from tests.mock_data.aws_data import mock_instances

# After
try:
    from src.ic.platforms.aws.ec2 import info
    from tests.ci.mock_data.aws_data import mock_instances
except ImportError:
    from ic.platforms.aws.ec2 import info
    from tests.ci.mock_data.aws_data import mock_instances
```

### Test Execution Updates

Test runners were updated to handle the new structure:

```python
# Updated test discovery in platform_test_runner.py
def discover_platform_tests(platform_name):
    """Discover tests for a specific platform."""
    test_paths = [
        f"tests/platforms/{platform_name}",
        f"tests/unit/test_{platform_name}_*",
        f"tests/integration/test_{platform_name}_*"
    ]
    return test_paths
```

## Future Migration Guidelines

### Planning a Migration

1. **Assessment Phase**:
   - Identify all affected files and imports
   - Create backup of current state
   - Document current structure and dependencies

2. **Preparation Phase**:
   - Create migration scripts for automated updates
   - Update documentation and examples
   - Prepare test cases for validation

3. **Execution Phase**:
   - Run automated migration scripts
   - Manual updates for complex cases
   - Update configuration files
   - Update package metadata

4. **Validation Phase**:
   - Run comprehensive test suite
   - Validate CLI functionality
   - Test package installation
   - Verify documentation accuracy

### Migration Best Practices

#### Code Changes

1. **Use Automated Tools**: Create scripts for repetitive changes
2. **Maintain Backward Compatibility**: Use fallback imports during transition
3. **Update Tests First**: Ensure tests reflect new structure
4. **Incremental Changes**: Make changes in small, testable increments

#### Documentation

1. **Update Examples**: Ensure all code examples use new patterns
2. **Migration Notes**: Document what changed and why
3. **Troubleshooting**: Add common migration issues and solutions
4. **Version Compatibility**: Document which versions support which patterns

#### Testing

1. **Comprehensive Testing**: Test both old and new patterns during transition
2. **Environment Testing**: Test in both development and installed environments
3. **Integration Testing**: Verify CLI and service functionality
4. **Performance Testing**: Ensure migration doesn't impact performance

### Migration Checklist

#### Pre-Migration
- [ ] Create full backup of codebase
- [ ] Document current structure and dependencies
- [ ] Create migration scripts and tools
- [ ] Update test cases for new structure
- [ ] Plan rollback strategy

#### During Migration
- [ ] Run automated migration scripts
- [ ] Update import statements
- [ ] Update configuration files
- [ ] Update package metadata
- [ ] Update documentation and examples

#### Post-Migration
- [ ] Run comprehensive test suite
- [ ] Validate CLI functionality
- [ ] Test package installation
- [ ] Update CI/CD pipelines
- [ ] Clean up legacy code and references

## Common Migration Issues

### Import Resolution Problems

**Issue**: `ModuleNotFoundError` after migration
**Solution**: Check import paths and ensure fallback imports are implemented

```python
# Add proper fallback imports
try:
    from src.ic.platforms.ncp.ec2 import info
except ImportError:
    from ic.platforms.ncp.ec2 import info
```

### CLI Command Discovery Issues

**Issue**: CLI commands not found after migration
**Solution**: Update platform discovery logic

```python
def discover_platforms():
    """Updated platform discovery."""
    try:
        # Development environment
        from src.ic import platforms
        base_path = "src.ic.platforms"
    except ImportError:
        # Installed package
        from ic import platforms
        base_path = "ic.platforms"
    
    return discover_modules(platforms, base_path)
```

### Package Installation Issues

**Issue**: Package doesn't include all modules after migration
**Solution**: Update `pyproject.toml` and `setup.py` package discovery

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["ic*"]
```

### Test Execution Issues

**Issue**: Tests fail due to import path changes
**Solution**: Update test imports and PYTHONPATH

```python
# In conftest.py or test setup
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))
```

## Rollback Procedures

### Emergency Rollback

If migration causes critical issues:

1. **Restore from Backup**:
```bash
git checkout HEAD~1  # or specific commit before migration
```

2. **Selective Rollback**:
```bash
git checkout HEAD~1 -- src/ic/platforms/
git checkout HEAD~1 -- pyproject.toml
```

3. **Verify Functionality**:
```bash
pip install -e .
ic --help
make test-all
```

### Gradual Rollback

For partial rollback while maintaining some changes:

1. Keep new structure but restore old import patterns
2. Update only critical files that are causing issues
3. Maintain backward compatibility during transition

## Version Compatibility

### Supported Versions

- **v1.x**: Legacy structure (deprecated)
- **v2.x**: New consolidated structure (current)
- **v2.1+**: Full migration with fallback support

### Compatibility Matrix

| Feature | v1.x | v2.0 | v2.1+ |
|---------|------|------|-------|
| Legacy imports | ✅ | ❌ | ✅ (fallback) |
| New imports | ❌ | ✅ | ✅ |
| CLI discovery | Legacy | New | New |
| Package structure | Old | New | New |

## Resources

- [Import Patterns Guide](import_patterns.md) - Detailed import patterns
- [Development Guide](development_guide.md) - Development best practices
- [Testing Guide](../tests/README.md) - Testing information
- [Project History](.local-docs/history/migration_history.md) - Detailed migration history

---

**Last Updated**: 2024  
**Maintainer**: IC CLI Development Team