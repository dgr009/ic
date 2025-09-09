"""
File cleanup and backup management module for IC.

This module provides functionality to organize and backup old files.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class FileCleanupManager:
    """
    Manages file cleanup and backup operations.
    """
    
    def __init__(self):
        """Initialize FileCleanupManager."""
        self.backup_dir = Path("backup")
        self.olds_dir = self.backup_dir / "olds"
        self.cleanup_history: List[Dict[str, Any]] = []
    
    def backup_old_files(self, file_patterns: Optional[List[str]] = None) -> bool:
        """
        Backup old files to backup/olds directory.
        
        Args:
            file_patterns: List of file patterns to backup (default: common old files)
            
        Returns:
            True if backup was successful
        """
        if file_patterns is None:
            file_patterns = [
                "*.env*",
                "*.log",
                "logs/",
                "old_*",
                "*.bak",
                "*.backup",
                "temp_*",
                "tmp_*"
            ]
        
        try:
            # Create backup directories
            self.backup_dir.mkdir(exist_ok=True)
            self.olds_dir.mkdir(exist_ok=True)
            
            backed_up_files = []
            
            for pattern in file_patterns:
                files_found = self._find_files_by_pattern(pattern)
                
                for file_path in files_found:
                    backup_path = self._backup_single_file(file_path)
                    if backup_path:
                        backed_up_files.append({
                            "original_path": str(file_path),
                            "backup_path": str(backup_path),
                            "file_type": self._get_file_type(file_path),
                            "size": file_path.stat().st_size if file_path.exists() else 0,
                            "timestamp": datetime.now().isoformat()
                        })
            
            if backed_up_files:
                self.cleanup_history.extend(backed_up_files)
                logger.info(f"Backed up {len(backed_up_files)} files to {self.olds_dir}")
                return True
            else:
                logger.info("No files found to backup")
                return True
                
        except Exception as e:
            logger.error(f"Failed to backup old files: {e}")
            return False
    
    def _find_files_by_pattern(self, pattern: str) -> List[Path]:
        """Find files matching a pattern."""
        files = []
        
        try:
            if pattern.endswith('/'):
                # Directory pattern
                dir_name = pattern.rstrip('/')
                dir_path = Path(dir_name)
                if dir_path.exists() and dir_path.is_dir():
                    files.append(dir_path)
            else:
                # File pattern
                files.extend(Path('.').glob(pattern))
                
        except Exception as e:
            logger.warning(f"Error finding files with pattern '{pattern}': {e}")
        
        return files
    
    def _backup_single_file(self, file_path: Path) -> Optional[Path]:
        """Backup a single file or directory."""
        if not file_path.exists():
            return None
        
        try:
            # Generate backup name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if file_path.is_dir():
                backup_name = f"{file_path.name}_{timestamp}"
                backup_path = self.olds_dir / backup_name
                shutil.copytree(file_path, backup_path)
                # Remove original directory
                shutil.rmtree(file_path)
            else:
                backup_name = f"{file_path.stem}_{timestamp}{file_path.suffix}"
                backup_path = self.olds_dir / backup_name
                shutil.copy2(file_path, backup_path)
                # Remove original file
                file_path.unlink()
            
            logger.debug(f"Backed up {file_path} to {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.warning(f"Failed to backup {file_path}: {e}")
            return None
    
    def _get_file_type(self, file_path: Path) -> str:
        """Determine file type for categorization."""
        if file_path.is_dir():
            return "directory"
        
        suffix = file_path.suffix.lower()
        
        if suffix in ['.env']:
            return "environment_config"
        elif suffix in ['.log']:
            return "log_file"
        elif suffix in ['.bak', '.backup']:
            return "backup_file"
        elif suffix in ['.py']:
            return "python_file"
        elif suffix in ['.yaml', '.yml']:
            return "yaml_config"
        elif suffix in ['.json']:
            return "json_config"
        elif suffix in ['.md']:
            return "documentation"
        else:
            return "other"
    
    def create_cleanup_history_document(self) -> bool:
        """
        Create a document recording all cleanup operations.
        
        Returns:
            True if document was created successfully
        """
        try:
            history_content = self._generate_cleanup_history_content()
            
            history_path = self.backup_dir / "file_cleanup_history.md"
            with open(history_path, 'w', encoding='utf-8') as f:
                f.write(history_content)
            
            logger.info(f"Created cleanup history document at {history_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create cleanup history document: {e}")
            return False
    
    def _generate_cleanup_history_content(self) -> str:
        """Generate cleanup history document content."""
        content = """# IC File Cleanup History

This document records all file cleanup and backup operations performed during the IC configuration migration.

## Overview

During the migration from .env-based configuration to YAML-based configuration, various old files were identified and moved to the backup directory to keep the project clean while preserving important data.

## Backup Structure

```
backup/
├── olds/                           # Old files moved during cleanup
│   ├── .env_YYYYMMDD_HHMMSS       # Original environment files
│   ├── logs_YYYYMMDD_HHMMSS/      # Old log directories
│   └── ...                        # Other backed up files
├── file_cleanup_history.md        # This document
└── migration_history.md           # Configuration migration history
```

## File Categories

### Environment Configuration Files
- `.env` files and variants
- Contains original environment variable configurations
- **Location**: Moved to `backup/olds/`
- **Purpose**: Preserve original configuration for rollback if needed

### Log Files
- `*.log` files and `logs/` directories
- Contains historical application logs
- **Location**: Moved to `backup/olds/`
- **Purpose**: Archive old logs while implementing fixed log paths

### Backup Files
- `*.bak`, `*.backup` files
- Previous backup files from other operations
- **Location**: Consolidated in `backup/olds/`
- **Purpose**: Centralize all backup files

### Temporary Files
- `temp_*`, `tmp_*`, `old_*` files
- Temporary files from development or previous operations
- **Location**: Moved to `backup/olds/`
- **Purpose**: Clean up workspace while preserving potentially important data

## Cleanup Operations

"""
        
        if self.cleanup_history:
            # Group files by type
            files_by_type = {}
            for file_info in self.cleanup_history:
                file_type = file_info['file_type']
                if file_type not in files_by_type:
                    files_by_type[file_type] = []
                files_by_type[file_type].append(file_info)
            
            for file_type, files in files_by_type.items():
                content += f"### {file_type.replace('_', ' ').title()}\n\n"
                
                total_size = sum(f['size'] for f in files)
                content += f"**Total Files**: {len(files)}\n"
                content += f"**Total Size**: {self._format_size(total_size)}\n\n"
                
                content += "| Original Path | Backup Path | Size | Timestamp |\n"
                content += "|---------------|-------------|------|----------|\n"
                
                for file_info in files:
                    content += f"| `{file_info['original_path']}` | `{file_info['backup_path']}` | {self._format_size(file_info['size'])} | {file_info['timestamp'][:19]} |\n"
                
                content += "\n"
        else:
            content += "No cleanup operations recorded.\n\n"
        
        content += """## File Roles and Purposes

### Original .env Files
- **Role**: Primary configuration source for the old system
- **Contents**: Environment variables for all services (AWS, GCP, Azure, etc.)
- **Migration**: Values extracted and categorized into `config/default.yaml` and `config/secrets.yaml`
- **Backup Reason**: Preserve for rollback and reference

### Log Files
- **Role**: Application runtime logs and debugging information
- **Contents**: Historical execution logs, error messages, debug information
- **Migration**: New fixed log path implemented at `~/.ic/logs/`
- **Backup Reason**: Archive historical data while implementing new logging system

### Development Files
- **Role**: Temporary files created during development
- **Contents**: Test files, temporary configurations, development artifacts
- **Migration**: Not migrated, but preserved for reference
- **Backup Reason**: Clean workspace while preserving potentially useful development data

## Recovery Instructions

### Restoring Original .env Configuration
If you need to restore the original .env-based configuration:

1. Copy the backed up .env file from `backup/olds/` to the project root
2. Rename or remove the `config/` directory
3. Restart the application

### Accessing Historical Logs
Historical logs are preserved in `backup/olds/logs_*/` directories and can be accessed for debugging or audit purposes.

### Recovering Specific Files
All backed up files maintain their original structure and can be restored by copying them back to their original locations.

## Cleanup Benefits

1. **Cleaner Workspace**: Removed clutter from the project root
2. **Organized Structure**: All backups centralized in one location
3. **Preserved Data**: No data loss - everything is backed up
4. **Clear Migration Path**: Easy to identify what was changed
5. **Rollback Capability**: Simple restoration process if needed

## Maintenance

- Backup files are preserved indefinitely
- Consider periodic cleanup of very old backup files (>1 year)
- Monitor backup directory size if disk space becomes a concern
- Backup directory can be excluded from version control

"""
        
        return content
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        
        return f"{size_bytes:.1f} TB"
    
    def get_backup_summary(self) -> Dict[str, Any]:
        """
        Get summary of backup operations.
        
        Returns:
            Dictionary containing backup summary
        """
        if not self.cleanup_history:
            return {"total_files": 0, "total_size": 0, "file_types": {}}
        
        total_files = len(self.cleanup_history)
        total_size = sum(f['size'] for f in self.cleanup_history)
        
        file_types = {}
        for file_info in self.cleanup_history:
            file_type = file_info['file_type']
            if file_type not in file_types:
                file_types[file_type] = {"count": 0, "size": 0}
            file_types[file_type]["count"] += 1
            file_types[file_type]["size"] += file_info['size']
        
        return {
            "total_files": total_files,
            "total_size": total_size,
            "file_types": file_types,
            "backup_location": str(self.olds_dir)
        }
    
    def validate_backups(self) -> Dict[str, List[str]]:
        """
        Validate that backed up files exist and are accessible.
        
        Returns:
            Dictionary of validation results
        """
        issues = {
            "missing_backups": [],
            "corrupted_backups": [],
            "permission_issues": []
        }
        
        for file_info in self.cleanup_history:
            backup_path = Path(file_info['backup_path'])
            
            if not backup_path.exists():
                issues["missing_backups"].append(file_info['backup_path'])
                continue
            
            try:
                # Try to read a small portion to check if file is accessible
                if backup_path.is_file():
                    with open(backup_path, 'rb') as f:
                        f.read(1024)  # Read first 1KB
                elif backup_path.is_dir():
                    list(backup_path.iterdir())  # List directory contents
                    
            except PermissionError:
                issues["permission_issues"].append(file_info['backup_path'])
            except Exception:
                issues["corrupted_backups"].append(file_info['backup_path'])
        
        return issues