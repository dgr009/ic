"""
Configuration Migration Utilities

This module provides utilities for migrating configuration files and folders
with user confirmation and rollback capabilities.
"""

import os
import shutil
import yaml
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from datetime import datetime
import logging

from .path_manager import ConfigPathManager, ConfigPathError

logger = logging.getLogger(__name__)


class ConfigMigrationError(Exception):
    """Configuration migration related errors"""
    pass


class ConfigMigrationUtils:
    """
    Utilities for configuration migration with user confirmation and rollback.
    """
    
    def __init__(self, path_manager: Optional[ConfigPathManager] = None):
        self.path_manager = path_manager or ConfigPathManager()
        self._migration_log = []
    
    def interactive_migration(self, confirm_func: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        """
        Perform interactive configuration migration with user confirmation.
        
        Args:
            confirm_func: Function to get user confirmation (str -> bool)
            
        Returns:
            Migration results
        """
        if confirm_func is None:
            confirm_func = self._default_confirm_func
        
        results = {
            "migrations_performed": [],
            "migrations_skipped": [],
            "errors": [],
            "backup_locations": []
        }
        
        # Check what needs migration
        migration_info = self._analyze_migration_needs()
        
        if not migration_info["needs_migration"]:
            logger.info("No configuration migration needed")
            return results
        
        # Display migration summary
        self._display_migration_summary(migration_info)
        
        # Ask for overall confirmation
        if not confirm_func("Proceed with configuration migration?"):
            logger.info("Configuration migration cancelled by user")
            return results
        
        # Perform migrations
        migration_results = self.path_manager.migrate_config_folders(confirm_func)
        
        # Process results
        for config_name, success in migration_results.items():
            if success:
                results["migrations_performed"].append(config_name)
            else:
                results["migrations_skipped"].append(config_name)
        
        # Create default structure if needed
        if results["migrations_performed"]:
            try:
                created_paths = self.path_manager.create_default_config_structure()
                logger.info(f"Created default configuration structure: {list(created_paths.keys())}")
            except Exception as e:
                results["errors"].append(f"Failed to create default structure: {e}")
        
        return results
    
    def _analyze_migration_needs(self) -> Dict[str, Any]:
        """
        Analyze what configuration migrations are needed.
        
        Returns:
            Migration analysis results
        """
        analysis = {
            "needs_migration": False,
            "project_configs": [],
            "existing_user_configs": [],
            "conflicts": []
        }
        
        # Check for project-level configs that should be migrated
        project_configs = [
            (self.path_manager.project_dir / ".ncp", "NCP"),
            (self.path_manager.project_dir / ".ncpgov", "NCPGOV")
        ]
        
        for config_path, config_name in project_configs:
            if config_path.exists():
                analysis["project_configs"].append({
                    "path": str(config_path),
                    "name": config_name,
                    "size": self._get_directory_size(config_path)
                })
                analysis["needs_migration"] = True
        
        # Check for existing user configs
        user_configs = [
            (self.path_manager.home_dir / ".ncp", "NCP"),
            (self.path_manager.home_dir / ".ncpgov", "NCPGOV")
        ]
        
        for config_path, config_name in user_configs:
            if config_path.exists():
                analysis["existing_user_configs"].append({
                    "path": str(config_path),
                    "name": config_name
                })
                
                # Check for conflicts
                project_equivalent = self.path_manager.project_dir / config_path.name
                if project_equivalent.exists():
                    analysis["conflicts"].append({
                        "project": str(project_equivalent),
                        "user": str(config_path),
                        "name": config_name
                    })
        
        return analysis
    
    def _display_migration_summary(self, migration_info: Dict[str, Any]):
        """
        Display migration summary to user.
        
        Args:
            migration_info: Migration analysis results
        """
        print("\n" + "="*60)
        print("CONFIGURATION MIGRATION SUMMARY")
        print("="*60)
        
        if migration_info["project_configs"]:
            print("\nConfigurations to migrate:")
            for config in migration_info["project_configs"]:
                size_str = self._format_size(config["size"])
                print(f"  • {config['name']}: {config['path']} ({size_str})")
        
        if migration_info["existing_user_configs"]:
            print("\nExisting user configurations:")
            for config in migration_info["existing_user_configs"]:
                print(f"  • {config['name']}: {config['path']}")
        
        if migration_info["conflicts"]:
            print("\nCONFLICTS DETECTED:")
            for conflict in migration_info["conflicts"]:
                print(f"  ⚠️  {conflict['name']}:")
                print(f"     Project: {conflict['project']}")
                print(f"     User:    {conflict['user']}")
                print(f"     → Files will be merged, existing user files backed up")
        
        print(f"\nMigration target: {self.path_manager.home_dir}")
        print(f"Backup location: {self.path_manager._backup_dir}")
        print("="*60)
    
    def _default_confirm_func(self, message: str) -> bool:
        """
        Default confirmation function using console input.
        
        Args:
            message: Confirmation message
            
        Returns:
            User's confirmation choice
        """
        while True:
            response = input(f"{message} [y/N]: ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no', '']:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    def _get_directory_size(self, path: Path) -> int:
        """
        Get total size of directory in bytes.
        
        Args:
            path: Directory path
            
        Returns:
            Total size in bytes
        """
        total_size = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception as e:
            logger.warning(f"Failed to calculate size for {path}: {e}")
        
        return total_size
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Format size in human readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    def validate_migration_prerequisites(self) -> Dict[str, Any]:
        """
        Validate prerequisites for configuration migration.
        
        Returns:
            Validation results
        """
        results = {
            "can_migrate": True,
            "issues": [],
            "warnings": []
        }
        
        # Check write permissions to home directory
        if not os.access(self.path_manager.home_dir, os.W_OK):
            results["can_migrate"] = False
            results["issues"].append(f"No write permission to home directory: {self.path_manager.home_dir}")
        
        # Check available disk space
        try:
            stat = shutil.disk_usage(self.path_manager.home_dir)
            available_space = stat.free
            
            # Calculate space needed for migration
            space_needed = 0
            for config_path in [self.path_manager.project_dir / ".ncp", self.path_manager.project_dir / ".ncpgov"]:
                if config_path.exists():
                    space_needed += self._get_directory_size(config_path) * 2  # Original + backup
            
            if space_needed > available_space:
                results["can_migrate"] = False
                results["issues"].append(
                    f"Insufficient disk space. Need: {self._format_size(space_needed)}, "
                    f"Available: {self._format_size(available_space)}"
                )
        except Exception as e:
            results["warnings"].append(f"Could not check disk space: {e}")
        
        # Check for existing backup conflicts
        backup_dir = self.path_manager._backup_dir
        if backup_dir.exists():
            existing_backups = list(backup_dir.glob("*_migration_*"))
            if len(existing_backups) > 10:
                results["warnings"].append(
                    f"Many existing migration backups found ({len(existing_backups)}). "
                    "Consider cleaning up old backups."
                )
        
        return results
    
    def rollback_migration(self, backup_timestamp: str) -> Dict[str, Any]:
        """
        Rollback a configuration migration using backup.
        
        Args:
            backup_timestamp: Timestamp of backup to restore
            
        Returns:
            Rollback results
        """
        results = {
            "rollback_successful": False,
            "restored_configs": [],
            "errors": []
        }
        
        backup_dir = self.path_manager._backup_dir
        
        # Find backup directories matching timestamp
        backup_patterns = [
            f"ncp_migration_{backup_timestamp}",
            f"ncpgov_migration_{backup_timestamp}"
        ]
        
        for pattern in backup_patterns:
            backup_path = backup_dir / pattern
            
            if not backup_path.exists():
                continue
            
            try:
                # Determine target path
                if "ncp_migration" in pattern:
                    target_path = self.path_manager.project_dir / ".ncp"
                    user_path = self.path_manager.home_dir / ".ncp"
                elif "ncpgov_migration" in pattern:
                    target_path = self.path_manager.project_dir / ".ncpgov"
                    user_path = self.path_manager.home_dir / ".ncpgov"
                else:
                    continue
                
                # Remove current user config if exists
                if user_path.exists():
                    shutil.rmtree(user_path)
                
                # Restore from backup to project directory
                shutil.copytree(backup_path, target_path)
                
                results["restored_configs"].append(str(target_path))
                logger.info(f"Restored configuration from backup: {backup_path} -> {target_path}")
                
            except Exception as e:
                error_msg = f"Failed to rollback {pattern}: {e}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
        
        results["rollback_successful"] = len(results["restored_configs"]) > 0 and not results["errors"]
        
        return results
    
    def list_available_backups(self) -> List[Dict[str, Any]]:
        """
        List available migration backups.
        
        Returns:
            List of backup information
        """
        backups = []
        backup_dir = self.path_manager._backup_dir
        
        if not backup_dir.exists():
            return backups
        
        # Find migration backups
        for backup_path in backup_dir.glob("*_migration_*"):
            if backup_path.is_dir():
                try:
                    # Parse backup name
                    name_parts = backup_path.name.split("_")
                    if len(name_parts) >= 3:
                        config_type = name_parts[0]
                        timestamp = "_".join(name_parts[2:])
                        
                        # Get backup info
                        stat = backup_path.stat()
                        size = self._get_directory_size(backup_path)
                        
                        backups.append({
                            "path": str(backup_path),
                            "config_type": config_type,
                            "timestamp": timestamp,
                            "created": datetime.fromtimestamp(stat.st_ctime),
                            "size": size,
                            "size_formatted": self._format_size(size)
                        })
                        
                except Exception as e:
                    logger.warning(f"Failed to parse backup info for {backup_path}: {e}")
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created"], reverse=True)
        
        return backups
    
    def cleanup_old_backups(self, keep_count: int = 5) -> Dict[str, Any]:
        """
        Clean up old migration backups, keeping only the most recent ones.
        
        Args:
            keep_count: Number of backups to keep for each config type
            
        Returns:
            Cleanup results
        """
        results = {
            "cleaned_up": [],
            "kept": [],
            "errors": []
        }
        
        backups = self.list_available_backups()
        
        # Group backups by config type
        backup_groups = {}
        for backup in backups:
            config_type = backup["config_type"]
            if config_type not in backup_groups:
                backup_groups[config_type] = []
            backup_groups[config_type].append(backup)
        
        # Clean up each group
        for config_type, group_backups in backup_groups.items():
            # Sort by creation time (newest first)
            group_backups.sort(key=lambda x: x["created"], reverse=True)
            
            # Keep the most recent ones
            to_keep = group_backups[:keep_count]
            to_remove = group_backups[keep_count:]
            
            for backup in to_keep:
                results["kept"].append(backup["path"])
            
            for backup in to_remove:
                try:
                    backup_path = Path(backup["path"])
                    shutil.rmtree(backup_path)
                    results["cleaned_up"].append(backup["path"])
                    logger.info(f"Cleaned up old backup: {backup_path}")
                except Exception as e:
                    error_msg = f"Failed to remove backup {backup['path']}: {e}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
        
        return results


def create_migration_confirmation_callback(interactive: bool = True) -> Callable[[str], bool]:
    """
    Create a confirmation callback function for migration.
    
    Args:
        interactive: Whether to use interactive confirmation
        
    Returns:
        Confirmation callback function
    """
    if interactive:
        def interactive_confirm(message: str) -> bool:
            while True:
                response = input(f"{message} [y/N]: ").strip().lower()
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no', '']:
                    return False
                else:
                    print("Please enter 'y' for yes or 'n' for no.")
        
        return interactive_confirm
    else:
        # Non-interactive: always confirm
        def auto_confirm(message: str) -> bool:
            logger.info(f"Auto-confirming: {message}")
            return True
        
        return auto_confirm