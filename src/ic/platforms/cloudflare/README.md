# CloudFlare Platform Integration

Comprehensive CloudFlare management commands for the IC CLI tool. Manage accounts, zones, DNS records, traffic analytics, WAF rules, and page rules across your CloudFlare infrastructure.

---

## 🚀 Features

- **Account Management**: View and filter CloudFlare accounts
- **Zone Management**: List zones with detailed information grouped by account
- **DNS Records**: View DNS records for zones with filtering
- **Traffic Analytics**: Monitor bandwidth, requests, cache performance, and threats
- **WAF Rules**: Display and audit Web Application Firewall security rules
- **Page Rules**: View URL-based behavior configurations
- **Configuration Filtering**: Filter accounts and zones via configuration file
- **Rich Terminal UI**: Beautiful tables, trees, and progress indicators
- **License Support**: Handles both Enterprise and Free CloudFlare zones

---

## 📋 Available Commands

All CloudFlare commands follow the pattern: `ic cf <service> <command> [options]`

| Service | Command | Description |
|---------|---------|-------------|
| `account` | `info` | Display CloudFlare account information |
| `zone` | `info` | List zones with details grouped by account |
| `dns` | `info` | View DNS records for zones |
| `traffic` | `info` | Show traffic analytics with configurable time windows |
| `waf` | `info` | Display WAF/firewall security rules |
| `rules` | `info` | Show page rules for zones |

---

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.9 or higher
- IC CLI tool installed (`pip install ic-code`)
- CloudFlare account with API access

### Configuration

Configure CloudFlare credentials in `~/.ic/config/secrets.yaml`:

```yaml
cloudflare:
  email: "your-email@example.com"
  api_token: "your_cloudflare_api_token"
  
  # Optional: Filter accounts (show only matching accounts)
  # Comment out or leave empty to show all accounts
  cloudflare_accounts:
    - "Production"
    - "Development"
  # Or use comma-separated format:
  # cloudflare_accounts: "Production,Development"
  
  # Optional: Filter zones (show only matching zones)
  # Comment out or leave empty to show all zones
  cloudflare_zones:
    - "example.com"
    - "test.com"
  # Or use comma-separated format:
  # cloudflare_zones: "example.com,test.com"
```

**📖 For detailed configuration examples and explanations, see:**
- [CloudFlare Configuration Examples](../../../docs/cloudflare_configuration_example.md) - Comprehensive guide with multiple use cases

### Getting Your API Token

1. Go to [CloudFlare Dashboard > My Profile > API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Click "Create Token"
3. Use "Read all resources" template or create custom token with:
   - **Account**: `Account Settings - Read`
   - **Zone**: `Zone - Read`, `DNS - Read`, `Analytics - Read`, `Firewall Services - Read`
4. Copy the generated token to your `secrets.yaml`

---

## 📖 Command Usage & Examples

### Account Info

Display CloudFlare account information with optional filtering.

**Basic Usage:**
```bash
# Show all accounts (respects config filters)
ic cf account info

# Filter by account name (overrides config)
ic cf account info -a Production
ic cf account info --account "Dev"
```

**Output Example:**
```
CloudFlare Accounts
┌──────────────────────────────────────┬─────────────────────┬────────────┬────────────┐
│ Account ID                           │ Name                │ Type       │ Settings   │
├──────────────────────────────────────┼─────────────────────┼────────────┼────────────┤
│ abc123def456...                      │ Production Account  │ Enterprise │ 2FA: ✓     │
│ ghi789jkl012...                      │ Development Account │ Free       │ 2FA: ✗     │
└──────────────────────────────────────┴─────────────────────┴────────────┴────────────┘
```

**CLI Options:**
- `-a, --account <name>`: Filter accounts by name (case-insensitive substring match)

---

### Zone Info

List zones with detailed information grouped by account.

**Basic Usage:**
```bash
# Show all zones (respects config filters)
ic cf zone info

# Filter by account
ic cf zone info -a Production

# Filter by zone name
ic cf zone info -z example.com

# Combine filters
ic cf zone info -a Production -z example
```

**Output Example:**
```
Production Account
┌──────────────────────────────────────┬─────────────────┬────────┬────────────┬─────────────────────┐
│ Zone ID                              │ Name            │ Status │ License    │ Nameservers         │
├──────────────────────────────────────┼─────────────────┼────────┼────────────┼─────────────────────┤
│ zone123abc...                        │ example.com     │ active │ Enterprise │ ns1.cloudflare.com  │
│ zone456def...                        │ api.example.com │ active │ Enterprise │ ns2.cloudflare.com  │
└──────────────────────────────────────┴─────────────────┴────────┴────────────┴─────────────────────┘

Development Account
┌──────────────────────────────────────┬─────────────────┬────────┬────────────┬─────────────────────┐
│ Zone ID                              │ Name            │ Status │ License    │ Nameservers         │
├──────────────────────────────────────┼─────────────────┼────────┼────────────┼─────────────────────┤
│ zone789ghi...                        │ test.com        │ active │ Free       │ ns3.cloudflare.com  │
└──────────────────────────────────────┴─────────────────┴────────┴────────────┴─────────────────────┘
```

**CLI Options:**
- `-a, --account <name>`: Filter by account name
- `-z, --zone <name>`: Filter by zone name

---

### DNS Records

View DNS records for zones with filtering support.

**Basic Usage:**
```bash
# Show DNS records for all zones (respects config filters)
ic cf dns info

# Filter by account
ic cf dns info -a Production

# Filter by zone
ic cf dns info -z example.com

# Combine filters
ic cf dns info -a Production -z example
```

**Output Example:**
```
Production Account - example.com
┌──────┬──────────────┬─────────────────┬──────────┬───────┬─────┬────────────────────┐
│ Type │ Name         │ Content         │ Priority │ Proxy │ TTL │ Modified           │
├──────┼──────────────┼─────────────────┼──────────┼───────┼─────┼────────────────────┤
│ A    │ @            │ 192.0.2.1       │ -        │ ✓     │ Auto│ 2024-11-15 10:30   │
│ CNAME│ www          │ example.com     │ -        │ ✓     │ Auto│ 2024-11-15 10:30   │
│ MX   │ @            │ mail.example.com│ 10       │ ✗     │ 3600│ 2024-11-10 14:22   │
│ TXT  │ @            │ v=spf1 ...      │ -        │ ✗     │ 3600│ 2024-11-01 09:15   │
└──────┴──────────────┴─────────────────┴──────────┴───────┴─────┴────────────────────┘
```

**CLI Options:**
- `-a, --account <name>`: Filter by account name
- `-z, --zone <name>`: Filter by zone name

**Note:** The `list_info` command is deprecated. Use `info` instead.

---

### Traffic Analytics

Monitor traffic analytics with configurable time windows. Supports both Enterprise and Free zones with appropriate data availability.

**Basic Usage:**
```bash
# Show analytics for last 8 hours (default)
ic cf traffic info

# Custom time window
ic cf traffic info -t 24h
ic cf traffic info -t 1d
ic cf traffic info -t 30m

# Filter by account/zone
ic cf traffic info -a Production -t 12h
ic cf traffic info -z example.com -t 1d
```

**Time Window Formats:**
- `5m`, `30m` - Minutes (e.g., last 5 minutes, last 30 minutes)
- `1h`, `8h`, `24h` - Hours (e.g., last 1 hour, last 8 hours, last 24 hours)
- `1d`, `7d`, `30d` - Days (e.g., last 1 day, last 7 days, last 30 days)

**Output Example:**
```
Traffic Analytics (Last 8 hours)

Production Account - example.com [Enterprise]
┌─────────────────┬──────────────┬────────────┬───────────────┬─────────────────┐
│ Metric          │ Value        │ Change     │ Peak          │ Cache Hit Ratio │
├─────────────────┼──────────────┼────────────┼───────────────┼─────────────────┤
│ Total Requests  │ 1,234,567    │ +12.5%     │ 45,678/hour   │ 87.3%           │
│ Bandwidth       │ 123.4 GB     │ +8.2%      │ 5.2 GB/hour   │ -               │
│ Unique Visitors │ 45,678       │ +15.3%     │ 2,345/hour    │ -               │
│ Threats Blocked │ 1,234        │ -5.2%      │ 67/hour       │ -               │
└─────────────────┴──────────────┴────────────┴───────────────┴─────────────────┘

Development Account - test.com [Free]
┌─────────────────┬──────────────┬────────────┬───────────────┬─────────────────┐
│ Metric          │ Value        │ Change     │ Peak          │ Cache Hit Ratio │
├─────────────────┼──────────────┼────────────┼───────────────┼─────────────────┤
│ Total Requests  │ 12,345       │ +5.2%      │ 456/hour      │ Limited data    │
│ Bandwidth       │ 1.2 GB       │ +3.1%      │ 52 MB/hour    │ -               │
│ Unique Visitors │ N/A          │ N/A        │ N/A           │ -               │
│ Threats Blocked │ N/A          │ N/A        │ N/A           │ -               │
└─────────────────┴──────────────┴────────────┴───────────────┴─────────────────┘
```

**CLI Options:**
- `-a, --account <name>`: Filter by account name
- `-z, --zone <name>`: Filter by zone name
- `-t, --time <window>`: Time window (default: 8h)

**License-Specific Data:**
- **Enterprise zones**: Full analytics including unique visitors, threats, detailed cache metrics
- **Free zones**: Basic analytics (requests, bandwidth), limited or unavailable advanced metrics

---

### WAF Security Rules

Display Web Application Firewall rules in a hierarchical tree structure with color coding.

**Basic Usage:**
```bash
# Show WAF rules for all zones (respects config filters)
ic cf waf info

# Filter by account/zone
ic cf waf info -a Production
ic cf waf info -z example.com
```

**Output Example:**
```
Production Account - example.com

WAF Security Rules
├── [ENABLED] Block SQL Injection (Priority: 1)
│   ├── Action: block
│   ├── Expression: (http.request.uri.query contains "union select")
│   └── Description: Blocks common SQL injection patterns
├── [ENABLED] Challenge Suspicious Bots (Priority: 2)
│   ├── Action: challenge
│   ├── Expression: (cf.bot_management.score lt 30)
│   └── Description: Challenges low-scoring bot traffic
└── [DISABLED] Rate Limit API (Priority: 3)
    ├── Action: block
    ├── Expression: (http.request.uri.path contains "/api/")
    └── Description: Rate limits API endpoints (currently disabled)

Development Account - test.com
No WAF rules configured
```

**CLI Options:**
- `-a, --account <name>`: Filter by account name
- `-z, --zone <name>`: Filter by zone name

**Color Coding:**
- **Block actions**: Red (bright if enabled, dim if disabled)
- **Challenge actions**: Yellow (bright if enabled, dim if disabled)
- **Allow actions**: Green (bright if enabled, dim if disabled)

---

### Page Rules

Display CloudFlare page rules in a hierarchical tree structure showing URL patterns and actions.

**Basic Usage:**
```bash
# Show page rules for all zones (respects config filters)
ic cf rules info

# Filter by account/zone
ic cf rules info -a Production
ic cf rules info -z example.com
```

**Output Example:**
```
Production Account - example.com

Page Rules
├── [ENABLED] Cache Everything for Static Assets (Priority: 1)
│   ├── URL Pattern: *example.com/static/*
│   ├── Actions:
│   │   ├── Cache Level: cache_everything
│   │   ├── Edge Cache TTL: 86400
│   │   └── Browser Cache TTL: 14400
│   └── Status: active
├── [ENABLED] Force HTTPS (Priority: 2)
│   ├── URL Pattern: http://*example.com/*
│   ├── Actions:
│   │   └── Always Use HTTPS: on
│   └── Status: active
└── [DISABLED] Redirect Old Domain (Priority: 3)
    ├── URL Pattern: *old.example.com/*
    ├── Actions:
    │   └── Forwarding URL: 301 to https://example.com/$1
    └── Status: disabled

Development Account - test.com
No page rules configured
```

**CLI Options:**
- `-a, --account <name>`: Filter by account name
- `-z, --zone <name>`: Filter by zone name

---

## 🔧 Configuration Details

### Filter Behavior

**Account Filters (`cloudflare_accounts`):**
- Supports both list format and comma-separated string
- Case-insensitive substring matching
- Empty or commented = show all accounts
- CLI `-a` option overrides configuration

**Zone Filters (`cloudflare_zones`):**
- Supports both list format and comma-separated string
- Case-insensitive substring matching
- Empty or commented = show all zones
- CLI `-z` option overrides configuration
- Applied after account filtering

**Filter Priority:**
```
CLI Arguments > Configuration File > Default (show all)
```

### Configuration Examples

**List Format:**
```yaml
cloudflare:
  cloudflare_accounts:
    - "Production"
    - "Development"
    - "Staging"
  cloudflare_zones:
    - "example.com"
    - "api.example.com"
```

**Comma-Separated Format:**
```yaml
cloudflare:
  cloudflare_accounts: "Production,Development,Staging"
  cloudflare_zones: "example.com,api.example.com"
```

**Show All (No Filtering):**
```yaml
cloudflare:
  # cloudflare_accounts:  # Commented out = show all
  # cloudflare_zones:     # Commented out = show all
```

---

## 🗂️ Logging

All CloudFlare operations are logged to the IC CLI log file with detailed information:

**Log Location:** `~/.ic/logs/ic_YYYYMMDD.log` or `src/logs/ic_YYYYMMDD.log`

**Logged Information:**
- API request details (endpoints, parameters)
- Response times for performance monitoring
- Filter application (accounts, zones)
- Result counts (accounts fetched, zones processed)
- Error details with full tracebacks
- **Note:** Credentials are never logged

**Console Output:**
- Minimal, clean output focused on results
- Progress indicators for long operations
- User-friendly error messages
- Rich tables and trees for data visualization

---

## ⚠️ Troubleshooting

### Authentication Errors

**Problem:** `❌ CloudFlare authentication failed`

**Solutions:**
1. Verify credentials in `~/.ic/config/secrets.yaml`:
   ```yaml
   cloudflare:
     email: "your-email@example.com"
     api_token: "your_token_here"
   ```
2. Check that your API token has required permissions:
   - Account: `Account Settings - Read`
   - Zone: `Zone - Read`, `DNS - Read`, `Analytics - Read`, `Firewall Services - Read`
3. Verify token is not expired in CloudFlare dashboard
4. Ensure email matches the account associated with the token

### Rate Limit Errors

**Problem:** `⚠️ CloudFlare API rate limit exceeded`

**Solutions:**
1. Wait for the suggested retry time (shown in error message)
2. Reduce the number of zones/accounts being queried using filters
3. Increase time between API calls
4. Consider upgrading CloudFlare plan for higher rate limits

### Network Errors

**Problem:** `❌ Network error connecting to CloudFlare API`

**Solutions:**
1. Check internet connectivity
2. Verify firewall/proxy settings allow HTTPS to `api.cloudflare.com`
3. Check if CloudFlare API is experiencing outages: https://www.cloudflarestatus.com/
4. Try again after a few moments

### Configuration Errors

**Problem:** `❌ CloudFlare configuration error`

**Solutions:**
1. Verify `secrets.yaml` syntax is valid YAML
2. Check that `email` and `api_token` fields are present
3. Ensure filter formats are correct (list or comma-separated string)
4. Run `ic config validate` to check configuration

### No Data Returned

**Problem:** Commands run successfully but show no data

**Solutions:**
1. Check if filters are too restrictive:
   ```bash
   # Try without filters
   ic cf account info
   ic cf zone info
   ```
2. Verify your CloudFlare account has zones/resources
3. Check API token permissions include read access
4. Review log file for detailed error messages

### Missing Analytics Data

**Problem:** Traffic analytics show "N/A" or "Limited data"

**Solutions:**
1. **Free zones**: Some metrics are only available on paid plans
   - Unique visitors, threats blocked, detailed cache metrics require Enterprise
2. **New zones**: Analytics may not be available for newly created zones
3. **Time window**: Try a longer time window (e.g., `-t 24h` instead of `-t 1h`)
4. **Enterprise zones**: Verify GraphQL Analytics API is enabled

### Deprecated Command Warning

**Problem:** `⚠️ The 'list_info' command is deprecated`

**Solution:**
- Use the new command name: `ic cf dns info` instead of `ic cf dns list_info`
- Update any scripts or documentation to use the new command
- The old command will be removed in a future version

---

## 📊 Performance Considerations

**API Call Optimization:**
- Filters are applied before making API calls when possible
- Pagination is handled automatically for large result sets
- Connection pooling for multiple API requests
- 30-second timeout for all API requests

**Expected Performance:**
- Account retrieval: < 2 seconds for 10 accounts
- Zone retrieval: < 5 seconds for 100 zones
- DNS records: < 3 seconds for 1000 records per zone
- Analytics retrieval: < 10 seconds for 10 zones
- WAF rules: < 5 seconds for 100 rules per zone
- Page rules: < 3 seconds for 50 rules per zone

---

## 🔒 Security Best Practices

1. **Never commit credentials**: Keep `secrets.yaml` out of version control
2. **Use API tokens**: Prefer API tokens over Global API Keys
3. **Minimal permissions**: Grant only required permissions to API tokens
4. **Rotate tokens**: Regularly rotate API tokens
5. **Audit logs**: Review log files for suspicious activity
6. **Secure storage**: Ensure `~/.ic/config/` has appropriate file permissions (600)

---

## 📞 Support & Resources

**Documentation:**
- IC CLI Documentation: See main README.md
- CloudFlare API Docs: https://developers.cloudflare.com/api/

**Getting Help:**
- Check log files for detailed error information
- Review this troubleshooting section
- Verify configuration with `ic config validate`
- Contact your system administrator for access issues

**CloudFlare Resources:**
- Dashboard: https://dash.cloudflare.com/
- API Tokens: https://dash.cloudflare.com/profile/api-tokens
- Status Page: https://www.cloudflarestatus.com/

---

## 📄 License

This module is part of the IC CLI tool and follows the same license terms.

