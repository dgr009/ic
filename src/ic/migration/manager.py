#!/usr/bin/env python3
"""
Migration manager for IC CLI project structure refactoring.

This module provides a unified interface to manage the complete migration process
including pre-validation, post-validation, and rollback capabilities.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

# Import migration components
from .validation import PreMigrationValidator
from .post_validation import PostMigrationValidator
from .rollback import MigrationRollback

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationManager:
    """
    Unified migration manager for IC CLI project structure refactoring.
    
    This class orchestrates the complete migration process:
    1. Pre-migration validation and backup
    2. Post-migration validation and comparison
    3. Rollback capabilities if needed
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the migration manager."""
        self.project_root = project_root or Path.cwd()
        self.validation_dir = self.project_root / ".migration_validation"
        
        # Initialize components
        self.pre_validator = PreMigrationValidator(self.project_root)
        self.post_validator = PostMigrationValidator(self.project_root)
        self.rollback_manager = MigrationRollback(self.project_root)
        
        logger.info(f"Initialized MigrationManager with project root: {self.project_root}")

    def run_pre_migration_validation(self) -> Dict[str, Any]:
        """
        Run comprehensive pre-migration validation.
        
        Returns:
            Dict containing validation results
        """
        logger.info("=" * 60)
        logger.info("STARTING PRE-MIGRATION VALIDATION")
        logger.info("=" * 60)
        
        try:
            validation_data = self.pre_validator.validate_all()
            
            # Check for critical issues
            critical_issues = self._check_pre_migration_issues(validation_data)
            
            if critical_issues:
                logger.warning("Critical issues detected in pre-migration validation:")
                for issue in critical_issues:
                    logger.warning(f"  - {issue}")
                
                validation_data["critical_issues"] = critical_issues
                validation_data["ready_for_migration"] = False
            else:
                logger.info("✅ Pre-migration validation passed - ready for migration")
                validation_data["ready_for_migration"] = True
            
            return validation_data
            
        except Exception as e:
            logger.error(f"Pre-migration validation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "ready_for_migration": False
            }

    def run_post_migration_validation(self) -> Dict[str, Any]:
        """
        Run comprehensive post-migration validation.
        
        Returns:
            Dict containing validation status and results
        """
        logger.info("=" * 60)
        logger.info("STARTING POST-MIGRATION VALIDATION")
        logger.info("=" * 60)
        
        try:
            validation_status = self.post_validator.validate_all()
            
            # Convert to dict for consistency
            validation_data = {
                "success": validation_status.success,
                "total_checks": validation_status.total_checks,
                "passed_checks": validation_status.passed_checks,
                "failed_checks": validation_status.failed_checks,
                "critical_failures": validation_status.critical_failures,
                "warnings": validation_status.warnings,
                "timestamp": validation_status.timestamp
            }
            
            if validation_status.success:
                logger.info("✅ Post-migration validation passed - migration successful")
            else:
                logger.error("❌ Post-migration validation failed - migration issues detected")
                logger.error("Critical failures:")
                for failure in validation_status.critical_failures:
                    logger.error(f"  - {failure}")
            
            return validation_data
            
        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "critical_failures": [str(e)]
            }

    def run_rollback(self, backup_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Run migration rollback.
        
        Args:
            backup_dir: Optional specific backup directory to restore from
            
        Returns:
            Dict containing rollback status and results
        """
        logger.info("=" * 60)
        logger.info("STARTING MIGRATION ROLLBACK")
        logger.info("=" * 60)
        
        try:
            if backup_dir:
                rollback_manager = MigrationRollback(self.project_root, backup_dir)
            else:
                rollback_manager = self.rollback_manager
            
            rollback_status = rollback_manager.rollback_all()
            
            # Convert to dict for consistency
            rollback_data = {
                "success": rollback_status.success,
                "total_operations": rollback_status.total_operations,
                "successful_operations": rollback_status.successful_operations,
                "failed_operations": rollback_status.failed_operations,
                "backup_restored_from": rollback_status.backup_restored_from,
                "timestamp": rollback_status.timestamp
            }
            
            if rollback_status.success:
                logger.info("✅ Migration rollback completed successfully")
            else:
                logger.error("❌ Migration rollback completed with issues")
                logger.error(f"Failed operations: {rollback_status.failed_operations}")
            
            return rollback_data
            
        except Exception as e:
            logger.error(f"Migration rollback failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "failed_operations": 1
            }

    def create_emergency_rollback_script(self) -> Path:
        """
        Create emergency rollback script.
        
        Returns:
            Path to the emergency rollback script
        """
        logger.info("Creating emergency rollback script...")
        
        try:
            script_path = self.rollback_manager.create_rollback_script()
            logger.info(f"✅ Emergency rollback script created: {script_path}")
            return script_path
            
        except Exception as e:
            logger.error(f"Failed to create emergency rollback script: {e}")
            raise

    def generate_migration_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive migration summary.
        
        Returns:
            Dict containing migration summary data
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "validation_directory": str(self.validation_dir),
            "files_generated": [],
            "status": "unknown"
        }
        
        # Check for validation files
        validation_files = [
            ("pre_migration_validation.json", "Pre-migration validation data"),
            ("cli_baselines.json", "CLI command baselines"),
            ("test_baselines.json", "Test execution baselines"),
            ("config_validation.json", "Configuration validation results"),
            ("module_analysis.json", "Module structure analysis"),
            ("validation_report.md", "Pre-migration validation report")
        ]
        
        for filename, description in validation_files:
            file_path = self.validation_dir / filename
            if file_path.exists():
                summary["files_generated"].append({
                    "file": str(file_path),
                    "description": description,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
        
        # Check for post-migration files
        post_migration_dir = self.validation_dir / "post_migration"
        if post_migration_dir.exists():
            post_files = [
                ("post_migration_validation.json", "Post-migration validation data"),
                ("cli_comparison.json", "CLI output comparison results"),
                ("test_baselines.json", "Post-migration test results"),
                ("config_validation.json", "Post-migration config validation"),
                ("regression_analysis.json", "Regression analysis results"),
                ("post_migration_report.md", "Post-migration validation report")
            ]
            
            for filename, description in post_files:
                file_path = post_migration_dir / filename
                if file_path.exists():
                    summary["files_generated"].append({
                        "file": str(file_path),
                        "description": description,
                        "size": file_path.stat().st_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
        
        # Check for rollback files
        rollback_dir = self.validation_dir / "rollback"
        if rollback_dir.exists():
            rollback_files = [
                ("rollback_log.json", "Rollback operation log"),
                ("rollback_report.md", "Rollback summary report"),
                ("emergency_rollback.py", "Emergency rollback script")
            ]
            
            for filename, description in rollback_files:
                file_path = rollback_dir / filename
                if file_path.exists():
                    summary["files_generated"].append({
                        "file": str(file_path),
                        "description": description,
                        "size": file_path.stat().st_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
        
        # Determine overall status
        if post_migration_dir.exists():
            post_validation_file = post_migration_dir / "post_migration_validation.json"
            if post_validation_file.exists():
                try:
                    with open(post_validation_file, 'r') as f:
                        post_data = json.load(f)
                    
                    if post_data.get("cli_comparison", {}).get("critical_differences"):
                        summary["status"] = "migration_failed"
                    elif post_data.get("test_comparison", {}).get("critical_test_failures"):
                        summary["status"] = "migration_failed"
                    elif post_data.get("configuration_validation", {}).get("config_failures"):
                        summary["status"] = "migration_failed"
                    else:
                        summary["status"] = "migration_successful"
                except:
                    summary["status"] = "validation_incomplete"
            else:
                summary["status"] = "validation_incomplete"
        elif rollback_dir.exists():
            summary["status"] = "rollback_completed"
        else:
            summary["status"] = "pre_migration_only"
        
        return summary

    def _check_pre_migration_issues(self, validation_data: Dict[str, Any]) -> List[str]:
        """Check for critical issues in pre-migration validation."""
        issues = []
        
        # Check CLI baselines
        cli_data = validation_data.get("cli_baselines", {})
        if cli_data.get("failed_commands", 0) > 0:
            issues.append(f"CLI validation failed: {cli_data['failed_commands']} commands failed")
        
        # Check test baselines
        test_data = validation_data.get("test_baselines", {})
        if test_data.get("failed_test_suites", 0) > 0:
            issues.append(f"Test validation failed: {test_data['failed_test_suites']} test suites failed")
        
        # Check configuration validation
        config_data = validation_data.get("configuration_validation", {})
        existing_configs = config_data.get("existing_configs", 0)
        valid_configs = config_data.get("valid_configs", 0)
        if existing_configs > 0 and valid_configs < existing_configs:
            issues.append(f"Configuration validation failed: {existing_configs - valid_configs} invalid configs")
        
        # Check module analysis
        module_data = validation_data.get("module_analysis", {})
        failed_imports = module_data.get("failed_imports", 0)
        if failed_imports > 0:
            issues.append(f"Module analysis failed: {failed_imports} import failures")
        
        return issues


def main():
    """Main entry point for migration manager."""
    parser = argparse.ArgumentParser(
        description="Migration manager for IC CLI project structure refactoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run pre-migration validation
  python -m src.ic.migration.manager pre-validate
  
  # Run post-migration validation
  python -m src.ic.migration.manager post-validate
  
  # Run rollback
  python -m src.ic.migration.manager rollback
  
  # Create emergency rollback script
  python -m src.ic.migration.manager emergency-script
  
  # Generate migration summary
  python -m src.ic.migration.manager summary
        """
    )
    
    parser.add_argument("command", choices=[
        "pre-validate", "post-validate", "rollback", 
        "emergency-script", "summary"
    ], help="Migration command to execute")
    
    parser.add_argument("--project-root", type=Path, help="Project root directory")
    parser.add_argument("--backup-dir", type=Path, help="Backup directory for rollback")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", "-o", type=Path, help="Output file for results")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        manager = MigrationManager(args.project_root)
        result = None
        
        if args.command == "pre-validate":
            result = manager.run_pre_migration_validation()
            
        elif args.command == "post-validate":
            result = manager.run_post_migration_validation()
            
        elif args.command == "rollback":
            result = manager.run_rollback(args.backup_dir)
            
        elif args.command == "emergency-script":
            script_path = manager.create_emergency_rollback_script()
            result = {"emergency_script": str(script_path)}
            
        elif args.command == "summary":
            result = manager.generate_migration_summary()
        
        # Save results if output file specified
        if args.output and result:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2, default=str)
            print(f"Results saved to: {args.output}")
        
        # Print summary
        if result:
            if args.command in ["pre-validate", "post-validate", "rollback"]:
                success = result.get("success", False)
                if success:
                    print(f"\n✅ {args.command} completed successfully!")
                else:
                    print(f"\n❌ {args.command} failed!")
                    if "error" in result:
                        print(f"Error: {result['error']}")
            
            elif args.command == "emergency-script":
                print(f"\n✅ Emergency rollback script created: {result['emergency_script']}")
            
            elif args.command == "summary":
                print(f"\n📊 Migration Summary:")
                print(f"Status: {result['status']}")
                print(f"Files generated: {len(result['files_generated'])}")
                print(f"Validation directory: {result['validation_directory']}")
        
        return 0 if result and result.get("success", True) else 1
        
    except Exception as e:
        logger.error(f"Migration manager failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())