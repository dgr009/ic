# IC (Infra Resource Management CLI)

`IC` is a Python-based CLI tool designed to **manage tags, collect resources, validate configurations, and automate operations** across AWS, OCI, Cloudflare, and SSH-based infrastructure environments.

- Manage and validate AWS resource tags (EC2, LB, RDS, S3, VPC, etc.)
- Retrieve Cloudflare DNS records
- Collect OCI resource and cost information in parallel
- Scan and register SSH servers with system details

---

## ⭐️ Key Features Summary

| Platform      | Service | Key Features |
|---------------|---------|--------------|
| **AWS**       | EC2, LB, VPC, RDS, S3 | Resource info, tag listing, regex-based tag validation |
| **Cloudflare**| DNS     | DNS record discovery |
| **OCI**       | Instance, LB, NSG, Volume, Object, Cost | Parallel resource/cost/credit collection |
| **SSH**       | SSH config | Parallel server health check + resource stats collection |

---

## 📂 Project Structure

```
ic/
├── cli.py                         # CLI Entry Point
├── common/                        # Shared utilities and logging
│   ├── log.py
│   ├── utils.py
│   ├── slack.py
│   └── gather_env.py
├── aws/
│   ├── ec2/ list_tags.py, tag_check.py, list_info.py
│   ├── lb/  list_tags.py, tag_check.py
│   ├── rds/ list_tags.py, tag_check.py
│   ├── s3/  list_tags.py, tag_check.py
│   └── vpc/ list_tags.py, tag_check.py
├── cf/
│   └── dns/ list_info.py
├── oci_module/
│   └── info.py                   # Parallel OCI resource collector
├── ssh/
│   ├── server_info.py            # SSH parallel info gatherer
│   └── auto_ssh.py               # Auto SSH registration helper
└── .env / .env.example           # Environment configuration
```

---

## 🚀 Installation & Execution

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Install CLI locally
```bash
pip install .
# or for development
pip install -e .
```

### 3. Configure .env file
Reference `.env.example` and create a `.env`:
```ini
# -------  COMMON ENV ----------
LOG_LEVEL=INFO  # Log level setting
SLACK_WEBHOOK_URL=https://hooks.slack.com/webhookslackurl

# --------- AWS ENV ------------
REGIONS=ap-northeast-2         # aws regions. ex) ap-northeast-1,ap-northeast-2
AWS_ACCOUNTS=0000000000         # aws Account. ex) 229930918337,229930918337

# --------- TAG ENV ------------
REQUIRED_TAGS=User,Team,Name,Service,Application,Role,Environment
OPTIONAL_TAGS=
RULE_USER=^.+$
RULE_TEAM=^\d+$
RULE_NAME=^[a-zA-Z0-9_.\-/+() ]+$
RULE_ROLE=^[a-zA-Z0-9_\-+, ]+$
RULE_ENVIRONMENT=^(PROD|STG|DEV|TEST|QA)$


# --------- CloudFlare ------------
CLOUDFLARE_EMAIL=cruiser594@gmail.com     # Account Login Email
CLOUDFLARE_API_TOKEN=tokentokentoken        # Account Token(Account Level)
CLOUDFLARE_ACCOUNTS=account_name       # Account (NAME)
CLOUDFLARE_ZONES=zone_name             # HOSTZONE (NAME)


# --------- SSH ------------
SSH_KEY_DIR=~/your_key_dir               # defualt keyfile directory path
SSH_CONFIG_FILE=~/.ssh/config       # ~/.ssh/config file path
SSH_MAX_WORKER=70                   # worker number
PORT_OPEN_TIMEOUT=0.5               # port scan(SSH) timeout (Seconds)
SSH_TIMEOUT=5                      # SSH Connection timeout (Seconds)
```

---

## ⚖️ Command Examples

```bash
ic aws ec2 list_tags --account 123456789012 --regions ap-northeast-2
ic aws ec2 tag_check
ic aws rds list_tags
ic cf dns list_info
ic oci info --instance --cost
ic ssh info
```

### AWS Supported Services
- `ec2`, `lb`, `vpc`, `rds`, `s3`
- Commands: `list_tags`, `tag_check`, `list_info`

### Cloudflare
- `cf dns list_info`: View DNS records

### OCI
- `oci info --instance`, `--lb`, `--nsg`, `--volume`, `--object`, `--cost`, `--credit`

### SSH
- `ssh info`: Collect server health, disk/CPU/memory in parallel

---

## 📊 Execution Pipeline Overview

- Uses `.env` for account/region → profiles mapped via `common.utils.get_profiles()`
- Parallel collection using `ThreadPoolExecutor` (account x region combinations)
- Output presented via `rich.Table` + optional Slack notifications
- `tag_check` verifies tag compliance using regex patterns

---

## 💬 Slack Notification (Optional)

- Use `.env` variable `SLACK_WEBHOOK_URL`
- Supported functions:
  - `send_slack_message()`
  - `send_slack_blocks_table()` / `..._with_color()`
- Prevents `too_many_attachments` & `413 Payload Too Large` errors

---

## ⚠️ Notes & Cautions

- S3 region issues: Handle `IllegalLocationConstraintException`
- Slack message size limitations require row count controls
- Regex rules (`RULE_XXX`) merge `.env` values with hardcoded defaults
- SSH expects `.ssh/config` based registered hosts
- AWS interaction relies on `aws-vault`, `~/.aws/config`, or `~/.aws/credentials`

---

## 🚧 Future Enhancements

- Planned: `apply_tags`, `backup_tags`, `excel_to_json` modules
- Integration with Terraform / CloudFormation tagging
- Periodic validation via GitHub Actions or Jenkins pipelines

---

## 📅 Maintainer / Contact

- Maintainer: **cruiser594@gmail.com**
- License: MIT