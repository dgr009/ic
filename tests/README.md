# IC CLI Test Suite

## 📁 Test Structure & Status

### Supported Platforms & Test Coverage

#### ✅ Supported Platforms (Tested in CI)
- **AWS**: Security Group rules (Ingress/Egress/Tree), EC2, S3, RDS, VPC, EKS, ECS, Fargate
- **GCP**: Compute Engine, Cloud Storage, VPC networks, GKE, Cloud SQL
- **OCI**: VM instances, VCN, Load Balancers, NSG, Volumes, IAM policies
- **CloudFlare**: Zones, DNS records, Accounts
- **SSH**: Server discovery, rule checking, connection management

### Validation & Test Directories

#### `validation/` - End-to-End Validation
- `end_to_end_cli_validation.py` - Complete CLI import, config, and command suite validation
- `ci_cd_pipeline_validation.py` - CI/CD pipeline and runner environment validation
- `security_performance_validation.py` - Security scanning and performance validation

#### `security/` - Security Test Suite
- `test_basic_security.py` - Basic security checks
- `test_configuration_security.py` - Configuration security and permissions validation
- `test_credential_handling.py` - Secret masking and environment variable protection
- `test_git_security_hooks.py` - Git pre-commit security hook checks
- `test_sensitive_data_masking.py` - Sensitive data log masking

#### `integration/` & `unit/`
- `test_basic_integration.py` - Core component integration
- `test_cli_integration.py` - CLI subcommand integration
- `test_config_manager.py` - Configuration manager unit tests
- `test_security_manager.py` - Security manager unit tests

#### `ci/` - CI Test System
- `run_ci_tests.py` - Multi-platform CI test runner
- `setup_ci_environment.py` - CI environment setup & cleanup manager
- `mock_configs.py` - Platform mock configuration and client providers
- `fallback_configs.py` - Environment fallback configuration loader

---

## 🚀 Running Tests

### 1. End-to-End CLI Validation (Recommended)

```bash
python tests/validation/end_to_end_cli_validation.py
```

### 2. Pytest Test Suites

```bash
# Run unit & integration tests
pytest tests/unit tests/integration

# Run specific validation
python tests/validation/security_performance_validation.py
```

### 3. CI Validation Mode

```bash
# Validate CI environment and mock configurations
python tests/ci/setup_ci_environment.py --validate-only
python tests/ci/run_ci_tests.py --validate-only
```

---

**Last Updated**: 2026  
**Maintainer**: IC CLI Team