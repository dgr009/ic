"""
Setup script for IC (Infra Resource Management CLI)

This setup.py is maintained for backward compatibility.
Modern packaging configuration is in pyproject.toml.

Security Notice:
- This package includes security-focused configuration management
- Sensitive data masking and validation features are built-in
- Follow the security guidelines in docs/security.md for proper setup
- Use environment variables for sensitive configuration data
"""

from setuptools import setup, find_packages
import os

# Read version from src/ic/__init__.py
def get_version():
    version_file = os.path.join("src", "ic", "__init__.py")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    return "1.0.0"

# Read long description with security notes
def get_long_description():
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Add security notice to the description
    security_notice = """

## 🔒 Security Notice

This package includes built-in security features:
- **Sensitive data masking** in logs and configuration files
- **Git pre-commit hooks** for security validation
- **Configuration validation** with security warnings
- **Environment variable-based** credential management

**Important**: Never commit sensitive data (API keys, passwords, tokens) to version control. 
Use environment variables or secure credential stores. See `docs/security.md` for detailed security setup instructions.
"""
    
    return content + security_notice

setup(
    name="ic",
    version=get_version(),
    author="SangYun Kim",
    author_email="cruiser594@gmail.com",
    description="A comprehensive CLI tool for managing cloud infrastructure resources across AWS, Azure, GCP, OCI, and CloudFlare with built-in security features",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/dgr009/ic",
    project_urls={
        "Homepage": "https://github.com/dgr009/ic",
        "Repository": "https://github.com/dgr009/ic",
        "Issues": "https://github.com/dgr009/ic/issues",
        "Documentation": "https://github.com/dgr009/ic#readme",
        "Security": "https://github.com/dgr009/ic/blob/main/docs/security.md",
        "Configuration Guide": "https://github.com/dgr009/ic/blob/main/docs/configuration.md",
        "Migration Guide": "https://github.com/dgr009/ic/blob/main/docs/migration.md",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "ic": ["config/*.yaml", "config/*.json", "config/examples/*.yaml"],
    },
    install_requires=[
        "boto3>=1.26.0",
        "oci>=2.100.0",
        "requests>=2.28.0",
        "paramiko>=2.11.0",
        "rich>=12.0.0",
        "InquirerPy>=0.3.0",
        "tqdm>=4.64.0",
        "python-dotenv>=0.19.0",
        "python-dateutil>=2.8.0",
        "kubernetes>=24.0.0",
        "PyYAML>=6.0",
        # Azure SDKs
        "azure-identity>=1.12.0",
        "azure-mgmt-compute>=29.0.0",
        "azure-mgmt-network>=22.0.0",
        "azure-mgmt-containerinstance>=10.0.0",
        "azure-mgmt-containerservice>=20.0.0",
        "azure-mgmt-storage>=21.0.0",
        "azure-mgmt-sql>=4.0.0",
        "azure-mgmt-rdbms>=10.0.0",
        "azure-mgmt-eventhub>=10.0.0",
        "azure-mgmt-resource>=22.0.0",
        "azure-mgmt-subscription>=3.0.0",
        "azure-devops>=7.0.0",
        # Google Cloud SDKs
        "google-cloud-compute>=1.11.0",
        "google-cloud-container>=2.17.0",
        "google-cloud-storage>=2.7.0",
        "google-cloud-functions>=1.8.0",
        "google-cloud-run>=0.9.0",
        "google-cloud-billing>=1.9.0",
        "google-auth>=2.16.0",
        "google-auth-oauthlib>=0.8.0",
        "google-auth-httplib2>=0.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "pre-commit>=2.20.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ic=ic.cli:main"
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Networking",
        "Topic :: Utilities",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Security",
        "Environment :: Console",
        "Natural Language :: English",
        "Natural Language :: Korean",
    ],
    keywords=[
        "aws", "azure", "gcp", "oci", "cloudflare", 
        "infrastructure", "cli", "cloud", "devops",
        "multi-cloud", "resource-management", "security",
        "configuration", "monitoring", "automation",
        "kubernetes", "containers", "serverless"
    ],
    python_requires=">=3.8",
)
