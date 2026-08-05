# Cloudflare Platform Guide

This document covers configuration, account filtering, and commands for Cloudflare in IC CLI.

## ⚙️ Configuration (`~/.ic/config/secrets.yaml`)

Add your Cloudflare credentials to your secrets file:

```yaml
cloudflare:
  email: "user@example.com"
  api_token: "your-cloudflare-api-token"

  # Optional filtering
  cloudflare_accounts:
    - "Production"
    - "Development"
  cloudflare_zones:
    - "example.com"
    - "my-app.io"
```

## 🚀 Available Commands

### 1. Zone Information
```bash
# List all discovered zones
ic cf zone info
```

### 2. DNS Record Management
```bash
# List DNS records for zones
ic cf dns info
```
