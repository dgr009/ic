# CloudFlare Configuration Example for IC CLI

This document provides comprehensive examples for configuring CloudFlare credentials and filters in the IC CLI tool's `secrets.yaml` file.

## Configuration File Location

CloudFlare configuration should be added to your secrets file:

```
~/.ic/config/secrets.yaml
```

**Important:** Never commit this file to version control. It contains sensitive credentials.

---

## Basic Configuration

### Minimal Configuration

The minimum required configuration includes your CloudFlare email and API token:

```yaml
cloudflare:
  email: "your-email@example.com"
  api_token: "your_cloudflare_api_token_here"
```

This configuration will:
- Allow access to all accounts associated with your email
- Display all zones across all accounts
- Enable all CloudFlare commands (`account`, `zone`, `dns`, `traffic`, `waf`, `rules`)

---

## Configuration with Filters

### Account Filtering

Filter which CloudFlare accounts are displayed in commands. This is useful when you have access to multiple accounts but only want to manage specific ones.

#### List Format (Recommended)

```yaml
cloudflare:
  email: "your-email@example.com"
  api_token: "your_cloudflare_api_token_here"
  
  # Show only these accounts (case-insensitive substring matching)
  cloudflare_accounts:
    - "Production"
    - "Development"
    - "Staging"
```

#### Comma-Separated Format

```yaml
cloudflare:
  email: "your-email@example.com"
  api_token: "your_cloudflare_api_token_here"
  
  # Alternative: comma-separated string format
  cloudflare_accounts: "Production,Development,Staging"
```

**Filter Behavior:**
- **Case-insensitive**: "production" matches "Production Account"
- **Substring matching**: "Prod" matches "Production Account"
- **Multiple matches**: All accounts containing any filter term are shown
- **Empty list**: Shows all accounts (same as commenting out the filter)

### Zone Filtering

Filter which zones are displayed in commands. Zones are filtered after account filtering is applied.

#### List Format (Recommended)

```yaml
cloudflare:
  email: "your-email@example.com"
  api_token: "your_cloudflare_api_token_here"
  
  # Show only these zones (case-insensitive substring matching)
  cloudflare_zones:
    - "example.com"
    - "api.example.com"
    - "test.com"
```

#### Comma-Separated Format

```yaml
cloudflare:
  email: "your-email@example.com"
  api_token: "your_cloudflare_api_token_here"
  
  # Alternative: comma-separated string format
  cloudflare_zones: "example.com,api.example.com,test.com"
```

**Filter Behavior:**
- **Case-insensitive**: "example.com" matches "Example.com"
- **Substring matching**: "example" matches "example.com", "api.example.com", "test.example.com"
- **Multiple matches**: All zones containing any filter term are shown
- **Empty list**: Shows all zones (same as commenting out the filter)

---

## Complete Configuration Examples

### Example 1: Production Environment

Configuration for managing production infrastructure only:

```yaml
cloudflare:
  # CloudFlare API credentials
  email: "devops@company.com"
  api_token: "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
  
  # Only show production account
  cloudflare_accounts:
    - "Production"
  
  # Only show production domains
  cloudflare_zones:
    - "company.com"
    - "api.company.com"
    - "cdn.company.com"
```

**Use Case:** DevOps team member who only manages production infrastructure.

### Example 2: Multi-Environment Management

Configuration for managing multiple environments:

```yaml
cloudflare:
  # CloudFlare API credentials
  email: "admin@company.com"
  api_token: "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
  
  # Show production, staging, and development accounts
  cloudflare_accounts:
    - "Production"
    - "Staging"
    - "Development"
  
  # Show all company domains across environments
  cloudflare_zones:
    - "company.com"
    - "staging.company.com"
    - "dev.company.com"
    - "api.company.com"
```

**Use Case:** Platform administrator managing multiple environments.

### Example 3: No Filtering (Show All)

Configuration to see all accounts and zones:

```yaml
cloudflare:
  # CloudFlare API credentials
  email: "admin@company.com"
  api_token: "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
  
  # No filters - show all accounts and zones
  # Comment out or leave empty to show everything
  # cloudflare_accounts:
  # cloudflare_zones:
```

**Use Case:** CloudFlare administrator who needs visibility into all accounts and zones.

### Example 4: Specific Domains Only

Configuration for managing specific domains without account filtering:

```yaml
cloudflare:
  # CloudFlare API credentials
  email: "webmaster@company.com"
  api_token: "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
  
  # Show all accounts (no account filter)
  # cloudflare_accounts:
  
  # Only show specific domains
  cloudflare_zones:
    - "blog.company.com"
    - "docs.company.com"
    - "support.company.com"
```

**Use Case:** Content team member managing specific web properties.

### Example 5: Development and Testing

Configuration for development and testing environments:

```yaml
cloudflare:
  # CloudFlare API credentials
  email: "developer@company.com"
  api_token: "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
  
  # Only show development and testing accounts
  cloudflare_accounts:
    - "Development"
    - "Testing"
    - "QA"
  
  # Show all zones in these accounts
  # cloudflare_zones:
```

**Use Case:** Developer working on non-production environments.

---

## Filter Behavior Details

### How Filters Work

1. **Account Filtering (First)**
   - Filters are applied to account names
   - Case-insensitive substring matching
   - If no account filter is specified, all accounts are included

2. **Zone Filtering (Second)**
   - Filters are applied to zone names within filtered accounts
   - Case-insensitive substring matching
   - If no zone filter is specified, all zones from filtered accounts are included

3. **CLI Override**
   - Command-line arguments (`-a`, `-z`) override configuration filters
   - Example: `ic cf zone info -a Production` overrides `cloudflare_accounts` config

### Filter Priority

```
CLI Arguments > Configuration File > Default (show all)
```

### Matching Examples

**Account Filter: "Production"**
- ✅ Matches: "Production", "Production Account", "production-env"
- ❌ Does not match: "Staging", "Development"

**Zone Filter: "example"**
- ✅ Matches: "example.com", "api.example.com", "test.example.org"
- ❌ Does not match: "mysite.com", "test.com"

**Multiple Filters: ["example", "test"]**
- ✅ Matches: "example.com", "test.com", "api.example.com", "test.example.com"
- ❌ Does not match: "mysite.com", "production.com"

---

## Getting Your API Token

### Step-by-Step Guide

1. **Log in to CloudFlare Dashboard**
   - Go to: https://dash.cloudflare.com/

2. **Navigate to API Tokens**
   - Click on your profile icon (top right)
   - Select "My Profile"
   - Click "API Tokens" tab
   - Or go directly to: https://dash.cloudflare.com/profile/api-tokens

3. **Create API Token**
   - Click "Create Token" button
   - Choose "Read all resources" template (recommended)
   - Or create custom token with specific permissions (see below)

4. **Configure Token Permissions (Custom Token)**
   
   **Account Permissions:**
   - Account Settings: Read
   
   **Zone Permissions:**
   - Zone: Read
   - DNS: Read
   - Analytics: Read
   - Firewall Services: Read
   - Page Rules: Read

5. **Set Token Restrictions (Optional but Recommended)**
   - **IP Address Filtering**: Restrict to your IP addresses
   - **TTL**: Set expiration date for security
   - **Zone Resources**: Limit to specific zones if needed

6. **Generate and Copy Token**
   - Click "Continue to summary"
   - Review permissions
   - Click "Create Token"
   - **Important**: Copy the token immediately (it won't be shown again)

7. **Add to Configuration**
   - Paste the token into your `~/.ic/config/secrets.yaml` file
   - Ensure the file has restricted permissions: `chmod 600 ~/.ic/config/secrets.yaml`

### Recommended Token Permissions

For full IC CLI functionality, your API token should have:

```
Account Permissions:
  - Account Settings: Read

Zone Permissions:
  - Zone: Read
  - DNS: Read
  - Analytics: Read
  - Firewall Services: Read
  - Page Rules: Read
```

### Security Best Practices

1. **Use API Tokens, Not Global API Keys**
   - API tokens have granular permissions
   - Can be revoked individually
   - Can be restricted by IP and TTL

2. **Principle of Least Privilege**
   - Only grant "Read" permissions for IC CLI
   - Don't grant "Edit" or "Delete" unless needed

3. **Token Rotation**
   - Rotate tokens regularly (every 90 days recommended)
   - Set TTL when creating tokens

4. **Secure Storage**
   - Keep `secrets.yaml` out of version control
   - Set file permissions: `chmod 600 ~/.ic/config/secrets.yaml`
   - Never share tokens in chat, email, or documentation

5. **IP Restrictions**
   - Restrict tokens to known IP addresses when possible
   - Update restrictions when IP addresses change

---

## Testing Your Configuration

### Verify Configuration

After adding CloudFlare configuration, test it:

```bash
# Test account access
ic cf account info

# Test zone access
ic cf zone info

# Test with filters
ic cf zone info -a Production
ic cf zone info -z example.com
```

### Validate Configuration File

```bash
# Validate YAML syntax and structure
ic config validate

# Show merged configuration (credentials masked)
ic config show
```

### Troubleshooting

**Problem: Authentication Failed**
```
❌ CloudFlare authentication failed
```

**Solutions:**
1. Verify email and api_token in `secrets.yaml`
2. Check token permissions in CloudFlare dashboard
3. Ensure token is not expired
4. Verify email matches the account associated with the token

**Problem: No Data Returned**
```
Commands run but show no accounts/zones
```

**Solutions:**
1. Check if filters are too restrictive
2. Try without filters: comment out `cloudflare_accounts` and `cloudflare_zones`
3. Verify your CloudFlare account has zones
4. Check token permissions include read access

**Problem: Rate Limit Exceeded**
```
⚠️ CloudFlare API rate limit exceeded
```

**Solutions:**
1. Wait for the suggested retry time
2. Reduce the number of zones/accounts using filters
3. Consider upgrading CloudFlare plan for higher rate limits

---

## Complete Configuration Template

Copy this template to `~/.ic/config/secrets.yaml` and customize:

```yaml
# CloudFlare Configuration for IC CLI
# Location: ~/.ic/config/secrets.yaml
# IMPORTANT: Never commit this file to version control

cloudflare:
  # Required: Your CloudFlare account email
  email: "your-email@example.com"
  
  # Required: Your CloudFlare API token
  # Get token from: https://dash.cloudflare.com/profile/api-tokens
  api_token: "your_cloudflare_api_token_here"
  
  # Optional: Filter accounts (show only matching accounts)
  # Supports both list format and comma-separated string
  # Comment out or leave empty to show all accounts
  # Case-insensitive substring matching
  cloudflare_accounts:
    - "Production"
    - "Development"
    - "Staging"
  # Or use comma-separated format:
  # cloudflare_accounts: "Production,Development,Staging"
  
  # Optional: Filter zones (show only matching zones)
  # Supports both list format and comma-separated string
  # Comment out or leave empty to show all zones
  # Case-insensitive substring matching
  # Applied after account filtering
  cloudflare_zones:
    - "example.com"
    - "api.example.com"
    - "test.com"
  # Or use comma-separated format:
  # cloudflare_zones: "example.com,api.example.com,test.com"

# Other platform configurations can be added below
# aws:
#   ...
# azure:
#   ...
```

---

## Additional Resources

**IC CLI Documentation:**
- CloudFlare Platform README: `src/ic/platforms/cloudflare/README.md`
- General Configuration Guide: `docs/general/configuration.md`
- Main README: `README.md`

**CloudFlare Resources:**
- API Documentation: https://developers.cloudflare.com/api/
- Dashboard: https://dash.cloudflare.com/
- API Tokens: https://dash.cloudflare.com/profile/api-tokens
- Status Page: https://www.cloudflarestatus.com/

**Security:**
- Never commit `secrets.yaml` to version control
- Add to `.gitignore`: `secrets.yaml`, `**/secrets.yaml`
- Set file permissions: `chmod 600 ~/.ic/config/secrets.yaml`
- Rotate API tokens regularly

---

## Quick Start Checklist

- [ ] Create `~/.ic/config/secrets.yaml` if it doesn't exist
- [ ] Add CloudFlare email and API token
- [ ] Set file permissions: `chmod 600 ~/.ic/config/secrets.yaml`
- [ ] (Optional) Add account and zone filters
- [ ] Test configuration: `ic cf account info`
- [ ] Verify access: `ic cf zone info`
- [ ] Review logs for any issues: `~/.ic/logs/ic_YYYYMMDD.log`

---

**Last Updated:** November 2024  
**IC CLI Version:** 1.2.x+  
**CloudFlare API Version:** v4
