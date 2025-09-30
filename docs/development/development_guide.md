# IC CLI Development Guide

## Overview

This guide provides comprehensive information for developers working on the IC CLI tool, including setup, development patterns, testing, and contribution guidelines.

## Quick Start

### Development Environment Setup

1. **Clone and Setup**:
```bash
git clone <repository-url>
cd ic-cli
python -m venv ic-env
source ic-env/bin/activate  # On Windows: ic-env\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

2. **Verify Installation**:
```bash
ic --help
ic config init
```

3. **Run Tests**:
```bash
make test-all
python tests/run_comprehensive_validation.py
```

## Project Architecture

### Directory Structure

```
src/ic/
├── cli.py                    # Main CLI entry point
├── config/                   # Configuration management
│   ├── manager.py           # ConfigManager class
│   ├── migration.py         # Config migration utilities
│   └── security.py          # Security validation
├── core/                     # Core functionality
│   ├── logging.py           # Logging utilities
│   └── platform_discovery.py # Platform discovery
├── platforms/               # Platform modules
│   ├── aws/                 # Amazon Web Services
│   ├── azure/               # Microsoft Azure
│   ├── cf/                  # CloudFlare
│   ├── gcp/                 # Google Cloud Platform
│   ├── ncp/                 # Naver Cloud Platform
│   ├── ncpgov/              # NCP Government
│   ├── oci/                 # Oracle Cloud Infrastructure
│   └── ssh/                 # SSH management
└── security/                # Security utilities
```

### Platform Module Pattern

Each platform follows this structure:

```
src/ic/platforms/{platform}/
├── __init__.py              # Platform exports
├── client.py               # Authentication & API client (optional)
└── {service}/
    ├── __init__.py         # Service exports
    └── info.py             # Service implementation
```

## Development Patterns

### Import Patterns

**Standard Pattern** (see [Import Patterns Guide](import_patterns.md) for details):

```python
# Platform imports with fallback
try:
    from src.ic.platforms.ncp.ec2 import info as ncp_ec2_info
    from src.ic.config.manager import ConfigManager
    from src.common.progress_decorator import progress_decorator
except ImportError:
    from ic.platforms.ncp.ec2 import info as ncp_ec2_info
    from ic.config.manager import ConfigManager
    from common.progress_decorator import progress_decorator
```

### Service Module Implementation

Every service module must implement:

```python
def add_arguments(parser):
    """Add service-specific CLI arguments."""
    parser.add_argument('--region', help='Specify region')
    parser.add_argument('--format', choices=['table', 'json'], 
                       default='table', help='Output format')

def main(args, config=None):
    """Execute the service command."""
    try:
        # Initialize configuration if not provided
        if config is None:
            config = ConfigManager()
        
        # Service implementation
        result = perform_operation(args, config)
        
        return {
            "success": True,
            "data": result,
            "message": "Operation completed successfully"
        }
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Operation failed: {e}"
        }
```

### Error Handling Pattern

```python
import logging

logger = logging.getLogger(__name__)

def robust_operation():
    """Example of robust error handling."""
    try:
        # Main operation
        result = perform_api_call()
        return {"success": True, "data": result}
    
    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
        return {
            "success": False,
            "error": "connection_failed",
            "message": "Unable to connect to service. Check your network connection."
        }
    
    except AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        return {
            "success": False,
            "error": "auth_failed",
            "message": "Authentication failed. Check your credentials."
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "success": False,
            "error": "unexpected_error",
            "message": f"An unexpected error occurred: {e}"
        }
```

### Progress Indicators

Use the progress decorator for long-running operations:

```python
from src.common.progress_decorator import progress_decorator

@progress_decorator("Processing resources")
def process_multiple_resources(resources):
    """Process multiple resources with progress indication."""
    results = []
    for resource in resources:
        result = process_single_resource(resource)
        results.append(result)
    return results

@progress_decorator("Fetching data from API")
def fetch_api_data(endpoint, params):
    """Fetch data from API with progress indication."""
    response = api_client.get(endpoint, params=params)
    return response.json()
```

### Configuration Management

```python
from src.ic.config.manager import ConfigManager

def service_with_config():
    """Example service using configuration."""
    config = ConfigManager()
    
    # Get configuration values with defaults
    region = config.get_config_value('aws.default_region', 'us-east-1')
    timeout = config.get_config_value('api.timeout', 30)
    
    # Get sensitive values (from secrets.yaml)
    api_key = config.get_secret('ncp.api_key')
    
    # Validate configuration
    if not api_key:
        raise ValueError("NCP API key not configured")
    
    return perform_operation(region, timeout, api_key)
```

## Testing Guidelines

### Test Organization

```
tests/
├── unit/                    # Unit tests
├── integration/             # Integration tests
├── performance/             # Performance tests
└── platforms/              # Platform-specific tests
    └── {platform}/
        └── {service}/
            ├── unit/
            ├── integration/
            └── performance/
```

### Unit Testing Pattern

```python
import unittest
from unittest.mock import Mock, patch
from src.ic.platforms.ncp.ec2 import info

class TestNCPEC2Info(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.get_config_value.return_value = 'test-region'
        self.mock_config.get_secret.return_value = 'test-api-key'
    
    @patch('src.ic.platforms.ncp.client.NCPClient')
    def test_main_success(self, mock_client):
        """Test successful execution."""
        # Setup mock
        mock_instance = mock_client.return_value
        mock_instance.get_instances.return_value = [{'id': 'i-123', 'name': 'test'}]
        
        # Create mock args
        args = Mock()
        args.region = 'test-region'
        args.format = 'table'
        
        # Execute
        result = info.main(args, self.mock_config)
        
        # Verify
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        mock_client.assert_called_once()
    
    def test_add_arguments(self):
        """Test argument parser setup."""
        parser = Mock()
        info.add_arguments(parser)
        
        # Verify arguments were added
        parser.add_argument.assert_called()
```

### Integration Testing Pattern

```python
import unittest
from src.ic.config.manager import ConfigManager
from src.ic.platforms.ncp.ec2 import info

class TestNCPEC2Integration(unittest.TestCase):
    
    def setUp(self):
        """Set up integration test environment."""
        self.config = ConfigManager()
        # Use test configuration
        self.config.load_config('tests/fixtures/test_config.yaml')
    
    @unittest.skipUnless(
        os.getenv('RUN_INTEGRATION_TESTS'), 
        "Integration tests disabled"
    )
    def test_real_api_call(self):
        """Test with real API (requires credentials)."""
        args = Mock()
        args.region = 'KR-1'
        args.format = 'json'
        
        result = info.main(args, self.config)
        
        # Should not fail with proper credentials
        self.assertTrue(result['success'])
```

## Code Quality Standards

### Linting and Formatting

```bash
# Install development dependencies
pip install black flake8 mypy bandit

# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Security scanning
bandit -r src/
```

### Code Review Checklist

- [ ] Follows import patterns from [Import Patterns Guide](import_patterns.md)
- [ ] Implements required service module interface
- [ ] Includes proper error handling
- [ ] Has progress indicators for long operations
- [ ] Includes unit tests with >80% coverage
- [ ] Follows security best practices
- [ ] Updates documentation as needed
- [ ] Passes all existing tests

## Security Guidelines

### Credential Handling

```python
# ✅ Correct: Use ConfigManager for secrets
config = ConfigManager()
api_key = config.get_secret('platform.api_key')

# ❌ Wrong: Hard-coded credentials
api_key = "hardcoded-key-123"

# ❌ Wrong: Environment variables for secrets
api_key = os.getenv('API_KEY')
```

### Input Validation

```python
def validate_region(region):
    """Validate region parameter."""
    valid_regions = ['us-east-1', 'us-west-2', 'eu-west-1']
    if region not in valid_regions:
        raise ValueError(f"Invalid region: {region}")
    return region

def sanitize_instance_name(name):
    """Sanitize instance name input."""
    # Remove potentially dangerous characters
    import re
    return re.sub(r'[^a-zA-Z0-9-_]', '', name)
```

### Logging Security

```python
# ✅ Correct: Mask sensitive data
logger.info(f"Connecting to API with key: {api_key[:8]}***")

# ❌ Wrong: Log sensitive data
logger.info(f"Using API key: {api_key}")
```

## Performance Guidelines

### Async Operations

```python
import asyncio
import aiohttp

async def fetch_multiple_resources(resource_ids):
    """Fetch multiple resources concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_resource(session, rid) for rid in resource_ids]
        results = await asyncio.gather(*tasks)
    return results

async def fetch_resource(session, resource_id):
    """Fetch a single resource."""
    async with session.get(f'/api/resources/{resource_id}') as response:
        return await response.json()
```

### Caching

```python
from functools import lru_cache
import time

@lru_cache(maxsize=128)
def get_cached_config(config_key):
    """Cache configuration values."""
    return ConfigManager().get_config_value(config_key)

class TimedCache:
    """Simple timed cache for API responses."""
    
    def __init__(self, ttl=300):  # 5 minutes default
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time.time())
```

## Debugging and Troubleshooting

### Debug Mode

```python
import logging

def enable_debug_logging():
    """Enable debug logging for development."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Usage in service modules
logger = logging.getLogger(__name__)

def debug_operation():
    logger.debug("Starting operation")
    logger.debug(f"Configuration: {config.to_dict()}")
    logger.debug("Operation completed")
```

### Common Issues and Solutions

1. **Import Errors**: Check [Import Patterns Guide](import_patterns.md)
2. **Configuration Issues**: Verify `~/.ic/config/` files
3. **Authentication Failures**: Check credentials in `secrets.yaml`
4. **API Timeouts**: Increase timeout values in configuration

## Contributing

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes following the development patterns
4. Add tests for new functionality
5. Update documentation
6. Run full test suite: `make test-all`
7. Submit pull request with clear description

### Commit Message Format

```
type(scope): brief description

Detailed description of changes made.

- List specific changes
- Reference issue numbers if applicable

Closes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Resources

- [Import Patterns Guide](import_patterns.md) - Detailed import patterns
- [Testing Guide](../tests/README.md) - Comprehensive testing information
- [Security Guide](../security.md) - Security best practices
- [Configuration Guide](../general/configuration.md) - Configuration management

---

**Last Updated**: 2024  
**Maintainer**: IC CLI Development Team