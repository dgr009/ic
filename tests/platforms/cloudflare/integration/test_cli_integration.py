#!/usr/bin/env python3
"""
Integration tests for CloudFlare CLI integration.

Tests:
- Platform discovery automatically detects CloudFlare services
- Command routing works correctly
- Help text displays all CloudFlare commands
- Backward compatibility with deprecated commands
"""

import sys
import subprocess
import pytest
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr


class TestCLIIntegration:
    """Test CLI integration for CloudFlare platform."""
    
    def test_platform_discovery_detects_cloudflare(self):
        """Test that platform discovery automatically detects CloudFlare platform."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        platforms = discovery.discover_platforms()
        
        # Verify CloudFlare platform is discovered
        assert 'cloudflare' in platforms, "CloudFlare platform not discovered"
        
        cf_platform = platforms['cloudflare']
        assert cf_platform.available, f"CloudFlare platform not available: {cf_platform.error}"
        
        # Verify all expected services are discovered
        expected_services = ['account', 'zone', 'dns', 'traffic', 'waf', 'rules']
        discovered_services = list(cf_platform.services.keys())
        
        for service in expected_services:
            assert service in discovered_services, f"Service '{service}' not discovered"
    
    def test_service_commands_discovered(self):
        """Test that all service commands are properly discovered."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        
        # Test each service has 'info' command
        services = ['account', 'zone', 'dns', 'traffic', 'waf', 'rules']
        
        for service in services:
            commands = discovery.get_service_commands('cloudflare', service)
            assert 'info' in commands, f"Service '{service}' missing 'info' command"
            
            # Verify command module has required functions
            info_module = commands['info']
            assert hasattr(info_module, 'add_arguments'), f"{service}.info missing add_arguments"
            assert hasattr(info_module, 'main'), f"{service}.info missing main function"
    
    def test_dns_backward_compatibility_command_exists(self):
        """Test that deprecated list_info command still exists for backward compatibility."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        commands = discovery.get_service_commands('cloudflare', 'dns')
        
        # Both info and list_info should exist
        assert 'info' in commands, "DNS info command not found"
        assert 'list_info' in commands, "DNS list_info command not found (backward compatibility broken)"
    
    def test_command_routing_account_info(self):
        """Test command routing for 'ic cloudflare account info'."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'account', 'info', '--help'],
            capture_output=True,
            text=True
        )
        
        # Should not error (exit code 0)
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Help text should be displayed
        assert 'account' in result.stdout.lower() or 'usage' in result.stdout.lower()
    
    def test_command_routing_zone_info(self):
        """Test command routing for 'ic cloudflare zone info'."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'zone', 'info', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert 'zone' in result.stdout.lower() or 'usage' in result.stdout.lower()
    
    def test_command_routing_dns_info(self):
        """Test command routing for 'ic cloudflare dns info'."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'dns', 'info', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert 'dns' in result.stdout.lower() or 'usage' in result.stdout.lower()
    
    def test_command_routing_traffic_info(self):
        """Test command routing for 'ic cloudflare traffic info'."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'traffic', 'info', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert 'traffic' in result.stdout.lower() or 'usage' in result.stdout.lower()
    
    def test_command_routing_waf_info(self):
        """Test command routing for 'ic cloudflare waf info'."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'waf', 'info', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert 'waf' in result.stdout.lower() or 'usage' in result.stdout.lower()
    
    def test_command_routing_rules_info(self):
        """Test command routing for 'ic cloudflare rules info'."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'rules', 'info', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert 'rules' in result.stdout.lower() or 'usage' in result.stdout.lower()
    
    def test_cloudflare_platform_help(self):
        """Test that CloudFlare platform help displays all services."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # All services should be listed in help
        help_text = result.stdout.lower()
        assert 'account' in help_text, "account service not in help"
        assert 'zone' in help_text, "zone service not in help"
        assert 'dns' in help_text, "dns service not in help"
        assert 'traffic' in help_text, "traffic service not in help"
        assert 'waf' in help_text, "waf service not in help"
        assert 'rules' in help_text, "rules service not in help"
    
    def test_dns_service_help_shows_both_commands(self):
        """Test that DNS service help shows both info and list_info commands."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'dns', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        help_text = result.stdout.lower()
        assert 'info' in help_text, "info command not in DNS help"
        assert 'list_info' in help_text, "list_info command not in DNS help (backward compatibility)"
    
    def test_dns_list_info_shows_deprecation_warning(self):
        """Test that 'ic cloudflare dns list_info' shows deprecation warning."""
        # The deprecation warning is shown when the module is imported
        # Since the module may already be imported, we check if the warning
        # was issued during test discovery or we force a reimport
        import warnings
        import sys
        
        # Clear the module from cache to force reimport
        modules_to_clear = [
            'src.ic.platforms.cloudflare.dns.list_info',
            'ic.platforms.cloudflare.dns.list_info'
        ]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]
        
        # Also clear the parent module to ensure clean import
        parent_modules = [
            'src.ic.platforms.cloudflare.dns',
            'ic.platforms.cloudflare.dns'
        ]
        for mod in parent_modules:
            if mod in sys.modules:
                # Don't delete, just clear the list_info attribute
                parent = sys.modules[mod]
                if hasattr(parent, 'list_info'):
                    delattr(parent, 'list_info')
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.filterwarnings("always", category=DeprecationWarning)
            
            # Force reimport
            import importlib
            import src.ic.platforms.cloudflare.dns.list_info as list_info_module
            
            # Check that a deprecation warning was issued
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            assert len(deprecation_warnings) > 0, f"No deprecation warning issued. Warnings: {[str(x.message) for x in w]}"
            
            # Check the warning content
            warning_message = str(deprecation_warnings[0].message).lower()
            assert "deprecated" in warning_message, "Warning message doesn't mention deprecation"
            assert "info" in warning_message, "Warning doesn't suggest 'info' command"
    
    def test_all_services_have_consistent_interface(self):
        """Test that all CloudFlare services follow consistent interface pattern."""
        from src.ic.core.platform_discovery import get_platform_discovery
        
        discovery = get_platform_discovery()
        services = ['account', 'zone', 'dns', 'traffic', 'waf', 'rules']
        
        for service in services:
            commands = discovery.get_service_commands('cloudflare', service)
            info_module = commands.get('info')
            
            assert info_module is not None, f"Service '{service}' missing info command"
            
            # Check for required functions
            assert hasattr(info_module, 'add_arguments'), \
                f"Service '{service}' info module missing add_arguments function"
            assert callable(info_module.add_arguments), \
                f"Service '{service}' add_arguments is not callable"
            
            assert hasattr(info_module, 'main'), \
                f"Service '{service}' info module missing main function"
            assert callable(info_module.main), \
                f"Service '{service}' main is not callable"
    
    def test_cloudflare_full_name_works(self):
        """Test that 'cloudflare' full platform name works."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"'cloudflare' platform failed: {result.stderr}"
        assert 'cloudflare' in result.stdout.lower() or 'usage' in result.stdout.lower()
    
    def test_invalid_service_shows_available_services(self):
        """Test that invalid service shows list of available services."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'invalid_service', 'info'],
            capture_output=True,
            text=True
        )
        
        # Should fail with non-zero exit code
        assert result.returncode != 0, "Invalid service should fail"
        
        # Error message should show available services (argparse shows "choose from")
        error_output = result.stderr.lower()
        assert 'invalid choice' in error_output or 'not found' in error_output
        assert 'choose from' in error_output or 'available' in error_output
    
    def test_invalid_command_shows_available_commands(self):
        """Test that invalid command shows list of available commands."""
        result = subprocess.run(
            ['python', '-m', 'src.ic.cli', 'cloudflare', 'dns', 'invalid_command'],
            capture_output=True,
            text=True
        )
        
        # Should fail with non-zero exit code
        assert result.returncode != 0, "Invalid command should fail"
        
        # Error message should show available commands (argparse shows "choose from")
        error_output = result.stderr.lower()
        assert 'invalid choice' in error_output or 'not found' in error_output
        assert 'choose from' in error_output or 'available' in error_output


class TestBackwardCompatibility:
    """Test backward compatibility features."""
    
    def test_list_info_module_imports_from_info(self):
        """Test that list_info module properly imports from info module."""
        from src.ic.platforms.cloudflare.dns import list_info
        from src.ic.platforms.cloudflare.dns import info
        
        # list_info should have main and add_arguments functions
        assert hasattr(list_info, 'main'), "list_info missing main function"
        assert hasattr(list_info, 'add_arguments'), "list_info missing add_arguments function"
        
        # add_arguments should be the same (imported directly)
        assert list_info.add_arguments is info.add_arguments, \
            "list_info.add_arguments is not the same as info.add_arguments"
        
        # main is wrapped to show deprecation message, so it won't be the same object
        # but it should be callable
        assert callable(list_info.main), "list_info.main is not callable"
    
    def test_deprecation_warning_content(self):
        """Test that deprecation warning has correct content."""
        import warnings
        import sys
        import importlib
        
        # Clear module from cache
        modules_to_clear = [
            'src.ic.platforms.cloudflare.dns.list_info',
            'ic.platforms.cloudflare.dns.list_info'
        ]
        for mod in modules_to_clear:
            if mod in sys.modules:
                del sys.modules[mod]
        
        # Clear parent module attribute
        parent_modules = [
            'src.ic.platforms.cloudflare.dns',
            'ic.platforms.cloudflare.dns'
        ]
        for mod in parent_modules:
            if mod in sys.modules:
                parent = sys.modules[mod]
                if hasattr(parent, 'list_info'):
                    delattr(parent, 'list_info')
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.filterwarnings("always", category=DeprecationWarning)
            
            # Force reimport
            import src.ic.platforms.cloudflare.dns.list_info as list_info_module
            
            # Get deprecation warnings
            deprecation_warnings = [warning for warning in w if issubclass(warning.category, DeprecationWarning)]
            assert len(deprecation_warnings) > 0, f"No warning issued. All warnings: {[str(x.message) for x in w]}"
            
            warning_message = str(deprecation_warnings[0].message).lower()
            
            # Check warning mentions key information
            assert 'list_info' in warning_message, "Warning doesn't mention list_info"
            assert 'deprecated' in warning_message, "Warning doesn't say deprecated"
            assert 'info' in warning_message, "Warning doesn't suggest info command"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
