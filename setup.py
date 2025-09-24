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
from setuptools.command.install import install
from setuptools.command.develop import develop
import os
import sys

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


class PostInstallCommand(install):
    """Custom post-installation command to set up default configuration."""
    
    def run(self):
        install.run(self)
        self._post_install()
    
    def _post_install(self):
        """Run post-installation configuration setup."""
        try:
            # Import here to avoid import errors during setup
            from src.ic.config.installer import ConfigInstaller
            
            installer = ConfigInstaller()
            
            # Check if we should install default configs
            home_config_dir = os.path.expanduser("~/.ic/config")
            local_config_dir = ".ic/config"
            
            # Try to install in user's home directory first
            if not os.path.exists(home_config_dir):
                print("🔧 Setting up default IC configuration...")
                success = installer.install_default_configs(home_config_dir)
                if success:
                    print(f"✅ Default configuration installed in {home_config_dir}")
                    print("💡 You can customize the configuration files as needed.")
                    print("📖 See documentation for configuration options.")
                else:
                    print("⚠️  Could not install default configuration in home directory.")
            else:
                print(f"ℹ️  Configuration directory {home_config_dir} already exists.")
            
        except ImportError:
            # Fallback: create basic configuration structure
            self._create_basic_config_structure()
        except Exception as e:
            print(f"⚠️  Post-installation setup encountered an issue: {e}")
            print("💡 You can manually run 'ic config init' after installation.")
    
    def _create_basic_config_structure(self):
        """Create basic configuration structure as fallback."""
        try:
            home_config_dir = os.path.expanduser("~/.ic/config")
            os.makedirs(home_config_dir, exist_ok=True)
            
            # Create a basic default.yaml
            basic_config = """# IC Configuration
# Run 'ic config init' to generate a complete configuration
version: '2.0'
logging:
  level: INFO
security:
  mask_sensitive_data: true
"""
            
            config_file = os.path.join(home_config_dir, "default.yaml")
            if not os.path.exists(config_file):
                with open(config_file, 'w') as f:
                    f.write(basic_config)
                print(f"✅ Basic configuration created at {config_file}")
                
        except Exception as e:
            print(f"⚠️  Could not create basic configuration: {e}")


class PostDevelopCommand(develop):
    """Custom post-development command for development installations."""
    
    def run(self):
        develop.run(self)
        # For development, we might want different behavior
        print("🔧 Development installation complete.")
        print("💡 Run 'ic config init' to set up configuration for development.")

setup(
    name="ic",
    version=get_version(),
    author="SangYun Kim",
    author_email="cruiser594@gmail.com",
    description="A comprehensive CLI tool for managing cloud infrastructure resources across AWS, Azure, GCP, OCI, NCP, and CloudFlare with built-in security features",
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
    packages=find_packages(where="src") + find_packages(include=["aws*", "azure_module*", "gcp*", "oci_module*", "ncp*", "ncp_module*", "ncpgov*", "ncpgov_module*", "ssh*", "cf*", "common*", "mcp*"]),
    package_dir={"": "src"},
    package_data={
        "ic": ["config/*.yaml", "config/*.json", "config/examples/*.yaml"],
    },
    install_requires=[
        # Core dependencies - Python 3.9-3.12 compatible
        "boto3>=1.26.0,<2.0.0",
        "botocore>=1.29.0,<2.0.0", 
        "requests>=2.28.0,<3.0.0",  # Required for NCP REST API calls
        "rich>=12.0.0,<15.0.0",
        "PyYAML>=6.0,<7.0.0",       # Required for NCP configuration files
        "paramiko>=2.11.0,<5.0.0",
        "python-dotenv>=0.19.0,<2.0.0",
        "cryptography>=3.4.8,<50.0.0",  # Required for NCP HMAC-SHA256 signatures
        "netifaces>=0.11.0,<1.0.0",
        "tqdm>=4.67.0,<5.0.0",
        "jsonschema>=4.23.0,<5.0.0",
        "python-dateutil>=2.8.0,<3.0.0",
        "click>=8.0.0,<9.0.0",
        "packaging>=21.0,<25.0",
        "setuptools>=61.0,<71.0",
        
        # Configuration system dependencies
        "watchdog>=3.0.0,<4.0.0",
        "cerberus>=1.3.4,<2.0.0",
        "pydantic>=2.0.0,<3.0.0",
        
        # Optional cloud platform dependencies (install as needed)
        # AWS: awscli>=1.42.0,<2.0.0, kubernetes>=29.0.0,<31.0.0
        # OCI: oci>=2.149.0,<3.0.0
        # NCP: Uses direct REST API calls (no SDK dependency required)
        # GCP: google-cloud-* packages
        # Azure: azure-* packages
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
        "aws", "azure", "gcp", "oci", "ncp", "naver-cloud", "cloudflare", 
        "infrastructure", "cli", "cloud", "devops",
        "multi-cloud", "resource-management", "security",
        "configuration", "monitoring", "automation",
        "kubernetes", "containers", "serverless"
    ],
    python_requires=">=3.9,<3.13",
    cmdclass={
        'install': PostInstallCommand,
        'develop': PostDevelopCommand,
    },
)
