#!/usr/bin/env python3
"""
CI Environment Setup Script

Main script for setting up CI test environments with mock configurations,
environment detection, and fallback mechanisms for GitHub Actions and other CI systems.

Requirements: 3.1, 3.2, 3.7 - CI environment setup and fallback mechanisms

Usage:
    python tests/ci/setup_ci_environment.py
    
Environment Variables:
    CI=true                    - Indicates CI environment
    GITHUB_ACTIONS=true        - Indicates GitHub Actions
    IC_CI_MODE=true           - Force CI mode for testing
    IC_MOCK_MODE=true         - Enable mock configurations
    IC_LOG_LEVEL=ERROR        - Set logging level for CI
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.ci.environment import CITestEnvironmentSetup, is_ci_environment, get_ci_info
from tests.ci.mock_configs import get_mock_config, get_mock_client
from tests.ci.fallback_configs import load_config_with_fallback, validate_config


class CIEnvironmentSetupManager:
    """Manages the complete CI environment setup process."""
    
    def __init__(self, force_ci_mode: bool = False, enable_mock_mode: bool = True):
        self.force_ci_mode = force_ci_mode
        self.enable_mock_mode = enable_mock_mode
        self.setup_info: Optional[Dict[str, Any]] = None
        
        # Configure logging
        log_level = os.getenv('IC_LOG_LEVEL', 'INFO').upper()
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/tmp/ci_setup.log', mode='w')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup(self) -> Dict[str, Any]:
        """Set up complete CI environment."""
        self.logger.info("Starting CI environment setup...")
        
        # Force CI mode if requested
        if self.force_ci_mode:
            os.environ['CI'] = 'true'
            os.environ['IC_CI_MODE'] = 'true'
            self.logger.info("Forced CI mode enabled")
        
        # Enable mock mode if requested
        if self.enable_mock_mode:
            os.environ['IC_MOCK_MODE'] = 'true'
            self.logger.info("Mock mode enabled")
        
        # Check CI environment
        ci_detected = is_ci_environment() or self.force_ci_mode
        ci_info = get_ci_info()
        
        self.logger.info(f"CI Environment Detected: {ci_detected}")
        self.logger.info(f"CI Provider: {ci_info.get('provider', 'Unknown')}")
        self.logger.info(f"Python Version: {ci_info.get('python_version', 'Unknown')}")
        self.logger.info(f"Platform: {ci_info.get('platform', 'Unknown')}")
        
        # Set up CI environment
        ci_setup = CITestEnvironmentSetup()
        self.setup_info = ci_setup.setup_ci_environment()
        
        # Validate configurations
        self._validate_configurations()
        
        # Set up mock clients if in mock mode
        if self.enable_mock_mode:
            self._setup_mock_clients()
        
        # Create test data directories
        self._create_test_directories()
        
        # Set additional CI-specific environment variables
        self._set_ci_environment_variables()
        
        self.logger.info("CI environment setup completed successfully")
        return self.setup_info
    
    def _validate_configurations(self):
        """Validate all loaded configurations."""
        self.logger.info("Validating configurations...")
        
        platforms = ['ic', 'ncp', 'ncpgov']
        validation_results = {}
        
        for platform in platforms:
            try:
                config = load_config_with_fallback(platform)
                issues = validate_config(platform, config)
                
                validation_results[platform] = {
                    'config_loaded': True,
                    'issues': issues,
                    'valid': len(issues) == 0
                }
                
                if issues:
                    self.logger.warning(f"{platform.upper()} config issues: {issues}")
                else:
                    self.logger.info(f"{platform.upper()} configuration is valid")
                    
            except Exception as e:
                validation_results[platform] = {
                    'config_loaded': False,
                    'error': str(e),
                    'valid': False
                }
                self.logger.error(f"Failed to load {platform.upper()} config: {e}")
        
        # Store validation results
        if self.setup_info:
            self.setup_info['validation_results'] = validation_results
    
    def _setup_mock_clients(self):
        """Set up mock clients for testing."""
        self.logger.info("Setting up mock clients...")
        
        mock_clients = {}
        platforms = ['aws', 'ncp', 'ncpgov', 'cloudflare']
        
        for platform in platforms:
            try:
                mock_client = get_mock_client(platform)
                mock_clients[platform] = mock_client
                self.logger.info(f"Created mock client for {platform.upper()}")
            except Exception as e:
                self.logger.warning(f"Failed to create mock client for {platform.upper()}: {e}")
        
        # Store mock clients in setup info
        if self.setup_info:
            self.setup_info['mock_clients'] = mock_clients
    
    def _create_test_directories(self):
        """Create necessary test directories."""
        self.logger.info("Creating test directories...")
        
        test_dirs = [
            Path('/tmp/ic_ci_logs'),
            Path('/tmp/ic_ci_configs'),
            Path('/tmp/ic_ci_data'),
            Path('/tmp/ic_ci_cache')
        ]
        
        created_dirs = []
        for test_dir in test_dirs:
            try:
                test_dir.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(test_dir))
                self.logger.info(f"Created test directory: {test_dir}")
            except Exception as e:
                self.logger.warning(f"Failed to create test directory {test_dir}: {e}")
        
        # Store created directories
        if self.setup_info:
            self.setup_info['test_directories'] = created_dirs
    
    def _set_ci_environment_variables(self):
        """Set additional CI-specific environment variables."""
        self.logger.info("Setting CI-specific environment variables...")
        
        ci_env_vars = {
            # Test configuration
            'IC_TEST_MODE': 'true',
            'IC_CI_ENVIRONMENT': 'true',
            'IC_DISABLE_INTERACTIVE': 'true',
            'IC_FORCE_COLOR': 'false',
            
            # Logging configuration
            'IC_LOG_TO_FILE': 'true',
            'IC_LOG_FILE_PATH': '/tmp/ic_ci_logs/ic.log',
            'IC_DISABLE_PROGRESS_BARS': 'true',
            
            # Performance configuration
            'IC_MAX_WORKERS': '5',
            'IC_TIMEOUT': '30',
            'IC_RETRY_ATTEMPTS': '2',
            
            # Security configuration
            'IC_MASK_SENSITIVE_DATA': 'true',
            'IC_DISABLE_TELEMETRY': 'true',
            
            # Platform-specific test settings
            'AWS_DEFAULT_OUTPUT': 'json',
            'AWS_PAGER': '',
            'AZURE_CORE_OUTPUT': 'json',
            'GOOGLE_CLOUD_PROJECT': 'mock-project',
            
            # Disable external network calls in tests
            'IC_OFFLINE_MODE': 'true',
            'IC_MOCK_EXTERNAL_CALLS': 'true'
        }
        
        set_vars = {}
        for key, value in ci_env_vars.items():
            os.environ[key] = value
            set_vars[key] = value
        
        self.logger.info(f"Set {len(set_vars)} CI environment variables")
        
        # Store set variables
        if self.setup_info:
            self.setup_info['ci_environment_variables'] = set_vars
    
    def cleanup(self):
        """Clean up CI environment."""
        self.logger.info("Cleaning up CI environment...")
        
        if self.setup_info:
            # Clean up temporary directories
            test_dirs = self.setup_info.get('test_directories', [])
            for test_dir in test_dirs:
                try:
                    import shutil
                    if Path(test_dir).exists():
                        shutil.rmtree(test_dir)
                        self.logger.info(f"Cleaned up test directory: {test_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up {test_dir}: {e}")
            
            # Remove CI environment variables
            ci_vars = self.setup_info.get('ci_environment_variables', {})
            for var in ci_vars.keys():
                if var in os.environ:
                    del os.environ[var]
        
        self.logger.info("CI environment cleanup completed")
    
    def get_setup_summary(self) -> Dict[str, Any]:
        """Get summary of CI setup."""
        if not self.setup_info:
            return {'status': 'not_setup'}
        
        summary = {
            'status': 'setup_complete',
            'ci_detected': self.setup_info['ci_info']['is_ci'],
            'ci_provider': self.setup_info['ci_info']['provider'],
            'python_version': self.setup_info['ci_info']['python_version'],
            'platform': self.setup_info['ci_info']['platform'],
            'mock_mode_enabled': self.enable_mock_mode,
            'configurations_loaded': {},
            'mock_clients_created': [],
            'test_directories_created': len(self.setup_info.get('test_directories', [])),
            'environment_variables_set': len(self.setup_info.get('ci_environment_variables', {}))
        }
        
        # Add configuration status
        validation_results = self.setup_info.get('validation_results', {})
        for platform, result in validation_results.items():
            summary['configurations_loaded'][platform] = result.get('valid', False)
        
        # Add mock client status
        mock_clients = self.setup_info.get('mock_clients', {})
        summary['mock_clients_created'] = list(mock_clients.keys())
        
        return summary


def main():
    """Main entry point for CI environment setup."""
    parser = argparse.ArgumentParser(description='Set up CI test environment')
    parser.add_argument('--force-ci', action='store_true',
                       help='Force CI mode even if not detected')
    parser.add_argument('--no-mock', action='store_true',
                       help='Disable mock mode')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Only perform cleanup')
    parser.add_argument('--summary', action='store_true',
                       help='Show setup summary and exit')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate configurations')
    
    args = parser.parse_args()
    
    # Create setup manager
    setup_manager = CIEnvironmentSetupManager(
        force_ci_mode=args.force_ci,
        enable_mock_mode=not args.no_mock
    )
    
    try:
        if args.cleanup_only:
            setup_manager.cleanup()
            print("✅ CI environment cleanup completed")
            return 0
        
        if args.validate_only:
            # Just validate configurations
            platforms = ['ic', 'ncp', 'ncpgov']
            all_valid = True
            
            for platform in platforms:
                try:
                    config = load_config_with_fallback(platform)
                    issues = validate_config(platform, config)
                    
                    if issues:
                        print(f"❌ {platform.upper()} configuration issues:")
                        for issue in issues:
                            print(f"   - {issue}")
                        all_valid = False
                    else:
                        print(f"✅ {platform.upper()} configuration is valid")
                        
                except Exception as e:
                    print(f"❌ Failed to validate {platform.upper()} config: {e}")
                    all_valid = False
            
            return 0 if all_valid else 1
        
        # Perform full setup
        setup_info = setup_manager.setup()
        
        if args.summary:
            summary = setup_manager.get_setup_summary()
            print("\n📋 CI Environment Setup Summary:")
            print(f"   Status: {summary['status']}")
            print(f"   CI Detected: {summary['ci_detected']}")
            print(f"   CI Provider: {summary['ci_provider']}")
            print(f"   Python Version: {summary['python_version']}")
            print(f"   Platform: {summary['platform']}")
            print(f"   Mock Mode: {summary['mock_mode_enabled']}")
            print(f"   Test Directories: {summary['test_directories_created']}")
            print(f"   Environment Variables: {summary['environment_variables_set']}")
            
            print("\n📝 Configuration Status:")
            for platform, valid in summary['configurations_loaded'].items():
                status = "✅" if valid else "❌"
                print(f"   {status} {platform.upper()}")
            
            print(f"\n🔧 Mock Clients: {', '.join(summary['mock_clients_created'])}")
        
        print("\n✅ CI environment setup completed successfully")
        print("   Use 'python tests/ci/setup_ci_environment.py --cleanup-only' to clean up")
        
        return 0
        
    except Exception as e:
        print(f"❌ CI environment setup failed: {e}")
        setup_manager.logger.exception("Setup failed with exception")
        return 1
    
    finally:
        # Always try to cleanup on exit if requested
        if not args.cleanup_only and os.getenv('IC_AUTO_CLEANUP', 'false').lower() == 'true':
            try:
                setup_manager.cleanup()
            except Exception as e:
                print(f"⚠️  Cleanup failed: {e}")


if __name__ == '__main__':
    sys.exit(main())