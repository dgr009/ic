# Security Policy

## Overview

IC (Infra Resource Management CLI) takes security seriously. This document outlines our security practices, how to report vulnerabilities, and guidelines for secure usage.

## 🔒 Built-in Security Features

### Sensitive Data Protection
- **Automatic masking** of sensitive data in logs and console output
- **Configuration validation** with warnings for sensitive data in config files
- **Git pre-commit hooks** to prevent accidental commits of sensitive information
- **Environment variable-based** credential management

### Secure Configuration Management
- **No secrets in configuration files** - all sensitive data must be in environment variables
- **Configuration hierarchy** with secure defaults
- **Validation and warnings** for insecure configurations
- **Example files** with placeholder values only

### Logging Security
- **Sensitive data masking** in all log outputs
- **Separate log levels** for console and file output
- **Automatic log rotation** and cleanup
- **No sensitive data** in console output (ERROR level only)

## 🚨 Reporting Security Vulnerabilities

If you discover a security vulnerability in IC, please report it responsibly:

### Preferred Method
- **Email**: cruiser594@gmail.com
- **Subject**: [SECURITY] IC Vulnerability Report
- **Include**: 
  - Description of the vulnerability
  - Steps to reproduce
  - Potential impact
  - Suggested fix (if any)

### What to Include
1. **Vulnerability Details**: Clear description of the issue
2. **Reproduction Steps**: Step-by-step instructions
3. **Impact Assessment**: Potential security implications
4. **Environment**: Version, OS, Python version
5. **Proof of Concept**: If applicable (non-destructive only)

### Response Timeline
- **Initial Response**: Within 48 hours
- **Assessment**: Within 1 week
- **Fix Development**: Depends on severity
- **Public Disclosure**: After fix is released

## 🛡️ Security Best Practices

### For Users

#### 1. Credential Management
```bash
# ✅ GOOD: Use environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AZURE_CLIENT_SECRET="your-client-secret"

# ❌ BAD: Never put credentials in config files
# config.yaml - DON'T DO THIS
aws:
  access_key: "AKIA..." # Never do this!
```

#### 2. Configuration Security
```yaml
# ✅ GOOD: config.yaml with no secrets
aws:
  accounts: ["123456789012"]
  regions: ["us-east-1"]
  
# Environment variables for secrets:
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
# GCP_SERVICE_ACCOUNT_KEY_PATH
```

#### 3. Git Security
```bash
# ✅ GOOD: Proper .gitignore
config.yaml
config.yml
.env
*.key
*.pem
**/credentials.json
logs/

# ✅ GOOD: Use example files
cp config.example.yaml config.yaml
# Edit config.yaml with your values
```

#### 4. File Permissions
```bash
# ✅ GOOD: Secure file permissions
chmod 600 ~/.aws/credentials
chmod 600 ~/.oci/config
chmod 600 config.yaml
chmod 700 ~/.ic/
```

### For Developers

#### 1. Code Security
- Never log sensitive data without masking
- Use the SecurityManager for data validation
- Implement proper error handling
- Follow secure coding practices

#### 2. Testing Security
- Mock all sensitive data in tests
- Use placeholder values in test configurations
- Test security features thoroughly
- Validate masking functionality

## 🔍 Security Features in Detail

### 1. Sensitive Data Masking

The SecurityManager automatically masks sensitive data:

```python
from ic.config.security import SecurityManager

security = SecurityManager(config)
masked_data = security.mask_sensitive_data({
    "password": "secret123",
    "api_key": "ak_1234567890",
    "normal_field": "safe_value"
})
# Result: {"password": "***MASKED***", "api_key": "***MASKED***", "normal_field": "safe_value"}
```

### 2. Configuration Validation

Automatic validation warns about security issues:

```python
warnings = security.validate_config_security(config_data)
for warning in warnings:
    print(f"⚠️  {warning}")
```

### 3. Git Pre-commit Hooks

Prevents committing sensitive data:

```bash
# Install pre-commit hooks
pre-commit install

# Hooks will check for:
# - Sensitive data patterns
# - Credential files
# - Configuration files with secrets
```

## 📋 Security Checklist

Before using IC in production:

- [ ] All credentials are in environment variables
- [ ] No sensitive data in configuration files
- [ ] Proper file permissions set (600 for config files)
- [ ] .gitignore includes all sensitive file patterns
- [ ] Pre-commit hooks installed and working
- [ ] Log files are secured and rotated
- [ ] Network access is properly restricted
- [ ] Regular security updates applied

## 🚫 What NOT to Do

### Never Commit These Files
- `config.yaml` or `config.yml` (actual config)
- `.env` (environment variables)
- `*.key`, `*.pem` (private keys)
- `**/credentials.json` (service account keys)
- `logs/` (log files may contain sensitive data)

### Never Put Secrets In
- Configuration files
- Command line arguments
- Environment variable names
- Log messages (without masking)
- Git repositories
- Documentation or examples

## 🔄 Security Updates

### Staying Secure
1. **Update regularly**: `pip install --upgrade ic`
2. **Monitor releases**: Watch the GitHub repository
3. **Review changelogs**: Check CHANGELOG.md for security fixes
4. **Subscribe to notifications**: Enable GitHub security alerts

### Security Releases
- Security fixes are prioritized
- Critical vulnerabilities get immediate patches
- Security releases are clearly marked
- Upgrade instructions are provided

## 📚 Additional Resources

### Documentation
- [Configuration Guide](docs/configuration.md)
- [Migration Guide](docs/migration.md)
- [Installation Guide](docs/installation.md)

### Security Tools
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [AWS Security Best Practices](https://aws.amazon.com/security/security-resources/)
- [Azure Security Documentation](https://docs.microsoft.com/en-us/azure/security/)
- [GCP Security Best Practices](https://cloud.google.com/security/best-practices)

## 📞 Contact

For security-related questions or concerns:

- **Security Issues**: cruiser594@gmail.com
- **General Questions**: [GitHub Issues](https://github.com/dgr009/ic/issues)
- **Documentation**: [GitHub Wiki](https://github.com/dgr009/ic/wiki)

---

**Remember**: Security is a shared responsibility. While IC provides security features, proper configuration and usage are essential for maintaining security in your environment.