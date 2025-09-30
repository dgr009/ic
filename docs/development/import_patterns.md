# IC CLI Import Patterns and Best Practices

## Overview

This document outlines the standardized import patterns and best practices for the IC CLI tool following the major project structure migration. All platform modules have been consolidated under `src/ic/platforms/` with consistent naming and import patterns.

## Project Structure

The IC CLI follows a modern Python packaging structure:

```
src/ic/
├── cli.py                    # Main CLI entry point
├── config/                   # Configuration management
├── core/                     # Core functionality
├── platforms/               # Platform modules
│   ├── aws/                 # Amazon Web Services
│   ├── azure/               # Microsoft Azure
│   ├── cf/                  # CloudFlare
│   ├── gcp/                 # Google Cloud Platform
│   ├── ncp/                 # Naver Cloud Platform
│   ├── ncpgov/              # Naver Cloud Platform Government
│   ├── oci/                 # Oracle Cloud Infrastructure
│   └── ssh/                 # SSH management
└── security/                # Security utilities
```

## Import Patterns

### Standard Import Pattern

All imports should follow the absolute import pattern from the `src` directory:

```python
# Platform service imports
from src.ic.platforms.aws.ec2 import info as aws_ec2_info
from src.ic.platforms.oci.vm import info as oci_vm_info
from src.ic.platforms.ncp.ec2 import info as ncp_ec2_info

# Configuration and core imports
from src.ic.config.manager import ConfigManager
from src.ic.core.logging import get_logger
from src.ic.security.validator import SecurityValidator

# Common utilities
from src.common.progress_decorator import progress_decorator
from src.common.utils import format_output
```

### Fallback Import Pattern

For compatibility with both development and installed package scenarios, use try/except blocks:

```python
try:
    # Development environment (src/ structure)
    from src.ic.platforms.ncp.ec2 import info as ncp_ec2_info
    from src.ic.config.manager import ConfigManager
    from src.common.progress_decorator import progress_decorator
except ImportError:
    # Installed package environment
    from ic.platforms.ncp.ec2 import info as ncp_ec2_info
    from ic.config.manager import ConfigManager
    from common.progress_decorator import progress_decorator
```

### Service Module Imports

When importing service modules within the same platform:

```python
# Within AWS platform modules
try:
    from src.ic.platforms.aws.client import AWSClient
    from src.ic.platforms.aws.utils import format_aws_output
except ImportError:
    from ic.platforms.aws.client import AWSClient
    from ic.platforms.aws.utils import format_aws_output
```

## Platform Module Standards

### Required Module Structure

Each platform must follow this structure:

```
src/ic/platforms/{platform}/
├── __init__.py              # Platform initialization
├── client.py               # Authentication & API client (optional)
└── {service}/
    ├── __init__.py         # Service initialization
    └── info.py             # Service operations & CLI integration
```

### Required Service Module Interface

Every service module MUST implement these functions:

```python
def add_arguments(parser):
    """
    Add service-specific arguments to the CLI parser.
    
    Args:
        parser: argparse.ArgumentParser instance
    """
    parser.add_argument('--region', help='Specify region')
    # Add other service-specific arguments

def main(args, config=None):
    """
    Execute the service command.
    
    Args:
        args: Parsed command line arguments
        config: Configuration manager instance (optional)
        
    Returns:
        dict: Result dictionary with success/error status
    """
    try:
        # Service implementation
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

## Common Import Scenarios

### CLI Integration

In the main CLI file (`src/ic/cli.py`):

```python
import importlib
import sys
from pathlib import Path

def discover_platforms():
    """Dynamically discover available platforms."""
    platforms = {}
    
    try:
        # Development environment
        platforms_path = Path(__file__).parent / "platforms"
        base_module = "src.ic.platforms"
    except:
        # Installed package environment
        import ic.platforms
        platforms_path = Path(ic.platforms.__file__).parent
        base_module = "ic.platforms"
    
    for platform_dir in platforms_path.iterdir():
        if platform_dir.is_dir() and not platform_dir.name.startswith('_'):
            platforms[platform_dir.name] = f"{base_module}.{platform_dir.name}"
    
    return platforms
```

### Configuration Access

```python
try:
    from src.ic.config.manager import ConfigManager
except ImportError:
    from ic.config.manager import ConfigManager

# Usage
config = ConfigManager()
aws_region = config.get_config_value('aws.default_region', 'us-east-1')
```

### Progress Indicators

```python
try:
    from src.common.progress_decorator import progress_decorator
except ImportError:
    from common.progress_decorator import progress_decorator

@progress_decorator("Processing resources")
def process_resources(items):
    """Process a list of resources with progress indication."""
    results = []
    for item in items:
        # Process each item
        results.append(process_item(item))
    return results
```

### Logging

```python
try:
    from src.ic.core.logging import get_logger
except ImportError:
    from ic.core.logging import get_logger

logger = get_logger(__name__)

def example_function():
    logger.info("Starting operation")
    try:
        # Operation logic
        logger.debug("Operation completed successfully")
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        raise
```

## Migration Guidelines

### Updating Existing Code

When updating existing code to use the new import patterns:

1. **Replace relative imports** with absolute imports from `src`
2. **Add fallback imports** for package compatibility
3. **Update module references** to use the new platform structure
4. **Test both scenarios** (development and installed package)

### Example Migration

**Before (Legacy):**
```python
from ncp.ec2 import info
from common.utils import format_output
from ..client import NCPClient
```

**After (New Pattern):**
```python
try:
    from src.ic.platforms.ncp.ec2 import info
    from src.common.utils import format_output
    from src.ic.platforms.ncp.client import NCPClient
except ImportError:
    from ic.platforms.ncp.ec2 import info
    from common.utils import format_output
    from ic.platforms.ncp.client import NCPClient
```

## Testing Import Patterns

### Unit Tests

```python
import unittest
from unittest.mock import patch

class TestImportPatterns(unittest.TestCase):
    
    def test_development_imports(self):
        """Test imports work in development environment."""
        try:
            from src.ic.platforms.ncp.ec2 import info
            self.assertTrue(hasattr(info, 'main'))
            self.assertTrue(hasattr(info, 'add_arguments'))
        except ImportError:
            self.fail("Development imports failed")
    
    def test_package_imports(self):
        """Test imports work in installed package environment."""
        with patch('sys.modules', {}):
            try:
                from ic.platforms.ncp.ec2 import info
                self.assertTrue(hasattr(info, 'main'))
                self.assertTrue(hasattr(info, 'add_arguments'))
            except ImportError:
                # This is expected in development environment
                pass
```

## Best Practices

### Do's

- ✅ Use absolute imports from `src` directory
- ✅ Implement fallback imports for package compatibility
- ✅ Follow consistent module naming (no unnecessary suffixes)
- ✅ Test imports in both development and installed scenarios
- ✅ Use try/except blocks for import fallbacks
- ✅ Document import patterns in module docstrings

### Don'ts

- ❌ Use relative imports (e.g., `from ..client import Client`)
- ❌ Hard-code platform module names in imports
- ❌ Mix import patterns within the same module
- ❌ Ignore import errors without proper fallbacks
- ❌ Use deprecated module names (e.g., `oci_module`, `azure_module`)

## Troubleshooting

### Common Import Issues

1. **ModuleNotFoundError**: Check if the module path is correct and follows the new structure
2. **ImportError in tests**: Ensure test environment has proper PYTHONPATH setup
3. **CLI commands not found**: Verify platform discovery is working correctly
4. **Circular imports**: Review import dependencies and restructure if necessary

### Debugging Import Issues

```python
import sys
import importlib.util

def debug_import(module_name):
    """Debug import issues by checking module availability."""
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        print(f"Module {module_name} not found")
        print(f"Python path: {sys.path}")
    else:
        print(f"Module {module_name} found at: {spec.origin}")

# Usage
debug_import("src.ic.platforms.ncp.ec2.info")
```

## Future Considerations

### Extensibility

The import pattern is designed to support:

- Easy addition of new platforms
- Dynamic service discovery
- Plugin architecture for third-party extensions
- Backward compatibility during migrations

### Performance

- Lazy loading of platform modules to improve startup time
- Import caching to avoid repeated module resolution
- Minimal import overhead for unused platforms

---

**Last Updated**: 2024  
**Maintainer**: IC CLI Development Team