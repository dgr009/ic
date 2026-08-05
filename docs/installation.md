# IC CLI Installation & Configuration Setup

Complete guide for installing IC CLI and setting up configuration.

## 📦 1. Installation

### From PyPI (Recommended)
```bash
pip install ic-code

# Verify installation
ic --version
ic --help
```

### From Source (Development)
```bash
git clone https://github.com/dgr009/ic.git
cd ic

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

---

## ⚙️ 2. Configuration Setup

IC CLI uses a secure two-file configuration system located in `~/.ic/config/`:

```text
~/.ic/config/
├── default.yaml        # Non-sensitive configuration (regions, limits)
└── secrets.yaml        # Sensitive API keys, tokens, and profiles
```

### Initialize Configuration
```bash
# Interactive setup
ic config init

# Validate configuration
ic config validate

# View current configuration (secrets masked)
ic config show
```

### Supported Cloud Credentials
- **AWS**: Native `~/.aws/config` & `~/.aws/credentials` or `secrets.yaml`
- **Tencent Cloud**: Native `~/.tencent/credentials` or `secrets.yaml`
- **GCP**: Application Default Credentials `gcloud auth application-default login`
- **OCI**: Native `~/.oci/config`
- **Cloudflare**: `api_token` in `secrets.yaml`
- **SSH**: Config file `~/.ssh/config` & key directory `~/.ssh/`