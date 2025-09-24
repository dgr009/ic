"""
Configuration Path Management System

This module provides hierarchical configuration path management for IC CLI,
implementing standardized configuration locations and migration utilities.
"""

import os
import shutil
import yaml
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConfigPathError(Exception):
    """Configuration path related errors"""
    pass


class ConfigPathManager:
    """
    Manages hierarchical configuration path lookup and migration.
    
    Implements the following hierarchy:
    1. Project-specific: ./.ic/config/
    2. User home: ~/.ic/config/
    3. Platform-specific: ~/.ncp/, ~/.ncpgov/
    4. System defaults: Built-in fallbacks
    """
    
    def __init__(self):
        self.home_dir = Path.home()
        self.project_dir = Path.cwd()
        self._backup_dir = self.home_dir / ".ic" / "backups"
        
    def get_config_hierarchy(self) -> List[Path]:
        """
        Get configuration file paths in order of precedence.
        
        Returns:
            List of configuration file paths to check
        """
        paths = []
        
        # 1. Project-specific configuration
        project_configs = [
            self.project_dir / ".ic" / "config" / "default.yaml",
            self.project_dir / ".ic" / "config.yaml",
            self.project_dir / "ic.yaml"
        ]
        paths.extend(project_configs)
        
        # 2. User home configuration
        user_configs = [
            self.home_dir / ".ic" / "config" / "default.yaml",
            self.home_dir / ".ic" / "config.yaml"
        ]
        paths.extend(user_configs)
        
        return paths
    
    def get_ncp_config_path(self) -> Optional[Path]:
        """
        Get NCP configuration path using hierarchical lookup.
        
        Returns:
            Path to NCP configuration file or None if not found
        """
        # Check hierarchy: project -> user home -> defaults
        paths = [
            self.project_dir / ".ic" / "config" / "ncp.yaml",
            self.home_dir / ".ncp" / "config.yaml",
            self.home_dir / ".ic" / "config" / "ncp.yaml"
        ]
        
        return self._find_first_existing(paths)
    
    def get_ncpgov_config_path(self) -> Optional[Path]:
        """
        Get NCPGOV configuration path using hierarchical lookup.
        
        Returns:
            Path to NCPGOV configuration file or None if not found
        """
        # Check hierarchy: project -> user home -> defaults
        paths = [
            self.project_dir / ".ic" / "config" / "ncpgov.yaml",
            self.home_dir / ".ncpgov" / "config.yaml",
            self.home_dir / ".ic" / "config" / "ncpgov.yaml"
        ]
        
        return self._find_first_existing(paths)
    
    def get_platform_config_path(self, platform: str) -> Optional[Path]:
        """
        Get platform-specific configuration path.
        
        Args:
            platform: Platform name (ncp, ncpgov, aws, gcp, etc.)
            
        Returns:
            Path to platform configuration file or None if not found
        """
        platform_lower = platform.lower()
        
        if platform_lower == "ncp":
            return self.get_ncp_config_path()
        elif platform_lower == "ncpgov":
            return self.get_ncpgov_config_path()
        else:
            # Generic platform config lookup
            paths = [
                self.project_dir / ".ic" / "config" / f"{platform_lower}.yaml",
                self.home_dir / f".{platform_lower}" / "config.yaml",
                self.home_dir / ".ic" / "config" / f"{platform_lower}.yaml"
            ]
            return self._find_first_existing(paths)
    
    def _find_first_existing(self, paths: List[Path]) -> Optional[Path]:
        """
        Find the first existing path from a list.
        
        Args:
            paths: List of paths to check
            
        Returns:
            First existing path or None
        """
        for path in paths:
            if path.exists() and path.is_file():
                logger.debug(f"Found config at: {path}")
                return path
        
        logger.debug(f"No config found in paths: {[str(p) for p in paths]}")
        return None
    
    def create_user_config_directories(self) -> Dict[str, Path]:
        """
        Create user configuration directories with proper permissions.
        
        Returns:
            Dictionary of created directory paths
        """
        directories = {
            "ic_config": self.home_dir / ".ic" / "config",
            "ncp_config": self.home_dir / ".ncp",
            "ncpgov_config": self.home_dir / ".ncpgov",
            "backup": self._backup_dir
        }
        
        created_dirs = {}
        
        for name, dir_path in directories.items():
            try:
                # Create directory with secure permissions (700)
                dir_path.mkdir(mode=0o700, parents=True, exist_ok=True)
                created_dirs[name] = dir_path
                logger.debug(f"Created config directory: {dir_path}")
            except Exception as e:
                logger.error(f"Failed to create directory {dir_path}: {e}")
                raise ConfigPathError(f"Failed to create config directory {dir_path}: {e}")
        
        return created_dirs
    
    def migrate_config_folders(self, confirm_callback=None) -> Dict[str, bool]:
        """
        Migrate configuration folders from project root to user home directory.
        
        Args:
            confirm_callback: Function to get user confirmation (returns bool)
            
        Returns:
            Dictionary of migration results
        """
        migration_results = {}
        
        # Define migration mappings
        migrations = [
            {
                "source": self.project_dir / ".ncp",
                "target": self.home_dir / ".ncp",
                "name": "NCP"
            },
            {
                "source": self.project_dir / ".ncpgov", 
                "target": self.home_dir / ".ncpgov",
                "name": "NCPGOV"
            }
        ]
        
        for migration in migrations:
            source = migration["source"]
            target = migration["target"]
            name = migration["name"]
            
            if not source.exists():
                migration_results[name] = True  # Nothing to migrate
                continue
            
            try:
                # Get user confirmation if callback provided
                if confirm_callback:
                    should_migrate = confirm_callback(
                        f"Migrate {name} configuration from {source} to {target}?"
                    )
                    if not should_migrate:
                        migration_results[name] = False
                        logger.info(f"User declined migration of {name} config")
                        continue
                
                # Create backup before migration
                backup_path = self._create_migration_backup(source, name)
                
                # Ensure target directory exists
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                
                # Perform migration
                if target.exists():
                    # Merge configurations if target exists
                    self._merge_config_directories(source, target)
                else:
                    # Move entire directory
                    shutil.move(str(source), str(target))
                
                # Set proper permissions
                self._set_secure_permissions(target)
                
                migration_results[name] = True
                logger.info(f"Successfully migrated {name} config from {source} to {target}")
                logger.info(f"Backup created at: {backup_path}")
                
            except Exception as e:
                migration_results[name] = False
                logger.error(f"Failed to migrate {name} config: {e}")
        
        return migration_results
    
    def _create_migration_backup(self, source_path: Path, config_name: str) -> Path:
        """
        Create backup of configuration before migration.
        
        Args:
            source_path: Source configuration path
            config_name: Configuration name for backup
            
        Returns:
            Path to backup directory
        """
        # Create backup directory
        self._backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        
        # Generate backup name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{config_name.lower()}_migration_{timestamp}"
        backup_path = self._backup_dir / backup_name
        
        # Copy configuration to backup
        shutil.copytree(source_path, backup_path)
        
        logger.info(f"Created migration backup: {backup_path}")
        return backup_path
    
    def _merge_config_directories(self, source: Path, target: Path):
        """
        Merge configuration directories, preserving existing files.
        
        Args:
            source: Source directory
            target: Target directory
        """
        for item in source.rglob("*"):
            if item.is_file():
                relative_path = item.relative_to(source)
                target_file = target / relative_path
                
                # Create parent directories if needed
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                if target_file.exists():
                    # Create backup of existing file
                    backup_file = target_file.with_suffix(f"{target_file.suffix}.backup")
                    shutil.copy2(target_file, backup_file)
                    logger.info(f"Backed up existing file: {target_file} -> {backup_file}")
                
                # Copy source file to target
                shutil.copy2(item, target_file)
                logger.debug(f"Merged file: {item} -> {target_file}")
        
        # Remove source directory after successful merge
        shutil.rmtree(source)
    
    def _set_secure_permissions(self, path: Path):
        """
        Set secure permissions on configuration files and directories.
        
        Args:
            path: Path to secure
        """
        try:
            if path.is_dir():
                # Directory: 700 (owner read/write/execute only)
                path.chmod(0o700)
                
                # Recursively set permissions on contents
                for item in path.rglob("*"):
                    if item.is_dir():
                        item.chmod(0o700)
                    else:
                        item.chmod(0o600)
            else:
                # File: 600 (owner read/write only)
                path.chmod(0o600)
                
            logger.debug(f"Set secure permissions on: {path}")
            
        except Exception as e:
            logger.warning(f"Failed to set permissions on {path}: {e}")
    
    def validate_config_paths(self) -> Dict[str, Any]:
        """
        Validate configuration paths and permissions.
        
        Returns:
            Validation results
        """
        results = {
            "valid_paths": [],
            "invalid_paths": [],
            "permission_issues": [],
            "missing_directories": []
        }
        
        # Check main config directories
        config_dirs = [
            self.home_dir / ".ic" / "config",
            self.home_dir / ".ncp",
            self.home_dir / ".ncpgov"
        ]
        
        for config_dir in config_dirs:
            if config_dir.exists():
                if self._check_directory_permissions(config_dir):
                    results["valid_paths"].append(str(config_dir))
                else:
                    results["permission_issues"].append(str(config_dir))
            else:
                results["missing_directories"].append(str(config_dir))
        
        # Check config files
        config_files = [
            self.get_ncp_config_path(),
            self.get_ncpgov_config_path()
        ]
        
        for config_file in config_files:
            if config_file and config_file.exists():
                if self._check_file_permissions(config_file):
                    results["valid_paths"].append(str(config_file))
                else:
                    results["permission_issues"].append(str(config_file))
        
        return results
    
    def _check_directory_permissions(self, path: Path) -> bool:
        """
        Check if directory has secure permissions (700).
        
        Args:
            path: Directory path to check
            
        Returns:
            True if permissions are secure
        """
        if not path.exists() or not path.is_dir():
            return False
        
        # Check permissions (should be 700)
        mode = path.stat().st_mode & 0o777
        return mode == 0o700
    
    def _check_file_permissions(self, path: Path) -> bool:
        """
        Check if file has secure permissions (600).
        
        Args:
            path: File path to check
            
        Returns:
            True if permissions are secure
        """
        if not path.exists() or not path.is_file():
            return False
        
        # Check permissions (should be 600)
        mode = path.stat().st_mode & 0o777
        return mode == 0o600
    
    def get_config_sources_info(self) -> Dict[str, Any]:
        """
        Get information about configuration sources and their status.
        
        Returns:
            Configuration sources information
        """
        info = {
            "hierarchy": [],
            "platform_configs": {},
            "migration_needed": [],
            "backup_location": str(self._backup_dir)
        }
        
        # Check hierarchy paths
        for path in self.get_config_hierarchy():
            info["hierarchy"].append({
                "path": str(path),
                "exists": path.exists(),
                "readable": path.exists() and os.access(path, os.R_OK)
            })
        
        # Check platform configs
        platforms = ["ncp", "ncpgov"]
        for platform in platforms:
            config_path = self.get_platform_config_path(platform)
            info["platform_configs"][platform] = {
                "path": str(config_path) if config_path else None,
                "exists": config_path.exists() if config_path else False
            }
        
        # Check for migration needs
        migration_sources = [
            self.project_dir / ".ncp",
            self.project_dir / ".ncpgov"
        ]
        
        for source in migration_sources:
            if source.exists():
                info["migration_needed"].append(str(source))
        
        return info
    
    def create_default_config_structure(self) -> Dict[str, Path]:
        """
        Create default configuration directory structure.
        
        Returns:
            Dictionary of created paths
        """
        # Create directories
        created_dirs = self.create_user_config_directories()
        
        # Create default config files if they don't exist
        default_configs = {
            "ic_main": self.home_dir / ".ic" / "config" / "default.yaml",
            "ncp": self.home_dir / ".ncp" / "config.yaml",
            "ncpgov": self.home_dir / ".ncpgov" / "config.yaml"
        }
        
        created_files = {}
        
        for name, config_path in default_configs.items():
            if not config_path.exists():
                try:
                    # Create default config content
                    if name == "ic_main":
                        content = self._get_default_ic_config()
                    elif name == "ncp":
                        content = self._get_default_ncp_config()
                    elif name == "ncpgov":
                        content = self._get_default_ncpgov_config()
                    
                    # Write config file
                    with open(config_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # Set secure permissions
                    config_path.chmod(0o600)
                    
                    created_files[name] = config_path
                    logger.info(f"Created default config: {config_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to create default config {config_path}: {e}")
        
        return {**created_dirs, **created_files}
    
    def _get_default_ic_config(self) -> str:
        """Get default IC configuration content."""
        return """# IC CLI Configuration
version: "1.0"

# Platform configurations
platforms:
  ncp:
    config_path: "~/.ncp/config.yaml"
    regions: ["KR"]
    max_workers: 10
  ncpgov:
    config_path: "~/.ncpgov/config.yaml"
    regions: ["KR"]
    max_workers: 10
    security:
      encryption_enabled: true
      audit_logging_enabled: true
      access_control_enabled: true

# Logging configuration
logging:
  console_level: "ERROR"
  file_level: "INFO"
  file_path: "~/.ic/logs/ic_{date}.log"
  max_files: 30

# Security settings
security:
  sensitive_keys:
    - "password"
    - "secret"
    - "key"
    - "token"
  mask_pattern: "***MASKED***"
  git_hooks_enabled: true
"""
    
    def _get_default_ncp_config(self) -> str:
        """Get default NCP configuration content."""
        return """# NCP Configuration
# Copy this file and update with your actual credentials

default:
  access_key: "your-ncp-access-key"
  secret_key: "your-ncp-secret-key"
  region: "KR"
  platform: "VPC"

# Example profiles
production:
  access_key: "prod-ncp-access-key"
  secret_key: "prod-ncp-secret-key"
  region: "KR"
  platform: "VPC"

development:
  access_key: "dev-ncp-access-key"
  secret_key: "dev-ncp-secret-key"
  region: "KR"
  platform: "Classic"
"""
    
    def _get_default_ncpgov_config(self) -> str:
        """Get default NCPGOV configuration content."""
        return """# NCP Government Cloud Configuration
# Copy this file and update with your actual credentials
# Government cloud requires additional security settings

default:
  access_key: "your-ncpgov-access-key"
  secret_key: "your-ncpgov-secret-key"
  apigw_key: "your-ncpgov-apigw-key"
  region: "KR"
  platform: "VPC"
  
  # Government cloud security settings
  encryption_enabled: true
  audit_logging_enabled: true
  access_control_enabled: true

production:
  access_key: "prod-ncpgov-access-key"
  secret_key: "prod-ncpgov-secret-key"
  apigw_key: "prod-ncpgov-apigw-key"
  region: "KR"
  platform: "VPC"
  encryption_enabled: true
  audit_logging_enabled: true
  access_control_enabled: true
"""