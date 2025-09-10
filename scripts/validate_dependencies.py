#!/usr/bin/env python3
"""
Dependency validation script for IC CLI.

This script validates that all dependencies are properly installed
and compatible with the current Python version (3.9-3.12).

Usage:
    python scripts/validate_dependencies.py
    python scripts/validate_dependencies.py --platforms aws oci
    python scripts/validate_dependencies.py --install-missing
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from ic.core.dependency_validator import DependencyValidator, validate_dependencies
except ImportError:
    print("❌ Could not import dependency validator. Installing core dependencies...")
    
    # Try to install core dependencies first
    core_deps = [
        "packaging>=21.0,<25.0",
        "setuptools>=61.0,<71.0",
    ]
    
    for dep in core_deps:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {dep}: {e}")
            sys.exit(1)
    
    # Try import again
    try:
        from ic.core.dependency_validator import DependencyValidator, validate_dependencies
    except ImportError as e:
        print(f"❌ Still cannot import dependency validator: {e}")
        sys.exit(1)


def install_missing_dependencies(validator: DependencyValidator) -> bool:
    """
    Install missing dependencies using pip.
    
    Args:
        validator: DependencyValidator instance with validation results
        
    Returns:
        bool: True if installation succeeded
    """
    if not validator.missing_dependencies and not validator.incompatible_dependencies:
        print("✅ No missing or incompatible dependencies found.")
        return True
        
    install_cmd = validator.generate_installation_command()
    if not install_cmd:
        print("❌ Could not generate installation command.")
        return False
        
    print(f"\n🔧 Installing dependencies with: {install_cmd}")
    
    try:
        # Split the command and run it
        cmd_parts = install_cmd.split()
        subprocess.check_call(cmd_parts)
        print("✅ Dependencies installed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during installation: {e}")
        return False


def test_requirements_txt_installation() -> bool:
    """
    Test that pip install -r requirements.txt works.
    
    Returns:
        bool: True if installation test passes
    """
    requirements_file = Path(__file__).parent.parent / "requirements.txt"
    
    if not requirements_file.exists():
        print(f"❌ Requirements file not found: {requirements_file}")
        return False
        
    print(f"\n🧪 Testing pip install -r requirements.txt...")
    
    try:
        # Use --dry-run to test without actually installing
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "--dry-run", "-r", str(requirements_file)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Requirements.txt installation test passed.")
            return True
        else:
            print(f"❌ Requirements.txt installation test failed:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing requirements.txt installation: {e}")
        return False


def check_python_version_compatibility() -> bool:
    """
    Check if current Python version is compatible.
    
    Returns:
        bool: True if Python version is compatible
    """
    version = sys.version_info
    min_version = (3, 9)
    max_version = (3, 12)
    
    print(f"\n🐍 Python Version Check:")
    print(f"   Current: {version.major}.{version.minor}.{version.micro}")
    print(f"   Required: {min_version[0]}.{min_version[1]}+ to {max_version[0]}.{max_version[1]}")
    
    if version[:2] < min_version:
        print(f"❌ Python version too old. Minimum required: {min_version[0]}.{min_version[1]}")
        return False
    elif version[:2] > max_version:
        print(f"⚠️  Python version newer than tested. Maximum tested: {max_version[0]}.{max_version[1]}")
        print("   The tool may still work, but compatibility is not guaranteed.")
        return True
    else:
        print("✅ Python version is compatible.")
        return True


def main():
    """Main function for dependency validation script."""
    parser = argparse.ArgumentParser(
        description="Validate IC CLI dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_dependencies.py
  python scripts/validate_dependencies.py --platforms aws oci
  python scripts/validate_dependencies.py --install-missing
  python scripts/validate_dependencies.py --test-requirements
        """
    )
    
    parser.add_argument(
        "--platforms",
        nargs="*",
        choices=["aws", "oci", "gcp", "azure", "ssh", "config"],
        help="Specific platforms to validate (default: all)"
    )
    
    parser.add_argument(
        "--install-missing",
        action="store_true",
        help="Automatically install missing dependencies"
    )
    
    parser.add_argument(
        "--test-requirements",
        action="store_true", 
        help="Test pip install -r requirements.txt"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress detailed output"
    )
    
    args = parser.parse_args()
    
    print("IC CLI Dependency Validation")
    print("=" * 50)
    
    # Check Python version compatibility
    python_ok = check_python_version_compatibility()
    if not python_ok and not args.quiet:
        print("\n⚠️  Python version compatibility issues detected.")
        
    # Test requirements.txt if requested
    if args.test_requirements:
        requirements_ok = test_requirements_txt_installation()
        if not requirements_ok:
            print("\n❌ Requirements.txt installation test failed.")
            sys.exit(1)
    
    # Run dependency validation
    validator = DependencyValidator()
    success = validator.validate_all(platforms=args.platforms)
    
    if not args.quiet:
        validator.print_validation_report()
    
    # Install missing dependencies if requested
    if args.install_missing and (validator.missing_dependencies or validator.incompatible_dependencies):
        install_success = install_missing_dependencies(validator)
        if install_success:
            # Re-run validation after installation
            print("\n🔄 Re-validating after installation...")
            validator = DependencyValidator()
            success = validator.validate_all(platforms=args.platforms)
            if not args.quiet:
                validator.print_validation_report()
    
    # Final result
    if success and python_ok:
        print("\n✅ All dependency validations passed!")
        sys.exit(0)
    else:
        print("\n❌ Dependency validation failed!")
        if validator.missing_dependencies or validator.incompatible_dependencies:
            print("\n💡 Try running with --install-missing to automatically fix issues.")
        sys.exit(1)


if __name__ == "__main__":
    main()