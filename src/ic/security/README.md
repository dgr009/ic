# IC CLI Security System

The IC CLI Security System provides comprehensive protection against accidentally committing sensitive data to version control. It includes pattern-based detection, pre-commit hooks, and detailed remediation guidance.

## Features

### 🔍 Sensitive Data Detection
- **API Keys & Tokens**: NCP, NCPGOV, AWS, GCP, Azure credentials
- **Communication Tokens**: Slack tokens, webhooks, user/channel IDs  
- **Personal Information**: Email addresses, phone numbers, IP addresses
- **Custom Patterns**: Configurable organization-specific patterns

### 🛡️ Pre-commit Protection
- Automatic scanning of staged files before commits
- Commit blocking for high-severity issues
- Detailed explanations of detected issues
- Respect for .gitignore exclusions

### 📖 Remediation Guidance
- Step-by-step remediation instructions
- Platform-specific configuration guidance
- Prevention tips and best practices
- Quick fix suggestions

## Quick Start

### 1. Install Pre-commit Hooks
```bash
ic security install-hooks
```

### 2. Scan Your Repository
```bash
# Scan entire repository
ic security scan

# Scan only staged files
ic security scan --staged

# Generate detailed report
ic security scan --report security_report.json
```

### 3. Get Remediation Guidance
```bash
# Generate comprehensive remediation guide
ic security remediation

# Save guide to file
ic security remediation --output remediation_guide.txt
```

## Commands

### Security Scanning
```bash
# Basic scan
ic security scan

# Scan specific path
ic security scan --path /path/to/directory

# Scan staged files only
ic security scan --staged

# Generate report
ic security scan --report security_report.json
```

### Hook Management
```bash
# Install pre-commit hooks
ic security install-hooks

# Remove pre-commit hooks  
ic security remove-hooks

# Check hook status
ic security status

# Test hooks without committing
ic security test-hook
```

### Configuration
```bash
# Show current configuration
ic security config

# Add custom pattern
ic security add-pattern "custom_secret" "(?i)(custom[_-]?secret)\\s*[:=]\\s*[\"']?([A-Za-z0-9]{20,})[\"']?" "Custom secret pattern" --severity high

# Remove custom pattern
ic security remove-pattern "custom_secret"
```

### Remediation
```bash
# Generate remediation guide
ic security remediation

# Generate guide for staged files
ic security remediation --staged

# Save guide to file
ic security remediation --output guide.txt
```

## Configuration

The security system uses a configuration file at `~/.ic/config/security.json`:

```json
{
  "enabled": true,
  "block_on_high_severity": true,
  "block_on_medium_severity": false,
  "scan_extensions": [".py", ".yaml", ".yml", ".json", ".txt", ".md"],
  "exclude_patterns": [".git/*", "__pycache__/*", "*.pyc"],
  "custom_patterns": [
    {
      "name": "custom_api_key",
      "pattern": "(?i)(api[_-]?key)\\s*[:=]\\s*[\"']?([A-Za-z0-9]{32,})[\"']?",
      "description": "Custom API key",
      "severity": "high",
      "guidance": "Move to environment variables"
    }
  ]
}
```

## Detected Patterns

### High Severity
- **NCP Access/Secret Keys**: Naver Cloud Platform credentials
- **NCPGOV Keys**: Government cloud credentials  
- **AWS Credentials**: Access keys, secret keys
- **GCP Service Account Keys**: JSON service account files
- **Azure Client Secrets**: Azure authentication secrets
- **API Keys**: Generic API keys and tokens
- **JWT Tokens**: JSON Web Tokens
- **Slack Tokens**: Bot tokens, app tokens

### Medium Severity
- **Slack Webhooks**: Webhook URLs
- **Slack User/Channel IDs**: Workspace identifiers
- **Email Addresses**: Personal/organizational emails
- **Phone Numbers**: Contact information

### Low Severity  
- **IP Addresses**: Internal/external IP addresses
- **Project Names**: Organization-specific project identifiers

## Remediation Examples

### NCP Credentials
```bash
# ❌ Don't do this
ncp_access_key = "AKIA1234567890ABCDEF"

# ✅ Do this instead
# 1. Remove from code
# 2. Run: ic config init
# 3. Add to ~/.ncp/config.yaml:
#    access_key: "AKIA1234567890ABCDEF"
#    secret_key: "your_secret_key"
#    region: "KR"
```

### Environment Variables
```bash
# ❌ Don't do this  
slack_token = "xoxb-1234567890-1234567890-abcdefghijklmnopqrstuvwx"

# ✅ Do this instead
import os
slack_token = os.getenv("SLACK_TOKEN")

# In .env file (add .env to .gitignore):
# SLACK_TOKEN=xoxb-1234567890-1234567890-abcdefghijklmnopqrstuvwx
```

## Integration with Git Workflow

### Pre-commit Hook Behavior
1. **Scan Staged Files**: Only files being committed are scanned
2. **Severity-based Blocking**: High severity issues block commits
3. **Detailed Feedback**: Shows exactly what was found and where
4. **Remediation Guidance**: Provides specific fix instructions
5. **Gitignore Respect**: Honors .gitignore exclusions

### Exit Codes
- `0`: No issues found, commit allowed
- `1`: High severity issues found, commit blocked  
- `2`: Medium/low severity issues found, commit allowed with warning

## Best Practices

### 1. Configuration Management
- Use `ic config init` to set up secure configuration directories
- Store credentials in `~/.ncp/`, `~/.ncpgov/`, `~/.aws/` etc.
- Use environment variables for CI/CD pipelines

### 2. .gitignore Setup
```gitignore
# Credentials and keys
*.key
*.pem
*.p12
*.pfx

# Environment files
.env
.env.local
.env.*.local

# Configuration files
config.yaml
secrets.yaml
credentials.json

# IC CLI local configs (if any)
.ic/local/
```

### 3. Regular Scanning
```bash
# Add to your development workflow
git add .
ic security scan --staged
git commit -m "Your commit message"
```

### 4. Team Setup
```bash
# Set up for entire team
ic security install-hooks
ic security config

# Share configuration (without secrets)
cp ~/.ic/config/security.json team-security-config.json
# Edit to remove any sensitive patterns, then share
```

## Troubleshooting

### Hook Not Working
```bash
# Check hook status
ic security status

# Reinstall if needed
ic security remove-hooks
ic security install-hooks

# Test manually
ic security test-hook
```

### False Positives
```bash
# Add to .gitignore to exclude files
echo "false_positive_file.py" >> .gitignore

# Or add custom exclude pattern to config
ic security config
# Edit ~/.ic/config/security.json to add exclude patterns
```

### Custom Patterns
```bash
# Add organization-specific patterns
ic security add-pattern "company_token" "(?i)(company[_-]?token)\\s*[:=]\\s*[\"']?([A-Za-z0-9]{16,})[\"']?" "Company internal token" --severity medium

# Test the pattern
ic security scan --staged
```

## Security Considerations

1. **Configuration Security**: Keep security configuration files secure
2. **Pattern Updates**: Regularly update detection patterns
3. **Team Training**: Ensure team understands security practices
4. **Regular Audits**: Periodically scan entire codebase
5. **Incident Response**: Have procedures for when secrets are committed

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Run `ic security config` to verify configuration
3. Use `ic security scan --report report.json` for detailed analysis
4. Review the remediation guide: `ic security remediation`