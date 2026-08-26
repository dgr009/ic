# IC CLI Release & Deployment Guide

Guide for building, versioning, and publishing IC CLI releases to PyPI.

## 📦 1. Build Requirements

```bash
# Install build and publishing tools
pip install build twine
```

---

## 🚀 2. Release Steps

### Step 1: Bump Version
Update project version in `pyproject.toml` and `src/ic/__init__.py`:

```bash
# Or run release script
./scripts/bump-version.sh patch
```

### Step 2: Build Package
```bash
# Clean previous build artifacts
rm -rf dist/ build/ *.egg-info

# Build wheel and source distribution
python3 -m build
```

### Step 3: Publish to PyPI
```bash
# Upload via script
./scripts/deploy.sh 1.3.3 prod

# Or manually via twine
python3 -m twine upload dist/*
```

### Step 4: Tag Release in Git
```bash
git add -A
git commit -m "release: bump version to 1.3.2"
git tag -a v1.3.2 -m "Release v1.3.2"

git push origin main
git push origin v1.3.2
```
