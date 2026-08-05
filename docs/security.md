# IC Security Guide

IC CLI includes built-in security auditing, secret scanning, and git hook integration to prevent accidental leakage of sensitive credentials.

## 🛡️ Core Security Features

- **Sensitive Data Masking**: Automatically masks API keys, tokens, and passwords in console outputs and logs (`***MASKED***`).
- **Secret Scanner**: Scans project files and staged git commits for hardcoded secrets.
- **Git Security Hooks**: Install pre-commit hooks to block commits containing sensitive data.

---

## 🚀 Security Commands

### 1. Codebase Secret Scan
Scan current directory or specific path for hardcoded secrets, keys, or passwords:

```bash
# Scan current repository
ic security scan

# Verbose output with file lines
ic security scan -v
```

### 2. Pre-Commit Hook Management
Install or uninstall git pre-commit security scanner hooks:

```bash
# Install pre-commit hook to current git repository
ic security install-hooks

# Uninstall pre-commit hook
ic security uninstall-hooks
```

---

## 🔒 Configuration Security Best Practices

1. **File Permissions**: Ensure configuration files have restricted permissions (`0o600`):
   ```bash
   chmod 600 ~/.ic/config/secrets.yaml
   chmod 600 ~/.aws/credentials
   chmod 600 ~/.tencent/credentials
   ```

2. **Git Ignore**: Ensure `secrets.yaml` and `.env` files are included in your `.gitignore`.