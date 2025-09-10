"""
Dependency validation module for IC CLI.

This module provides comprehensive dependency validation and management
for Python 3.9-3.12 compatibility across all cloud platform modules.
"""

import sys
import importlib
import subprocess
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import pkg_resources
from packaging import version
import logging

logger = logging.getLogger(__name__)


@dataclass
class DependencyInfo:
    """Information about a dependency requirement."""
    name: str
    required_version: str
    installed_version: Optional[str] = None
    is_available: bool = False
    is_compatible: bool = False
    error_message: Optional[str] = None


class DependencyValidator:
    """
    Validates and manages dependencies for IC CLI.
    
    Features:
    - Python version compatibility checking (3.9-3.12)
    - Package availability and version validation
    - Clear error messages for missing or incompatible packages
    - Dependency conflict detection
    - Installation guidance
    """
    
    # Core dependencies required for basic functionality
    CORE_DEPENDENCIES = {
        "boto3": ">=1.26.0",
        "requests": ">=2.28.0", 
        "rich": ">=12.0.0",
        "PyYAML": ">=6.0",
        "paramiko": ">=2.11.0",
        "python-dotenv": ">=0.19.0",
        "cryptography": ">=3.4.8",
        "tqdm": ">=4.67.0",
    }
    
    # Optional dependencies for specific cloud platforms
    OPTIONAL_DEPENDENCIES = {
        "aws": {
            "awscli": ">=1.42.0",
            "kubernetes": ">=29.0.0",
        },
        "oci": {
            "oci": ">=2.149.0",
        },
        "gcp": {
            "google-cloud-compute": ">=1.36.0",
            "google-cloud-container": ">=2.44.0",
            "google-cloud-storage": ">=2.18.0",
            "google-auth": ">=2.29.0",
        },
        "azure": {
            "azure-identity": ">=1.15.0",
            "azure-mgmt-compute": ">=29.1.0",
            "azure-mgmt-network": ">=24.0.0",
        },
        "ssh": {
            "netifaces": ">=0.11.0",
        },
        "config": {
            "jsonschema": ">=4.23.0",
            "watchdog": ">=3.0.0",
            "cerberus": ">=1.3.4",
            "pydantic": ">=2.0.0",
        }
    }
    
    # Python version compatibility
    MIN_PYTHON_VERSION = (3, 9)
    MAX_PYTHON_VERSION = (3, 12)
    RECOMMENDED_PYTHON_VERSION = (3, 11, 13)
    
    def __init__(self):
        self.validation_results: Dict[str, DependencyInfo] = {}
        self.python_version_compatible = False
        self.missing_dependencies: List[str] = []
        self.incompatible_dependencies: List[str] = []
        
    def validate_python_version(self) -> bool:
        """
        Validate Python version compatibility.
        
        Returns:
            bool: True if Python version is compatible
        """
        current_version = sys.version_info[:2]
        
        if current_version < self.MIN_PYTHON_VERSION:
            logger.error(
                f"Python {current_version[0]}.{current_version[1]} is not supported. "
                f"Minimum required version is {self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]}"
            )
            return False
            
        if current_version > self.MAX_PYTHON_VERSION:
            logger.warning(
                f"Python {current_version[0]}.{current_version[1]} is newer than tested versions. "
                f"Maximum tested version is {self.MAX_PYTHON_VERSION[0]}.{self.MAX_PYTHON_VERSION[1]}"
            )
            
        self.python_version_compatible = True
        return True
        
    def check_package_availability(self, package_name: str, required_version: str) -> DependencyInfo:
        """
        Check if a package is available and compatible.
        
        Args:
            package_name: Name of the package to check
            required_version: Required version specification (e.g., ">=1.0.0")
            
        Returns:
            DependencyInfo: Information about the dependency
        """
        dep_info = DependencyInfo(
            name=package_name,
            required_version=required_version
        )
        
        # Package name to import name mapping
        import_name_mapping = {
            "PyYAML": "yaml",
            "python-dotenv": "dotenv",
            "google-cloud-compute": "google.cloud.compute",
            "google-cloud-container": "google.cloud.container",
            "google-cloud-storage": "google.cloud.storage",
            "google-cloud-functions": "google.cloud.functions",
            "google-cloud-run": "google.cloud.run",
            "google-cloud-billing": "google.cloud.billing",
            "google-cloud-resource-manager": "google.cloud.resourcemanager",
            "google-auth": "google.auth",
            "google-auth-oauthlib": "google_auth_oauthlib",
            "google-auth-httplib2": "google_auth_httplib2",
            "azure-identity": "azure.identity",
            "azure-mgmt-compute": "azure.mgmt.compute",
            "azure-mgmt-network": "azure.mgmt.network",
            "azure-mgmt-containerinstance": "azure.mgmt.containerinstance",
            "azure-mgmt-containerservice": "azure.mgmt.containerservice",
            "azure-mgmt-storage": "azure.mgmt.storage",
            "azure-mgmt-sql": "azure.mgmt.sql",
            "azure-mgmt-rdbms": "azure.mgmt.rdbms",
            "azure-mgmt-eventhub": "azure.mgmt.eventhub",
            "azure-mgmt-resource": "azure.mgmt.resource",
            "azure-mgmt-subscription": "azure.mgmt.subscription",
        }
        
        # Determine import name
        import_name = import_name_mapping.get(package_name, package_name.replace("-", "_"))
        
        try:
            # Try to import the package
            importlib.import_module(import_name)
            dep_info.is_available = True
            
            # Check version if available
            try:
                installed_version = pkg_resources.get_distribution(package_name).version
                dep_info.installed_version = installed_version
                
                # Parse version requirement
                req = pkg_resources.Requirement.parse(f"{package_name}{required_version}")
                if installed_version in req:
                    dep_info.is_compatible = True
                else:
                    dep_info.is_compatible = False
                    dep_info.error_message = (
                        f"Version {installed_version} does not meet requirement {required_version}"
                    )
                    
            except Exception as e:
                dep_info.error_message = f"Could not determine version: {e}"
                
        except ImportError as e:
            dep_info.is_available = False
            dep_info.error_message = f"Package not found: {e}"
            
        except Exception as e:
            dep_info.is_available = False
            dep_info.error_message = f"Unexpected error: {e}"
            
        return dep_info
        
    def validate_core_dependencies(self) -> bool:
        """
        Validate all core dependencies.
        
        Returns:
            bool: True if all core dependencies are satisfied
        """
        all_satisfied = True
        
        for package_name, required_version in self.CORE_DEPENDENCIES.items():
            dep_info = self.check_package_availability(package_name, required_version)
            self.validation_results[package_name] = dep_info
            
            if not dep_info.is_available:
                self.missing_dependencies.append(package_name)
                all_satisfied = False
            elif not dep_info.is_compatible:
                self.incompatible_dependencies.append(package_name)
                all_satisfied = False
                
        return all_satisfied
        
    def validate_optional_dependencies(self, platforms: List[str] = None) -> Dict[str, bool]:
        """
        Validate optional dependencies for specific platforms.
        
        Args:
            platforms: List of platforms to validate (e.g., ['aws', 'oci'])
            
        Returns:
            Dict[str, bool]: Platform validation results
        """
        if platforms is None:
            platforms = list(self.OPTIONAL_DEPENDENCIES.keys())
            
        results = {}
        
        for platform in platforms:
            if platform not in self.OPTIONAL_DEPENDENCIES:
                results[platform] = False
                continue
                
            platform_satisfied = True
            dependencies = self.OPTIONAL_DEPENDENCIES[platform]
            
            for package_name, required_version in dependencies.items():
                dep_info = self.check_package_availability(package_name, required_version)
                self.validation_results[f"{platform}:{package_name}"] = dep_info
                
                if not dep_info.is_available or not dep_info.is_compatible:
                    platform_satisfied = False
                    
            results[platform] = platform_satisfied
            
        return results
        
    def generate_installation_command(self) -> str:
        """
        Generate pip install command for missing dependencies.
        
        Returns:
            str: Pip install command
        """
        if not self.missing_dependencies and not self.incompatible_dependencies:
            return ""
            
        packages = []
        
        # Add missing core dependencies
        for package in self.missing_dependencies:
            if package in self.CORE_DEPENDENCIES:
                packages.append(f"{package}{self.CORE_DEPENDENCIES[package]}")
                
        # Add incompatible core dependencies
        for package in self.incompatible_dependencies:
            if package in self.CORE_DEPENDENCIES:
                packages.append(f"{package}{self.CORE_DEPENDENCIES[package]}")
                
        if packages:
            return f"pip install {' '.join(packages)}"
        else:
            return "pip install -r requirements.txt"
            
    def print_validation_report(self) -> None:
        """Print a comprehensive validation report."""
        print("\n" + "="*60)
        print("IC CLI Dependency Validation Report")
        print("="*60)
        
        # Python version
        current_version = sys.version_info
        print(f"\nPython Version: {current_version.major}.{current_version.minor}.{current_version.micro}")
        
        if self.python_version_compatible:
            print("✅ Python version is compatible")
        else:
            print("❌ Python version is not compatible")
            print(f"   Required: {self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]}+")
            
        # Core dependencies
        print(f"\nCore Dependencies ({len(self.CORE_DEPENDENCIES)}):")
        for package_name in self.CORE_DEPENDENCIES:
            if package_name in self.validation_results:
                dep_info = self.validation_results[package_name]
                status = "✅" if dep_info.is_available and dep_info.is_compatible else "❌"
                version_info = f" (v{dep_info.installed_version})" if dep_info.installed_version else ""
                print(f"  {status} {package_name}{version_info}")
                if dep_info.error_message:
                    print(f"     Error: {dep_info.error_message}")
                    
        # Optional dependencies
        print(f"\nOptional Dependencies:")
        for platform, dependencies in self.OPTIONAL_DEPENDENCIES.items():
            print(f"\n  {platform.upper()}:")
            for package_name in dependencies:
                key = f"{platform}:{package_name}"
                if key in self.validation_results:
                    dep_info = self.validation_results[key]
                    status = "✅" if dep_info.is_available and dep_info.is_compatible else "❌"
                    version_info = f" (v{dep_info.installed_version})" if dep_info.installed_version else ""
                    print(f"    {status} {package_name}{version_info}")
                    if dep_info.error_message:
                        print(f"       Error: {dep_info.error_message}")
                        
        # Installation guidance
        if self.missing_dependencies or self.incompatible_dependencies:
            print(f"\n" + "="*60)
            print("Installation Guidance")
            print("="*60)
            
            if self.missing_dependencies:
                print(f"\nMissing packages ({len(self.missing_dependencies)}):")
                for package in self.missing_dependencies:
                    print(f"  - {package}")
                    
            if self.incompatible_dependencies:
                print(f"\nIncompatible packages ({len(self.incompatible_dependencies)}):")
                for package in self.incompatible_dependencies:
                    print(f"  - {package}")
                    
            install_cmd = self.generate_installation_command()
            if install_cmd:
                print(f"\nRecommended installation command:")
                print(f"  {install_cmd}")
                
        print("\n" + "="*60)
        
    def validate_all(self, platforms: List[str] = None) -> bool:
        """
        Run complete dependency validation.
        
        Args:
            platforms: Optional list of platforms to validate
            
        Returns:
            bool: True if all validations pass
        """
        # Validate Python version
        python_ok = self.validate_python_version()
        
        # Validate core dependencies
        core_ok = self.validate_core_dependencies()
        
        # Validate optional dependencies
        optional_results = self.validate_optional_dependencies(platforms)
        
        return python_ok and core_ok


def validate_dependencies(platforms: List[str] = None, verbose: bool = True) -> bool:
    """
    Convenience function to validate dependencies.
    
    Args:
        platforms: Optional list of platforms to validate
        verbose: Whether to print detailed report
        
    Returns:
        bool: True if validation passes
    """
    validator = DependencyValidator()
    result = validator.validate_all(platforms)
    
    if verbose:
        validator.print_validation_report()
        
    return result


if __name__ == "__main__":
    # CLI usage for dependency validation
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate IC CLI dependencies")
    parser.add_argument(
        "--platforms", 
        nargs="*", 
        choices=list(DependencyValidator.OPTIONAL_DEPENDENCIES.keys()),
        help="Specific platforms to validate"
    )
    parser.add_argument(
        "--quiet", 
        action="store_true", 
        help="Suppress detailed output"
    )
    
    args = parser.parse_args()
    
    success = validate_dependencies(
        platforms=args.platforms,
        verbose=not args.quiet
    )
    
    sys.exit(0 if success else 1)