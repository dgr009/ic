# Changelog

All notable changes to IC (Infra Resource Management CLI) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-03

### 🎉 Initial PyPI Release

This is the first official release of IC (Infra Resource Management CLI) on PyPI, featuring a complete restructure for modern Python packaging standards and enhanced security.

### ✨ Added

#### Package Structure & Distribution
- **Modern Python packaging** with `src/` layout and `pyproject.toml`
- **PyPI-ready distribution** with wheel and source packages
- **Comprehensive metadata** with security-focused descriptions
- **Pinned dependencies** for security and reproducibility

#### Security Features
- **SecurityManager** with automatic sensitive data masking
- **Git pre-commit hooks** for security validation
- **Configuration security validation** with warnings
- **Environment variable-based credential management**
- **Secure logging** with sensitive data masking in all outputs

#### Configuration Management
- **YAML-based configuration system** replacing .env files
- **Configuration hierarchy** (default → user → project → environment)
- **Schema validation** with comprehensive error messages
- **Migration utility** from .env to YAML configuration
- **Backward compatibility** with existing .env files

#### Enhanced Logging
- **Dual-level logging** (console ERROR only, file comprehensive)
- **Rich console output** with minimal noise
- **File-only INFO logging** for detailed operation tracking
- **Automatic log rotation** and cleanup
- **Sensitive data masking** in all log outputs

#### AWS Session Management
- **Intelligent profile detection** (assume_role vs direct credentials)
- **Session caching** for improved performance
- **Account alias resolution** with fallback to account ID
- **Enhanced error handling** and validation

#### MCP Integration
- **MCP server support** for AWS, Azure, Terraform, and GitHub
- **Secure MCP configuration loading** with sensitive data masking
- **Query methods** for different cloud platforms
- **Fallback mechanisms** for MCP server unavailability

#### Multi-Cloud Support
- **AWS**: EC2, ECS, EKS, Fargate, MSK, CodePipeline, LB, RDS, S3, VPC, VPN, Security Groups, NAT
- **Azure**: VM, VNet, AKS, Storage Account, NSG, Load Balancer, Container Instances
- **GCP**: Compute Engine, VPC Networks, GKE, Cloud Storage, Cloud SQL, Cloud Functions, Cloud Run, Load Balancing, Firewall Rules, Billing
- **OCI**: VM, LB, NSG, VCN, Volume, Object Storage, Policy, Cost
- **CloudFlare**: DNS record management
- **SSH**: Server status checking and automatic registration

#### Documentation & Security
- **Comprehensive security documentation** (SECURITY.md)
- **Configuration management guide** (docs/configuration.md)
- **Migration guide** (docs/migration.md)
- **Installation guide** (docs/installation.md)
- **Security-focused README** with best practices

### 🔧 Changed

#### Breaking Changes
- **Package structure** moved to `src/ic/` layout
- **Configuration system** now uses YAML instead of .env (with backward compatibility)
- **Logging behavior** changed to console ERROR only, file comprehensive
- **Import paths** updated for new structure (backward compatibility maintained)

#### Improvements
- **Performance optimizations** with session caching and parallel processing
- **Error handling** enhanced with detailed error messages
- **Output formatting** improved with Rich library integration
- **Security hardening** throughout the codebase

### 🛡️ Security

#### New Security Features
- **Automatic sensitive data masking** in logs and configuration
- **Git security validation** with pre-commit hooks
- **Configuration security warnings** for sensitive data
- **Secure credential management** with environment variables only
- **File permission validation** and recommendations

#### Security Best Practices
- **No secrets in configuration files** - environment variables only
- **Comprehensive .gitignore** for sensitive files
- **Security documentation** and guidelines
- **Vulnerability reporting process** established

### 📦 Dependencies

#### Updated Dependencies
- **boto3**: 1.40.59 (AWS SDK)
- **azure-***: Latest stable versions for Azure services
- **google-cloud-***: Latest stable versions for GCP services
- **oci**: 2.149.2 (Oracle Cloud Infrastructure)
- **rich**: 14.0.0 (Console formatting)
- **paramiko**: 4.0.1 (SSH client)
- **PyYAML**: 6.0.1 (YAML parsing)

#### New Dependencies
- **jsonschema**: 4.23.0 (Configuration validation)
- **cryptography**: 42.0.8 (Security utilities)
- **invoke**: 2.2.0 (Task execution)

### 🔄 Migration

#### From Previous Versions
1. **Install new version**: `pip install --upgrade ic`
2. **Migrate configuration**: `ic config migrate` (converts .env to YAML)
3. **Update imports**: Most imports remain compatible
4. **Review security**: Follow new security guidelines in SECURITY.md

#### Configuration Migration
```bash
# Automatic migration from .env to config.yaml
ic config migrate

# Validate new configuration
ic config validate

# Initialize secure configuration
ic config init
```

### 🐛 Fixed
- **Session management** reliability improvements
- **Error handling** for various edge cases
- **Memory usage** optimizations
- **Logging** consistency across modules

### 📋 Known Issues
- **Azure DevOps SDK**: Only beta versions available, commented out in dependencies
- **Large log files**: Automatic rotation helps but monitor disk usage
- **MCP server dependencies**: Requires separate MCP server setup for full functionality

### 🔮 Coming Soon
- **Additional cloud providers** support
- **Enhanced reporting** with Excel/CSV export
- **CI/CD integration** templates
- **Performance monitoring** and metrics
- **Advanced security scanning** integration

---

## Development Guidelines

### Version Numbering
- **Major** (X.0.0): Breaking changes, major new features
- **Minor** (1.X.0): New features, backward compatible
- **Patch** (1.0.X): Bug fixes, security patches

### Release Process
1. Update version in `src/ic/__init__.py`
2. Update CHANGELOG.md with new version
3. Create and test distribution packages
4. Tag release in Git
5. Upload to PyPI
6. Update documentation

### Security Releases
- **Critical vulnerabilities**: Immediate patch release
- **Security improvements**: Next minor release
- **Security documentation**: Continuous updates

---

For more information, see:
- [Security Policy](SECURITY.md)
- [Configuration Guide](docs/configuration.md)
- [Migration Guide](docs/migration.md)
- [GitHub Repository](https://github.com/dgr009/ic)