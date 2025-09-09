# PyPI Deployment with OpenID Connect

This guide explains how to set up automated PyPI publishing using GitHub Actions and OpenID Connect (OIDC) for secure, token-free deployment.

## Overview

OpenID Connect allows GitHub Actions to authenticate with PyPI without storing long-lived API tokens as secrets. This is more secure and eliminates the need to manage API tokens.

## Setup Steps

### 1. Configure PyPI Trusted Publishing

1. **Log in to PyPI** (https://pypi.org)
2. **Go to your account settings** → "Publishing" → "Add a new pending publisher"
3. **Fill in the details**:
   - **PyPI Project Name**: `ic-code` (must match the name in `pyproject.toml`)
   - **Owner**: `dgr009` (e.g., `yourusername`)
   - **Repository name**: `ic`
   - **Workflow name**: `publish-to-pypi.yml`
   - **Environment name**: `pypi` (optional but recommended)

### 2. Create GitHub Environment (Recommended)

1. **Go to your GitHub repository** → Settings → Environments
2. **Create new environment** named `pypi`
3. **Add protection rules** (optional):
   - Required reviewers
   - Wait timer
   - Deployment branches (e.g., only `main` branch)

### 3. Update pyproject.toml

Ensure your `pyproject.toml` has the correct project name:

```toml
[project]
name = "ic-cli"  # This must match the PyPI project name
version = "1.0.0"
# ... other settings
```

### 4. GitHub Actions Workflow

The workflow is already configured in `.github/workflows/publish-to-pypi.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]
  workflow_dispatch:  # Manual trigger

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    - name: Build package
      run: python -m build
    - name: Check package
      run: twine check dist/*
    - name: Upload build artifacts
      uses: actions/upload-artifact@v3
      with:
        name: dist
        path: dist/

  publish:
    needs: build
    runs-on: ubuntu-latest
    environment: pypi  # This references the GitHub environment
    permissions:
      id-token: write  # IMPORTANT: Required for OIDC
    steps:
    - name: Download build artifacts
      uses: actions/download-artifact@v3
      with:
        name: dist
        path: dist/
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        verbose: true
```

## Key Points

### Required Permissions
```yaml
permissions:
  id-token: write  # This is mandatory for trusted publishing
```

### Environment Configuration
- The `environment: pypi` line links to the GitHub environment
- This provides additional security and audit trails
- You can add protection rules in the GitHub environment settings

### Workflow Triggers
- **Automatic**: Triggers when you create a GitHub release
- **Manual**: Can be triggered manually via GitHub Actions UI

## Deployment Process

### Method 1: Create a GitHub Release (Recommended)

1. **Tag your release**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Create GitHub Release**:
   - Go to your repository → Releases → "Create a new release"
   - Choose the tag you just created
   - Add release notes
   - Click "Publish release"

3. **Automatic deployment**: The workflow will automatically trigger and deploy to PyPI

### Method 2: Manual Trigger

1. Go to your repository → Actions → "Publish to PyPI"
2. Click "Run workflow"
3. Select the branch and click "Run workflow"

## Troubleshooting

### Common Issues

1. **"Trusted publisher not configured"**
   - Ensure you've set up the trusted publisher on PyPI correctly
   - Check that all details match exactly (repository name, workflow name, etc.)

2. **"Package already exists"**
   - Update the version number in `pyproject.toml`
   - PyPI doesn't allow overwriting existing versions

3. **"Permission denied"**
   - Ensure the `id-token: write` permission is set
   - Check that the GitHub environment is configured correctly

4. **"Build failed"**
   - Check the build logs in GitHub Actions
   - Ensure all dependencies are correctly specified in `pyproject.toml`

### Verification

After successful deployment:

1. **Check PyPI**: Visit https://pypi.org/project/ic-cli/
2. **Test installation**: 
   ```bash
   pip install ic-cli
   ic --help
   ```

## Security Benefits

- **No API tokens**: No need to store PyPI API tokens as GitHub secrets
- **Short-lived credentials**: OIDC tokens are temporary and automatically managed
- **Audit trail**: All deployments are logged and traceable
- **Environment protection**: GitHub environments can add additional security layers

## Version Management

Update the version in `pyproject.toml` before creating a release:

```toml
[project]
version = "1.0.1"  # Increment for each release
```

Consider using semantic versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## Additional Resources

- [PyPI Trusted Publishing Guide](https://docs.pypi.org/trusted-publishers/)
- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [PyPA GitHub Action](https://github.com/pypa/gh-action-pypi-publish)