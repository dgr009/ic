# IC CLI Development Documentation

## Overview

This directory contains comprehensive development documentation for the IC CLI tool. Whether you're a new contributor or an experienced developer, these guides will help you understand the project structure, development patterns, and best practices.

## Quick Start

1. **[Development Guide](development_guide.md)** - Complete development setup and patterns
2. **[Import Patterns](import_patterns.md)** - Essential import patterns and best practices
3. **[Migration Guide](migration_guide.md)** - Migration procedures and troubleshooting

## Documentation Index

### Core Development Guides

- **[Development Guide](development_guide.md)** - Comprehensive development guide including:
  - Environment setup and configuration
  - Project architecture and patterns
  - Code quality standards and testing
  - Security guidelines and performance tips
  - Contributing guidelines and PR process

- **[Import Patterns Guide](import_patterns.md)** - Essential guide for import patterns:
  - Standard import patterns for the new structure
  - Fallback patterns for package compatibility
  - Platform module standards and interfaces
  - Migration examples and troubleshooting
  - Testing import patterns

- **[Migration Guide](migration_guide.md)** - Migration procedures and history:
  - Recent platform consolidation migration
  - Automated migration tools and scripts
  - Future migration guidelines and best practices
  - Common issues and rollback procedures
  - Version compatibility information

### Specialized Topics

- **[Dependency Management](.local-docs/development/dependency_management.md)** - Managing project dependencies
- **[Output Formatting System](.local-docs/development/output_formatting_system.md)** - Rich terminal output patterns
- **[PyPI Deployment](.local-docs/development/pypi_deployment.md)** - Package deployment procedures

### Testing Documentation

- **[Testing Guide](../tests/README.md)** - Comprehensive testing information
- **[Testing Summary](../tests/TESTING_SUMMARY.md)** - Current testing status and coverage

## Development Workflow

### 1. Initial Setup

```bash
# Clone and setup development environment
git clone <repository-url>
cd ic-cli
python -m venv ic-env
source ic-env/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Development Patterns

Follow the patterns outlined in the [Development Guide](development_guide.md):

- Use the standardized import patterns from [Import Patterns Guide](import_patterns.md)
- Implement required service module interfaces
- Include proper error handling and progress indicators
- Add comprehensive tests for new functionality

### 3. Code Quality

```bash
# Format and lint code
black src/ tests/
flake8 src/ tests/
mypy src/

# Run security scanning
bandit -r src/

# Run comprehensive tests
make test-all
python tests/run_comprehensive_validation.py
```

### 4. Contributing

1. Create feature branch from main
2. Follow development patterns and guidelines
3. Add tests and update documentation
4. Submit pull request with clear description

## Architecture Overview

### Project Structure

```
src/ic/
├── cli.py                    # Main CLI entry point
├── config/                   # Configuration management
├── core/                     # Core functionality
├── platforms/               # Platform modules (AWS, Azure, GCP, etc.)
└── security/                # Security utilities

src/common/                   # Common utilities
tests/                        # Test suite
docs/                         # Documentation
```

### Key Principles

1. **Consistent Import Patterns**: All modules use standardized import patterns with fallbacks
2. **Service Module Interface**: All services implement `add_arguments()` and `main()` functions
3. **Security First**: Credential protection, input validation, and audit logging
4. **Rich User Experience**: Progress indicators, formatted output, and helpful error messages
5. **Comprehensive Testing**: Unit, integration, and performance tests

## Common Development Tasks

### Adding a New Platform

1. Create platform directory: `src/ic/platforms/{platform}/`
2. Implement platform client and services following the standard pattern
3. Add comprehensive tests in `tests/platforms/{platform}/`
4. Update CLI discovery and documentation

### Adding a New Service

1. Create service module: `src/ic/platforms/{platform}/{service}/info.py`
2. Implement required interface: `add_arguments()` and `main()`
3. Add unit and integration tests
4. Update platform documentation

### Updating Import Patterns

1. Follow patterns from [Import Patterns Guide](import_patterns.md)
2. Use try/except blocks for fallback imports
3. Test in both development and installed environments
4. Update related tests and documentation

## Troubleshooting

### Common Issues

1. **Import Errors**: Check [Import Patterns Guide](import_patterns.md) for correct patterns
2. **CLI Commands Not Found**: Verify platform discovery is working
3. **Test Failures**: Ensure PYTHONPATH includes src directory
4. **Package Installation Issues**: Check pyproject.toml configuration

### Debug Tools

```python
# Debug import issues
from src.ic.core.platform_discovery import debug_platform_discovery
debug_platform_discovery()

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Getting Help

1. Check existing documentation and guides
2. Review test cases for examples
3. Check project issues and discussions
4. Contact the development team

## Resources

### Internal Documentation
- [Project History](.local-docs/history/) - Detailed project history and changes
- [Security Documentation](.local-docs/security/) - Security reports and guidelines
- [Validation Reports](.local-docs/validation/) - Validation and testing reports

### External Resources
- [Python Packaging Guide](https://packaging.python.org/) - Python packaging best practices
- [Click Documentation](https://click.palletsprojects.com/) - CLI framework documentation
- [Rich Documentation](https://rich.readthedocs.io/) - Terminal formatting library

---

**Last Updated**: 2024  
**Maintainer**: IC CLI Development Team

## Quick Reference

### Essential Commands

```bash
# Development setup
python -m venv ic-env && source ic-env/bin/activate
pip install -r requirements.txt && pip install -e .

# Testing
make test-all
python tests/run_comprehensive_validation.py

# Code quality
black src/ tests/ && flake8 src/ tests/ && mypy src/

# Package building
python setup.py sdist bdist_wheel

# CLI testing
ic --help
ic config init
ic aws ec2 info --help
```

### Import Template

```python
# Standard import pattern with fallback
try:
    from src.ic.platforms.{platform}.{service} import info
    from src.ic.config.manager import ConfigManager
    from src.common.progress_decorator import progress_decorator
except ImportError:
    from ic.platforms.{platform}.{service} import info
    from ic.config.manager import ConfigManager
    from common.progress_decorator import progress_decorator
```

### Service Module Template

```python
def add_arguments(parser):
    """Add service-specific arguments."""
    parser.add_argument('--region', help='Specify region')

def main(args, config=None):
    """Execute service command."""
    try:
        # Service implementation
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```