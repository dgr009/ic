#!/usr/bin/env python3
"""
Rollback system for IC CLI project structure refactoring.

This module provides comprehensive rollback capabilities to restore the previous
module structure, configurations, and project state in case migration fails.
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class RollbackOperation:
    """Represents a single rollback operation."""
    operation_type: str  # 'restore_file', 'restore_directory', 'remove_file', 'remove_directory'
    source_path: Optional[str] = None
    target_path: Optional[str] = None
    success: bool = False
    error_message: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

@dataclass
class RollbackStatus:
    """Overall rollback status."""
    success: bool
    total_operations: int
    successful_operations: int
    failed_operations: int
    operations: List[RollbackOperation]
    timestamp: str
    backup_restored_from: Optional[str] = None

class MigrationRollback:
    """
    Comprehensive migration rollback system.
    
    This class provides methods to:
    1. Restore previous module structure from backups
    2. Restore configuration files from backups
    3. Validate rollback completeness
    4. Generate rollback reports
    """
    
    def __init__(self, project_root: Optional[Path] = None, backup_dir: Optional[Path] = None):
        """Initialize the rollback system."""
        self.project_root = project_root or Path.cwd()
        self.validation_dir = self.project_root / ".migration_validation"
        
        # Find the most recent backup if not specified
        if backup_dir is None:
            backup_dir = self._find_latest_backup()
        
        self.backup_dir = backup_dir
        self.rollback_dir = self.validation_dir / "rollback"
        self.operations: List[RollbackOperation] = []
        
        # Ensure rollback directory exists
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized MigrationRollback with project root: {self.project_root}")
        logger.info(f"Using backup directory: {self.backup_dir}")
        logger.info(f"Rollback data will be stored in: {self.rollback_dir}")

    def _find_latest_backup(self) -> Optional[Path]:
        """Find the most recent pre-migration backup."""
        backup_base = self.project_root / "backup"
        
        if not backup_base.exists():
            logger.error("No backup directory found")
            return None
        
        # Look for pre-migration backups
        pre_migration_backups = list(backup_base.glob("pre_migration_*"))
        
        if not pre_migration_backups:
            logger.error("No pre-migration backups found")
            return None
        
        # Sort by creation time and get the latest
        latest_backup = max(pre_migration_backups, key=lambda p: p.stat().st_mtime)
        logger.info(f"Found latest backup: {latest_backup}")
        
        return latest_backup

    def rollback_all(self) -> RollbackStatus:
        """
        Perform complete rollback of migration changes.
        
        Returns:
            RollbackStatus with overall results
        """
        logger.info("Starting comprehensive migration rollback...")
        
        if not self.backup_dir or not self.backup_dir.exists():
            logger.error(f"Backup directory not found or invalid: {self.backup_dir}")
            return RollbackStatus(
                success=False,
                total_operations=0,
                successful_operations=0,
                failed_operations=1,
                operations=[RollbackOperation(
                    operation_type="validation",
                    success=False,
                    error_message="Backup directory not found or invalid"
                )],
                timestamp=datetime.now().isoformat()
            )
        
        try:
            # Load backup manifest
            manifest = self._load_backup_manifest()
            if not manifest:
                logger.error("Failed to load backup manifest")
                return RollbackStatus(
                    success=False,
                    total_operations=0,
                    successful_operations=0,
                    failed_operations=1,
                    operations=[RollbackOperation(
                        operation_type="validation",
                        success=False,
                        error_message="Failed to load backup manifest"
                    )],
                    timestamp=datetime.now().isoformat()
                )
            
            # 1. Remove new unified module structure
            logger.info("Removing new unified module structure...")
            self._remove_unified_modules()
            
            # 2. Restore original module structure
            logger.info("Restoring original module structure...")
            self._restore_module_structure(manifest)
            
            # 3. Restore configuration files
            logger.info("Restoring configuration files...")
            self._restore_configurations(manifest)
            
            # 4. Restore CLI file
            logger.info("Restoring CLI file...")
            self._restore_cli_file(manifest)
            
            # 5. Restore test structure
            logger.info("Restoring test structure...")
            self._restore_test_structure(manifest)
            
            # 6. Validate rollback completeness
            logger.info("Validating rollback completeness...")
            validation_result = self._validate_rollback_completeness()
            
            # Save rollback data
            rollback_data = {
                "timestamp": datetime.now().isoformat(),
                "backup_restored_from": str(self.backup_dir),
                "operations": [asdict(op) for op in self.operations],
                "validation_result": validation_result
            }
            
            rollback_file = self.rollback_dir / "rollback_log.json"
            with open(rollback_file, 'w') as f:
                json.dump(rollback_data, f, indent=2, default=str)
            
            # Generate rollback report
            self._generate_rollback_report(rollback_data)
            
            # Create rollback status
            successful_ops = len([op for op in self.operations if op.success])
            failed_ops = len([op for op in self.operations if not op.success])
            
            rollback_status = RollbackStatus(
                success=failed_ops == 0 and validation_result.get("success", False),
                total_operations=len(self.operations),
                successful_operations=successful_ops,
                failed_operations=failed_ops,
                operations=self.operations,
                timestamp=datetime.now().isoformat(),
                backup_restored_from=str(self.backup_dir)
            )
            
            logger.info(f"Migration rollback completed. Results saved to: {rollback_file}")
            
            return rollback_status
            
        except Exception as e:
            logger.error(f"Migration rollback failed: {e}")
            return RollbackStatus(
                success=False,
                total_operations=len(self.operations),
                successful_operations=len([op for op in self.operations if op.success]),
                failed_operations=len([op for op in self.operations if not op.success]) + 1,
                operations=self.operations + [RollbackOperation(
                    operation_type="system_error",
                    success=False,
                    error_message=str(e)
                )],
                timestamp=datetime.now().isoformat(),
                backup_restored_from=str(self.backup_dir) if self.backup_dir else None
            )

    def _load_backup_manifest(self) -> Optional[Dict[str, Any]]:
        """Load backup manifest file."""
        manifest_file = self.backup_dir / "backup_manifest.json"
        
        if not manifest_file.exists():
            logger.error(f"Backup manifest not found: {manifest_file}")
            return None
        
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            logger.info(f"Loaded backup manifest with {len(manifest.get('backup_items', []))} items")
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to load backup manifest: {e}")
            return None

    def _remove_unified_modules(self) -> None:
        """Remove the new unified module structure."""
        unified_paths = [
            self.project_root / "src" / "ic" / "platforms" / "ncp",
            self.project_root / "src" / "ic" / "platforms" / "ncpgov",
            self.project_root / "src" / "ic" / "platforms"  # Remove if empty
        ]
        
        for path in unified_paths:
            if path.exists():
                try:
                    if path.is_dir():
                        # Check if directory is empty before removing platforms dir
                        if path.name == "platforms":
                            if not any(path.iterdir()):
                                shutil.rmtree(path)
                                self.operations.append(RollbackOperation(
                                    operation_type="remove_directory",
                                    target_path=str(path),
                                    success=True
                                ))
                            else:
                                logger.info(f"Platforms directory not empty, keeping: {path}")
                        else:
                            shutil.rmtree(path)
                            self.operations.append(RollbackOperation(
                                operation_type="remove_directory",
                                target_path=str(path),
                                success=True
                            ))
                    else:
                        path.unlink()
                        self.operations.append(RollbackOperation(
                            operation_type="remove_file",
                            target_path=str(path),
                            success=True
                        ))
                    
                    logger.debug(f"Removed unified module path: {path}")
                    
                except Exception as e:
                    logger.error(f"Failed to remove unified module path {path}: {e}")
                    self.operations.append(RollbackOperation(
                        operation_type="remove_directory" if path.is_dir() else "remove_file",
                        target_path=str(path),
                        success=False,
                        error_message=str(e)
                    ))

    def _restore_module_structure(self, manifest: Dict[str, Any]) -> None:
        """Restore original module structure from backup."""
        backup_items = manifest.get("backup_items", [])
        
        # Restore module directories
        module_items = [
            item for item in backup_items 
            if item["item"] in ["ncp", "ncp_module", "ncpgov", "ncpgov_module"]
        ]
        
        for item in module_items:
            if not item["success"]:
                continue
            
            backup_path = Path(item["backup"])
            target_path = Path(item["source"])
            
            try:
                if backup_path.exists():
                    # Remove existing target if it exists
                    if target_path.exists():
                        if target_path.is_dir():
                            shutil.rmtree(target_path)
                        else:
                            target_path.unlink()
                    
                    # Restore from backup
                    if backup_path.is_dir():
                        shutil.copytree(backup_path, target_path)
                        self.operations.append(RollbackOperation(
                            operation_type="restore_directory",
                            source_path=str(backup_path),
                            target_path=str(target_path),
                            success=True
                        ))
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_path, target_path)
                        self.operations.append(RollbackOperation(
                            operation_type="restore_file",
                            source_path=str(backup_path),
                            target_path=str(target_path),
                            success=True
                        ))
                    
                    logger.debug(f"Restored module: {item['item']} -> {target_path}")
                    
                else:
                    logger.warning(f"Backup path not found: {backup_path}")
                    self.operations.append(RollbackOperation(
                        operation_type="restore_directory",
                        source_path=str(backup_path),
                        target_path=str(target_path),
                        success=False,
                        error_message="Backup path not found"
                    ))
                    
            except Exception as e:
                logger.error(f"Failed to restore module {item['item']}: {e}")
                self.operations.append(RollbackOperation(
                    operation_type="restore_directory",
                    source_path=str(backup_path),
                    target_path=str(target_path),
                    success=False,
                    error_message=str(e)
                ))

    def _restore_configurations(self, manifest: Dict[str, Any]) -> None:
        """Restore configuration files from backup."""
        config_backup_dir = self.backup_dir / "configs"
        
        if not config_backup_dir.exists():
            logger.warning("No configuration backups found")
            return
        
        # Restore all configuration files
        for config_file in config_backup_dir.rglob("*"):
            if config_file.is_file():
                try:
                    # Determine target path
                    relative_path = config_file.relative_to(config_backup_dir)
                    
                    # Try to restore to project root first, then home directory
                    possible_targets = [
                        self.project_root / relative_path,
                        Path.home() / relative_path
                    ]
                    
                    # Choose the appropriate target based on the path
                    if str(relative_path).startswith(".ic"):
                        target_path = Path.home() / relative_path
                    elif str(relative_path).startswith(".ncp") or str(relative_path).startswith(".ncpgov"):
                        target_path = Path.home() / relative_path
                    else:
                        target_path = self.project_root / relative_path
                    
                    # Ensure target directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Restore configuration file
                    shutil.copy2(config_file, target_path)
                    
                    self.operations.append(RollbackOperation(
                        operation_type="restore_file",
                        source_path=str(config_file),
                        target_path=str(target_path),
                        success=True
                    ))
                    
                    logger.debug(f"Restored configuration: {config_file} -> {target_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to restore configuration {config_file}: {e}")
                    self.operations.append(RollbackOperation(
                        operation_type="restore_file",
                        source_path=str(config_file),
                        target_path="unknown",
                        success=False,
                        error_message=str(e)
                    ))

    def _restore_cli_file(self, manifest: Dict[str, Any]) -> None:
        """Restore CLI file from backup."""
        backup_items = manifest.get("backup_items", [])
        
        cli_item = next((item for item in backup_items if item["item"] == "cli"), None)
        
        if not cli_item or not cli_item["success"]:
            logger.warning("No CLI backup found")
            return
        
        backup_path = Path(cli_item["backup"])
        target_path = Path(cli_item["source"])
        
        try:
            if backup_path.exists():
                # Ensure target directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Restore CLI file
                shutil.copy2(backup_path, target_path)
                
                self.operations.append(RollbackOperation(
                    operation_type="restore_file",
                    source_path=str(backup_path),
                    target_path=str(target_path),
                    success=True
                ))
                
                logger.debug(f"Restored CLI file: {backup_path} -> {target_path}")
                
            else:
                logger.warning(f"CLI backup not found: {backup_path}")
                self.operations.append(RollbackOperation(
                    operation_type="restore_file",
                    source_path=str(backup_path),
                    target_path=str(target_path),
                    success=False,
                    error_message="CLI backup not found"
                ))
                
        except Exception as e:
            logger.error(f"Failed to restore CLI file: {e}")
            self.operations.append(RollbackOperation(
                operation_type="restore_file",
                source_path=str(backup_path),
                target_path=str(target_path),
                success=False,
                error_message=str(e)
            ))

    def _restore_test_structure(self, manifest: Dict[str, Any]) -> None:
        """Restore test structure from backup."""
        backup_items = manifest.get("backup_items", [])
        
        tests_item = next((item for item in backup_items if item["item"] == "tests"), None)
        
        if not tests_item or not tests_item["success"]:
            logger.warning("No tests backup found")
            return
        
        backup_path = Path(tests_item["backup"])
        target_path = Path(tests_item["source"])
        
        try:
            if backup_path.exists():
                # Remove existing tests directory
                if target_path.exists():
                    shutil.rmtree(target_path)
                
                # Restore tests directory
                shutil.copytree(backup_path, target_path)
                
                self.operations.append(RollbackOperation(
                    operation_type="restore_directory",
                    source_path=str(backup_path),
                    target_path=str(target_path),
                    success=True
                ))
                
                logger.debug(f"Restored tests directory: {backup_path} -> {target_path}")
                
            else:
                logger.warning(f"Tests backup not found: {backup_path}")
                self.operations.append(RollbackOperation(
                    operation_type="restore_directory",
                    source_path=str(backup_path),
                    target_path=str(target_path),
                    success=False,
                    error_message="Tests backup not found"
                ))
                
        except Exception as e:
            logger.error(f"Failed to restore tests directory: {e}")
            self.operations.append(RollbackOperation(
                operation_type="restore_directory",
                source_path=str(backup_path),
                target_path=str(target_path),
                success=False,
                error_message=str(e)
            ))

    def _validate_rollback_completeness(self) -> Dict[str, Any]:
        """
        Validate that rollback was completed successfully.
        
        Returns:
            Dict containing validation results
        """
        validation_results = {
            "success": True,
            "checks": [],
            "errors": [],
            "warnings": []
        }
        
        # Check that original modules exist
        original_modules = [
            self.project_root / "ncp",
            self.project_root / "ncp_module", 
            self.project_root / "ncpgov",
            self.project_root / "ncpgov_module"
        ]
        
        for module_path in original_modules:
            if module_path.exists():
                validation_results["checks"].append(f"✅ Original module exists: {module_path}")
            else:
                validation_results["errors"].append(f"❌ Original module missing: {module_path}")
                validation_results["success"] = False
        
        # Check that unified modules are removed
        unified_modules = [
            self.project_root / "src" / "ic" / "platforms" / "ncp",
            self.project_root / "src" / "ic" / "platforms" / "ncpgov"
        ]
        
        for module_path in unified_modules:
            if not module_path.exists():
                validation_results["checks"].append(f"✅ Unified module removed: {module_path}")
            else:
                validation_results["warnings"].append(f"⚠️ Unified module still exists: {module_path}")
        
        # Test CLI functionality
        try:
            result = subprocess.run(
                ["python", "-m", "src.ic.cli", "--help"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                validation_results["checks"].append("✅ CLI help command works")
            else:
                validation_results["errors"].append(f"❌ CLI help command failed: {result.stderr}")
                validation_results["success"] = False
                
        except Exception as e:
            validation_results["errors"].append(f"❌ CLI test failed: {e}")
            validation_results["success"] = False
        
        # Test original module imports
        import_tests = [
            "from ncp.ec2 import info",
            "from ncp_module.rds import info",
            "from ncpgov.ec2 import info", 
            "from ncpgov_module.rds import info"
        ]
        
        for import_test in import_tests:
            try:
                # Parse import statement to extract module and attribute
                if import_test.startswith("from ") and " import " in import_test:
                    parts = import_test.replace("from ", "").split(" import ")
                    module_name = parts[0].strip()
                    attr_name = parts[1].strip()
                    
                    import importlib
                    module = importlib.import_module(module_name)
                    getattr(module, attr_name)  # Check if attribute exists
                    
                validation_results["checks"].append(f"✅ Import works: {import_test}")
            except Exception as e:
                validation_results["errors"].append(f"❌ Import failed: {import_test} - {e}")
                validation_results["success"] = False
        
        return validation_results

    def _generate_rollback_report(self, rollback_data: Dict[str, Any]) -> None:
        """Generate human-readable rollback report."""
        report_file = self.rollback_dir / "rollback_report.md"
        
        with open(report_file, 'w') as f:
            f.write("# Migration Rollback Report\n\n")
            f.write(f"**Generated:** {rollback_data['timestamp']}\n")
            f.write(f"**Backup Restored From:** {rollback_data['backup_restored_from']}\n\n")
            
            # Operations Summary
            operations = rollback_data.get('operations', [])
            successful_ops = [op for op in operations if op['success']]
            failed_ops = [op for op in operations if not op['success']]
            
            f.write("## Rollback Operations Summary\n\n")
            f.write(f"- **Total Operations:** {len(operations)}\n")
            f.write(f"- **Successful:** {len(successful_ops)}\n")
            f.write(f"- **Failed:** {len(failed_ops)}\n\n")
            
            # Failed Operations
            if failed_ops:
                f.write("### Failed Operations\n\n")
                for op in failed_ops:
                    f.write(f"- **{op['operation_type']}**: {op.get('target_path', 'N/A')}\n")
                    f.write(f"  - Error: {op.get('error_message', 'Unknown error')}\n")
                f.write("\n")
            
            # Validation Results
            validation = rollback_data.get('validation_result', {})
            f.write("## Rollback Validation\n\n")
            
            if validation.get('success', False):
                f.write("### ✅ Validation Status: PASSED\n\n")
            else:
                f.write("### ❌ Validation Status: FAILED\n\n")
            
            # Validation Checks
            checks = validation.get('checks', [])
            if checks:
                f.write("#### Successful Checks\n\n")
                for check in checks:
                    f.write(f"- {check}\n")
                f.write("\n")
            
            # Validation Errors
            errors = validation.get('errors', [])
            if errors:
                f.write("#### Validation Errors\n\n")
                for error in errors:
                    f.write(f"- {error}\n")
                f.write("\n")
            
            # Validation Warnings
            warnings = validation.get('warnings', [])
            if warnings:
                f.write("#### Validation Warnings\n\n")
                for warning in warnings:
                    f.write(f"- {warning}\n")
                f.write("\n")
            
            # Next Steps
            f.write("## Next Steps\n\n")
            if validation.get('success', False) and not failed_ops:
                f.write("1. ✅ Rollback completed successfully\n")
                f.write("2. ✅ All original functionality restored\n")
                f.write("3. 📝 Review rollback report for any warnings\n")
                f.write("4. 🔄 Consider addressing migration issues before retry\n")
            else:
                f.write("1. ❌ Rollback completed with issues\n")
                f.write("2. 🔍 Review failed operations and validation errors\n")
                f.write("3. 🛠️ Manually address any remaining issues\n")
                f.write("4. ✅ Verify system functionality before proceeding\n")
        
        logger.info(f"Rollback report generated: {report_file}")

    def create_rollback_script(self) -> Path:
        """
        Create a standalone rollback script for emergency use.
        
        Returns:
            Path to the generated rollback script
        """
        script_content = f'''#!/usr/bin/env python3
"""
Emergency rollback script for IC CLI migration.
Generated automatically - can be run independently.
"""

import sys
import shutil
from pathlib import Path

def emergency_rollback():
    """Perform emergency rollback using hardcoded paths."""
    project_root = Path("{self.project_root}")
    backup_dir = Path("{self.backup_dir}")
    
    print("🚨 Starting emergency rollback...")
    
    # Remove unified modules
    unified_paths = [
        project_root / "src" / "ic" / "platforms" / "ncp",
        project_root / "src" / "ic" / "platforms" / "ncpgov"
    ]
    
    for path in unified_paths:
        if path.exists():
            try:
                shutil.rmtree(path)
                print(f"✅ Removed: {{path}}")
            except Exception as e:
                print(f"❌ Failed to remove {{path}}: {{e}}")
    
    # Restore original modules
    modules_backup = backup_dir / "modules"
    if modules_backup.exists():
        for module_backup in modules_backup.iterdir():
            if module_backup.is_dir():
                target = project_root / module_backup.name
                try:
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(module_backup, target)
                    print(f"✅ Restored: {{module_backup.name}}")
                except Exception as e:
                    print(f"❌ Failed to restore {{module_backup.name}}: {{e}}")
    
    print("🚨 Emergency rollback completed!")
    print("⚠️  Please run full validation to ensure system integrity")

if __name__ == "__main__":
    emergency_rollback()
'''
        
        script_path = self.rollback_dir / "emergency_rollback.py"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make script executable
        script_path.chmod(0o755)
        
        logger.info(f"Emergency rollback script created: {script_path}")
        return script_path


def main():
    """Main entry point for migration rollback."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migration rollback system for IC CLI")
    parser.add_argument("--project-root", type=Path, help="Project root directory")
    parser.add_argument("--backup-dir", type=Path, help="Backup directory to restore from")
    parser.add_argument("--create-emergency-script", action="store_true", 
                       help="Create emergency rollback script")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        rollback = MigrationRollback(args.project_root, args.backup_dir)
        
        if args.create_emergency_script:
            script_path = rollback.create_rollback_script()
            print(f"✅ Emergency rollback script created: {script_path}")
            return 0
        
        rollback_status = rollback.rollback_all()
        
        if rollback_status.success:
            print("\n✅ Migration rollback completed successfully!")
            print(f"📊 Operations: {rollback_status.successful_operations}/{rollback_status.total_operations}")
            print(f"💾 Restored from: {rollback_status.backup_restored_from}")
        else:
            print("\n❌ Migration rollback completed with issues!")
            print(f"📊 Operations: {rollback_status.successful_operations}/{rollback_status.total_operations}")
            print(f"❌ Failed operations: {rollback_status.failed_operations}")
            
            # Show first few failed operations
            failed_ops = [op for op in rollback_status.operations if not op.success]
            for op in failed_ops[:3]:  # Show first 3 failures
                print(f"  - {op.operation_type}: {op.error_message}")
            
            if len(failed_ops) > 3:
                print(f"  - ... and {len(failed_ops) - 3} more failures")
        
        print(f"📁 Rollback data: {rollback.rollback_dir}")
        print(f"📊 Report: {rollback.rollback_dir / 'rollback_report.md'}")
        
        return 0 if rollback_status.success else 1
        
    except Exception as e:
        logger.error(f"Migration rollback failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())