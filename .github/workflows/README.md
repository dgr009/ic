# IC CLI CI/CD Workflows

## Smart Platform Testing

The CI workflow automatically detects which platforms to test based on:

### 1. Commit Message Tags

Use platform tags in your commit message to trigger specific platform tests:

```bash
# Test single platform
git commit -m "[ncp] Fix EC2 instance listing"
git commit -m "[oci] Update compartment handling"
git commit -m "[aws] Add S3 bucket support"

# Test multiple platforms
git commit -m "[ncp][oci] Update authentication flow"

# Test all platforms
git commit -m "[all] Update core configuration system"
git commit -m "[test-all] Major refactoring"
```

**Supported platform tags:**
- `[ncp]` - Naver Cloud Platform
- `[ncpgov]` - Naver Cloud Platform Government
- `[oci]` - Oracle Cloud Infrastructure
- `[azure]` - Microsoft Azure
- `[aws]` - Amazon Web Services
- `[gcp]` - Google Cloud Platform
- `[ssh]` - SSH Server Management
- `[cf]` - CloudFlare

### 2. Changed Files Detection

If no platform tags are found in the commit message, the workflow automatically detects platforms based on changed files:

```bash
# Changes in src/ic/platforms/ncp/ → tests NCP
# Changes in tests/platforms/oci/ → tests OCI
# Changes in src/ic/platforms/aws/ → tests AWS
```

### 3. Manual Workflow Dispatch

You can manually trigger tests for specific platforms:

1. Go to Actions → IC CLI CI Tests
2. Click "Run workflow"
3. Select platform and test type
4. Click "Run workflow"

## Test Types

The workflow runs three types of tests for each detected platform:

- **Unit Tests**: Fast, isolated tests with mocked dependencies
- **Integration Tests**: Tests with real API interactions (mocked in CI)
- **Performance Tests**: Benchmarks and performance validation

## Examples

### Example 1: NCP Feature Development
```bash
# Edit NCP EC2 code
vim src/ic/platforms/ncp/ec2/info.py

# Commit with NCP tag
git commit -m "[ncp] Add support for GPU instances"
git push

# Result: Only NCP tests run (unit, integration, performance)
```

### Example 2: Multi-Platform Update
```bash
# Update authentication across platforms
vim src/ic/core/auth.py

# Commit with multiple tags
git commit -m "[ncp][oci][aws] Standardize authentication error handling"
git push

# Result: NCP, OCI, and AWS tests run
```

### Example 3: Core System Change
```bash
# Update configuration system
vim src/ic/config/manager.py

# Commit with all tag
git commit -m "[all] Refactor configuration loading system"
git push

# Result: All platform tests run
```

### Example 4: Auto-Detection
```bash
# Edit OCI code without tag
vim src/ic/platforms/oci/vm/info.py

# Commit without platform tag
git commit -m "Fix VM instance filtering"
git push

# Result: OCI tests run automatically (detected from changed files)
```

## Default Behavior

If no platforms are detected:
- **Default platforms tested**: NCP, NCPGov
- **Reason**: These are the most stable and have comprehensive test coverage

## CI Optimization

The workflow is optimized for speed:
- Only tests affected platforms
- Runs tests in parallel across Python 3.11 and 3.12
- Skips platforms without test files
- Uses caching for dependencies

## Test Coverage

Current test coverage by platform:

| Platform | Unit | Integration | Performance | Status |
|----------|------|-------------|-------------|--------|
| NCP | ✅ | ✅ | ✅ | Production |
| NCPGov | ✅ | ✅ | ✅ | Production |
| OCI | ✅ | ✅ | ✅ | Production |
| Azure | ✅ | ✅ | ✅ | Beta |
| AWS | ⚠️ | ⚠️ | ⚠️ | Partial |
| GCP | ⚠️ | ⚠️ | ⚠️ | Partial |
| SSH | ⚠️ | ⚠️ | ⚠️ | Partial |
| CloudFlare | ⚠️ | ⚠️ | ⚠️ | Partial |

## Adding Tests for New Platforms

To add tests for a new platform:

1. Create test directory structure:
```bash
mkdir -p tests/platforms/{platform}/{service}/{unit,integration,performance}
```

2. Add test files:
```bash
tests/platforms/{platform}/{service}/unit/test_{feature}.py
```

3. Tests will automatically run when:
   - Commit message includes `[{platform}]`
   - Files in `src/ic/platforms/{platform}/` are changed
   - Manual workflow dispatch selects the platform

## Troubleshooting

### Tests not running for my platform

Check:
1. Does `tests/platforms/{platform}/` directory exist?
2. Are there any `test_*.py` files in the directory?
3. Did you include the platform tag in commit message?
4. Are the changed files in `src/ic/platforms/{platform}/`?

### All platforms testing when I only changed one

Check:
1. Did you use `[all]` or `[test-all]` tag?
2. Did you change core files that affect all platforms?

### Want to skip CI tests

Add `[skip ci]` or `[ci skip]` to your commit message:
```bash
git commit -m "[skip ci] Update documentation"
```
