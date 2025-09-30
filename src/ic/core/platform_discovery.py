#!/usr/bin/env python3
"""
Platform Discovery System for IC CLI

This module provides dynamic discovery of platforms and services,
replacing hardcoded imports with a flexible discovery mechanism.
"""

import os
import sys
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class ServiceInfo:
    """Information about a discovered service."""
    name: str
    module: Any
    add_arguments: Optional[callable] = None
    main: Optional[callable] = None
    available: bool = True
    error: Optional[str] = None


@dataclass
class PlatformInfo:
    """Information about a discovered platform."""
    name: str
    services: Dict[str, ServiceInfo]
    available: bool = True
    error: Optional[str] = None


class PlatformDiscovery:
    """Dynamic platform and service discovery system."""
    
    def __init__(self):
        self.platforms: Dict[str, PlatformInfo] = {}
        self._discovery_cache: Dict[str, Any] = {}
        
    def discover_platforms(self) -> Dict[str, PlatformInfo]:
        """
        Discover all available platforms and their services.
        
        Returns:
            Dict mapping platform names to PlatformInfo objects
        """
        if self.platforms:
            return self.platforms
            
        platforms_dir = self._get_platforms_directory()
        if not platforms_dir or not platforms_dir.exists():
            return {}
            
        for platform_path in platforms_dir.iterdir():
            if platform_path.is_dir() and not platform_path.name.startswith('_'):
                platform_name = platform_path.name
                platform_info = self._discover_platform(platform_name, platform_path)
                self.platforms[platform_name] = platform_info
                
        return self.platforms
    
    def _get_platforms_directory(self) -> Optional[Path]:
        """Get the platforms directory path."""
        try:
            # Try to find platforms directory relative to this file
            current_file = Path(__file__)
            platforms_dir = current_file.parent.parent / "platforms"
            
            if platforms_dir.exists():
                return platforms_dir
                
            # Fallback: try to find it in the package
            try:
                import src.ic as ic
                ic_path = Path(ic.__file__).parent
            except ImportError:
                try:
                    import ic
                    ic_path = Path(ic.__file__).parent
                except ImportError:
                    # Last resort: use relative path
                    ic_path = Path(__file__).parent.parent
            platforms_dir = ic_path / "platforms"
            
            if platforms_dir.exists():
                return platforms_dir
                
        except Exception:
            pass
            
        return None
    
    def _discover_platform(self, platform_name: str, platform_path: Path) -> PlatformInfo:
        """
        Discover services within a platform.
        
        Args:
            platform_name: Name of the platform
            platform_path: Path to the platform directory
            
        Returns:
            PlatformInfo object with discovered services
        """
        services = {}
        platform_available = True
        platform_error = None
        
        try:
            # Discover services in the platform directory
            for service_path in platform_path.iterdir():
                if service_path.is_dir() and not service_path.name.startswith('_'):
                    service_name = service_path.name
                    service_info = self._discover_service(platform_name, service_name, service_path)
                    services[service_name] = service_info
                elif service_path.is_file() and service_path.suffix == '.py':
                    # Handle single-file services (like client.py)
                    service_name = service_path.stem
                    if service_name not in ['__init__', 'client']:
                        service_info = self._discover_file_service(platform_name, service_name, service_path)
                        services[service_name] = service_info
                        
        except Exception as e:
            platform_available = False
            platform_error = f"Failed to discover platform {platform_name}: {str(e)}"
            
        return PlatformInfo(
            name=platform_name,
            services=services,
            available=platform_available,
            error=platform_error
        )
    
    def _discover_service(self, platform_name: str, service_name: str, service_path: Path) -> ServiceInfo:
        """
        Discover a service within a platform directory.
        
        Args:
            platform_name: Name of the platform
            service_name: Name of the service
            service_path: Path to the service directory
            
        Returns:
            ServiceInfo object
        """
        try:
            # Discover all command modules in the service directory
            command_modules = {}
            
            for file_path in service_path.iterdir():
                if file_path.is_file() and file_path.suffix == '.py' and not file_path.name.startswith('_'):
                    command_name = file_path.stem
                    module_path = f"src.ic.platforms.{platform_name}.{service_name}.{command_name}"
                    command_module = self._import_module(module_path)
                    
                    if command_module:
                        command_modules[command_name] = command_module
            
            # Create a composite service info that can handle multiple commands
            if command_modules:
                return ServiceInfo(
                    name=service_name,
                    module=command_modules,  # Store all command modules
                    add_arguments=None,  # Will be handled per command
                    main=None,  # Will be handled per command
                    available=True
                )
            else:
                return ServiceInfo(
                    name=service_name,
                    module=None,
                    available=False,
                    error=f"No command modules found in service directory"
                )
                
        except Exception as e:
            return ServiceInfo(
                name=service_name,
                module=None,
                available=False,
                error=f"Failed to discover service {service_name}: {str(e)}"
            )
    
    def _discover_file_service(self, platform_name: str, service_name: str, service_path: Path) -> ServiceInfo:
        """
        Discover a single-file service.
        
        Args:
            platform_name: Name of the platform
            service_name: Name of the service
            service_path: Path to the service file
            
        Returns:
            ServiceInfo object
        """
        try:
            module_path = f"src.ic.platforms.{platform_name}.{service_name}"
            service_module = self._import_module(module_path)
            
            if service_module:
                add_arguments = getattr(service_module, 'add_arguments', None)
                main_func = getattr(service_module, 'main', None)
                
                return ServiceInfo(
                    name=service_name,
                    module=service_module,
                    add_arguments=add_arguments,
                    main=main_func,
                    available=True
                )
            else:
                return ServiceInfo(
                    name=service_name,
                    module=None,
                    available=False,
                    error=f"Could not import service file"
                )
                
        except Exception as e:
            return ServiceInfo(
                name=service_name,
                module=None,
                available=False,
                error=f"Failed to discover file service {service_name}: {str(e)}"
            )
    
    def _import_module(self, module_path: str) -> Optional[Any]:
        """
        Import a module with fallback mechanisms.
        
        Args:
            module_path: Module path to import
            
        Returns:
            Imported module or None if failed
        """
        if module_path in self._discovery_cache:
            return self._discovery_cache[module_path]
        
        try:
            # Try primary import path
            module = importlib.import_module(module_path)
            self._discovery_cache[module_path] = module
            return module
        except ImportError:
            try:
                # Try fallback path (for installed package)
                fallback_path = module_path.replace('src.ic.', 'ic.')
                module = importlib.import_module(fallback_path)
                self._discovery_cache[module_path] = module
                return module
            except ImportError:
                # Try legacy import paths for backward compatibility
                try:
                    # Handle legacy module names like oci_module -> oci
                    if 'oci_module' in module_path:
                        legacy_path = module_path.replace('oci_module', 'oci')
                        module = importlib.import_module(legacy_path)
                        self._discovery_cache[module_path] = module
                        return module
                    elif 'azure_module' in module_path:
                        legacy_path = module_path.replace('azure_module', 'azure')
                        module = importlib.import_module(legacy_path)
                        self._discovery_cache[module_path] = module
                        return module
                except ImportError:
                    pass
                
                self._discovery_cache[module_path] = None
                return None
    
    def get_platform(self, platform_name: str) -> Optional[PlatformInfo]:
        """
        Get information about a specific platform.
        
        Args:
            platform_name: Name of the platform
            
        Returns:
            PlatformInfo object or None if not found
        """
        if not self.platforms:
            self.discover_platforms()
        return self.platforms.get(platform_name)
    
    def get_service(self, platform_name: str, service_name: str) -> Optional[ServiceInfo]:
        """
        Get information about a specific service.
        
        Args:
            platform_name: Name of the platform
            service_name: Name of the service
            
        Returns:
            ServiceInfo object or None if not found
        """
        platform = self.get_platform(platform_name)
        if platform:
            return platform.services.get(service_name)
        return None
    
    def list_platforms(self) -> List[str]:
        """
        List all available platform names.
        
        Returns:
            List of platform names
        """
        if not self.platforms:
            self.discover_platforms()
        return list(self.platforms.keys())
    
    def list_services(self, platform_name: str) -> List[str]:
        """
        List all services for a platform.
        
        Args:
            platform_name: Name of the platform
            
        Returns:
            List of service names
        """
        platform = self.get_platform(platform_name)
        if platform:
            return list(platform.services.keys())
        return []
    
    def get_service_commands(self, platform_name: str, service_name: str) -> Dict[str, Any]:
        """
        Get all command modules for a service.
        
        Args:
            platform_name: Name of the platform
            service_name: Name of the service
            
        Returns:
            Dictionary mapping command names to modules
        """
        service_info = self.get_service(platform_name, service_name)
        if service_info and service_info.available and isinstance(service_info.module, dict):
            return service_info.module
        return {}
    
    def get_command_module(self, platform_name: str, service_name: str, command_name: str) -> Optional[Any]:
        """
        Get a specific command module.
        
        Args:
            platform_name: Name of the platform
            service_name: Name of the service
            command_name: Name of the command
            
        Returns:
            Command module or None if not found
        """
        commands = self.get_service_commands(platform_name, service_name)
        return commands.get(command_name)
    
    def validate_platform_availability(self, platform_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if a platform is available and provide error message if not.
        
        Args:
            platform_name: Name of the platform to validate
            
        Returns:
            Tuple of (is_available, error_message)
        """
        platform = self.get_platform(platform_name)
        
        if not platform:
            return False, f"Platform '{platform_name}' not found"
        
        if not platform.available:
            return False, platform.error or f"Platform '{platform_name}' is not available"
        
        return True, None
    
    def get_platform_help(self, platform_name: str) -> str:
        """
        Get help information for a platform.
        
        Args:
            platform_name: Name of the platform
            
        Returns:
            Help text for the platform
        """
        platform = self.get_platform(platform_name)
        
        if not platform:
            return f"Platform '{platform_name}' not found"
        
        if not platform.available:
            return f"Platform '{platform_name}' is not available: {platform.error}"
        
        help_text = f"Platform '{platform_name}' services:\n"
        for service_name, service_info in platform.services.items():
            if service_info.available:
                commands = list(service_info.module.keys()) if isinstance(service_info.module, dict) else []
                help_text += f"  {service_name}: {', '.join(commands) if commands else 'available'}\n"
            else:
                help_text += f"  {service_name}: unavailable ({service_info.error})\n"
        
        return help_text


# Global discovery instance
_discovery_instance = None


def get_platform_discovery() -> PlatformDiscovery:
    """Get the global platform discovery instance."""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = PlatformDiscovery()
    return _discovery_instance