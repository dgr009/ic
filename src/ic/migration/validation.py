#!/usr/bin/env python3
"""
Pre-migration validation system for IC CLI project structure refactoring.

This module provides comprehensive validation capabilities to ensure safe migration
by capturing current state, validating configurations, and creating baselines.
"""

import os
import sys
import json
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import importlib.util
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of a validation check."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

@dataclass
class CLICommandResult:
    """Result of a CLI command execution."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timestamp: str

@dataclass
class ModuleImportResult:
    """Result of module import validation."""
    module_path: str
    success: bool
    error_message: Optional[str] = None
    functions_found: List[str] = None
    
    def __post_init__(self):
        if self.functions_found is None:
            self.functions_found = []

class PreMigrationValidator:
    """
    Comprehensive pre-migration validation system.
    
    This class provides methods to:
    1. Capture CLI command outputs for comparison
    2. Create comprehensive test execution baselines
    3. Validate configuration files and create backups
    4. Analyze current module structure and dependencies
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the validator with project root directory."""
        self.project_root = project_root or Path.cwd()
        self.validation_dir = self.project_root / ".migration_validation"
        self.backup_dir = self.project_root / "backup" / f"pre_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.results: List[ValidationResult] = []
        
        # Ensure validation directories exist
        self.validation_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized PreMigrationValidator with project root: {self.project_root}")
        logger.info(f"Validation data will be stored in: {self.validation_dir}")
        logger.info(f"Backups will be stored in: {self.backup_dir}")

    def validate_all(self) -> Dict[str, Any]:
        """
        Run all pre-migration validation checks.
        
        Returns:
            Dict containing all validation results and baseline data
        """
        logger.info("Starting comprehensive pre-migration validation...")
        
        validation_data = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "validation_results": {},
            "cli_baselines": {},
            "test_baselines": {},
            "configuration_validation": {},
            "module_analysis": {},
            "backup_info": {}
        }
        
        try:
            # 1. CLI Command Output Capture
            logger.info("Capturing CLI command outputs...")
            validation_data["cli_baselines"] = self._capture_cli_baselines()
            
            # 2. Test Execution Baseline Recording
            logger.info("Recording test execution baselines...")
            validation_data["test_baselines"] = self._record_test_baselines()
            
            # 3. Configuration File Validation and Backup
            logger.info("Validating and backing up configuration files...")
            validation_data["configuration_validation"] = self._validate_and_backup_configs()
            
            # 4. Module Structure Analysis
            logger.info("Analyzing current module structure...")
            validation_data["module_analysis"] = self._analyze_module_structure()
            
            # 5. Create Comprehensive Backup
            logger.info("Creating comprehensive backup...")
            validation_data["backup_info"] = self._create_comprehensive_backup()
            
            # Save validation data
            validation_file = self.validation_dir / "pre_migration_validation.json"
            with open(validation_file, 'w') as f:
                json.dump(validation_data, f, indent=2, default=str)
            
            logger.info(f"Pre-migration validation completed. Results saved to: {validation_file}")
            
            # Generate summary report
            self._generate_validation_report(validation_data)
            
            return validation_data
            
        except Exception as e:
            logger.error(f"Pre-migration validation failed: {e}")
            self.results.append(ValidationResult(
                success=False,
                message=f"Pre-migration validation failed: {e}",
                details={"error_type": type(e).__name__}
            ))
            raise

    def _capture_cli_baselines(self) -> Dict[str, Any]:
        """
        Capture current CLI command outputs for comparison after migration.
        
        Returns:
            Dict containing CLI command results and metadata
        """
        cli_commands = [
            # Basic help commands
            ["python", "-m", "src.ic.cli", "--help"],
            ["python", "-m", "src.ic.cli", "config", "--help"],
            ["python", "-m", "src.ic.cli", "ncp", "--help"],
            ["python", "-m", "src.ic.cli", "ncpgov", "--help"],
            
            # NCP service help commands
            ["python", "-m", "src.ic.cli", "ncp", "ec2", "--help"],
            ["python", "-m", "src.ic.cli", "ncp", "s3", "--help"],
            ["python", "-m", "src.ic.cli", "ncp", "vpc", "--help"],
            ["python", "-m", "src.ic.cli", "ncp", "sg", "--help"],
            ["python", "-m", "src.ic.cli", "ncp", "rds", "--help"],
            
            # NCPGOV service help commands
            ["python", "-m", "src.ic.cli", "ncpgov", "ec2", "--help"],
            ["python", "-m", "src.ic.cli", "ncpgov", "s3", "--help"],
            ["python", "-m", "src.ic.cli", "ncpgov", "vpc", "--help"],
            ["python", "-m", "src.ic.cli", "ncpgov", "sg", "--help"],
            ["python", "-m", "src.ic.cli", "ncpgov", "rds", "--help"],
        ]
        
        cli_results = []
        
        for cmd in cli_commands:
            try:
                start_time = datetime.now()
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                end_time = datetime.now()
                
                cli_result = CLICommandResult(
                    command=" ".join(cmd),
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    execution_time=(end_time - start_time).total_seconds(),
                    timestamp=start_time.isoformat()
                )
                
                cli_results.append(asdict(cli_result))
                logger.debug(f"Captured CLI command: {' '.join(cmd)} (exit code: {result.returncode})")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"CLI command timed out: {' '.join(cmd)}")
                cli_results.append({
                    "command": " ".join(cmd),
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Command timed out",
                    "execution_time": 30.0,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to execute CLI command {' '.join(cmd)}: {e}")
                cli_results.append({
                    "command": " ".join(cmd),
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time": 0.0,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Save CLI baselines to file
        cli_baseline_file = self.validation_dir / "cli_baselines.json"
        with open(cli_baseline_file, 'w') as f:
            json.dump(cli_results, f, indent=2)
        
        return {
            "total_commands": len(cli_commands),
            "successful_commands": len([r for r in cli_results if r["exit_code"] == 0]),
            "failed_commands": len([r for r in cli_results if r["exit_code"] != 0]),
            "results": cli_results,
            "baseline_file": str(cli_baseline_file)
        }

    def _record_test_baselines(self) -> Dict[str, Any]:
        """
        Record comprehensive test execution baselines.
        
        Returns:
            Dict containing test execution results and metadata
        """
        test_commands = [
            # Platform-specific tests
            ["python", "-m", "pytest", "tests/platforms/ncp/", "-v", "--tb=short", "--no-header"],
            ["python", "-m", "pytest", "tests/platforms/ncpgov/", "-v", "--tb=short", "--no-header"],
            
            # Unit tests
            ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short", "--no-header"],
            
            # Integration tests
            ["python", "-m", "pytest", "tests/integration/", "-v", "--tb=short", "--no-header"],
            
            # Configuration tests
            ["python", "-m", "pytest", "tests/test_config.py", "-v", "--tb=short", "--no-header"],
            
            # CI tests
            ["python", "-m", "pytest", "tests/ci/", "-v", "--tb=short", "--no-header"],
        ]
        
        test_results = []
        
        for cmd in test_commands:
            try:
                start_time = datetime.now()
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes timeout for tests
                )
                end_time = datetime.now()
                
                test_result = {
                    "command": " ".join(cmd),
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_time": (end_time - start_time).total_seconds(),
                    "timestamp": start_time.isoformat(),
                    "test_summary": self._parse_pytest_output(result.stdout)
                }
                
                test_results.append(test_result)
                logger.debug(f"Recorded test baseline: {' '.join(cmd)} (exit code: {result.returncode})")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"Test command timed out: {' '.join(cmd)}")
                test_results.append({
                    "command": " ".join(cmd),
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Test execution timed out",
                    "execution_time": 300.0,
                    "timestamp": datetime.now().isoformat(),
                    "test_summary": {"status": "timeout"}
                })
            except Exception as e:
                logger.error(f"Failed to execute test command {' '.join(cmd)}: {e}")
                test_results.append({
                    "command": " ".join(cmd),
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "test_summary": {"status": "error", "error": str(e)}
                })
        
        # Save test baselines to file
        test_baseline_file = self.validation_dir / "test_baselines.json"
        with open(test_baseline_file, 'w') as f:
            json.dump(test_results, f, indent=2)
        
        return {
            "total_test_suites": len(test_commands),
            "successful_test_suites": len([r for r in test_results if r["exit_code"] == 0]),
            "failed_test_suites": len([r for r in test_results if r["exit_code"] != 0]),
            "results": test_results,
            "baseline_file": str(test_baseline_file)
        }

    def _parse_pytest_output(self, output: str) -> Dict[str, Any]:
        """Parse pytest output to extract test summary information."""
        summary = {"status": "unknown"}
        
        try:
            lines = output.split('\n')
            for line in lines:
                if "passed" in line or "failed" in line or "error" in line:
                    # Look for pytest summary line
                    if "passed" in line and ("failed" in line or "error" in line):
                        summary["status"] = "mixed"
                    elif "passed" in line:
                        summary["status"] = "passed"
                    elif "failed" in line or "error" in line:
                        summary["status"] = "failed"
                    
                    # Extract numbers
                    import re
                    numbers = re.findall(r'(\d+) (passed|failed|error)', line)
                    for count, status in numbers:
                        summary[status] = int(count)
                    break
        except Exception as e:
            logger.debug(f"Failed to parse pytest output: {e}")
            summary["parse_error"] = str(e)
        
        return summary

    def _validate_and_backup_configs(self) -> Dict[str, Any]:
        """
        Validate configuration files and create backups.
        
        Returns:
            Dict containing configuration validation results and backup info
        """
        config_paths = [
            # IC configuration files
            self.project_root / ".ic" / "config",
            Path.home() / ".ic" / "config",
            
            # NCP configuration files
            self.project_root / ".ncp",
            Path.home() / ".ncp",
            
            # NCPGOV configuration files
            self.project_root / ".ncpgov",
            Path.home() / ".ncpgov",
            
            # Environment files
            self.project_root / ".env",
            
            # Project configuration files
            self.project_root / "pyproject.toml",
            self.project_root / "requirements.txt",
            self.project_root / "setup.py",
        ]
        
        validation_results = []
        backup_info = []
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    # Validate configuration
                    validation_result = self._validate_config_file(config_path)
                    validation_results.append(validation_result)
                    
                    # Create backup
                    backup_result = self._backup_config_file(config_path)
                    backup_info.append(backup_result)
                    
                    logger.debug(f"Validated and backed up: {config_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to validate/backup config {config_path}: {e}")
                    validation_results.append({
                        "path": str(config_path),
                        "exists": True,
                        "valid": False,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
            else:
                validation_results.append({
                    "path": str(config_path),
                    "exists": False,
                    "valid": None,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Save configuration validation results
        config_validation_file = self.validation_dir / "config_validation.json"
        with open(config_validation_file, 'w') as f:
            json.dump({
                "validation_results": validation_results,
                "backup_info": backup_info
            }, f, indent=2, default=str)
        
        return {
            "total_configs_checked": len(config_paths),
            "existing_configs": len([r for r in validation_results if r["exists"]]),
            "valid_configs": len([r for r in validation_results if r.get("valid", False)]),
            "validation_results": validation_results,
            "backup_info": backup_info,
            "validation_file": str(config_validation_file)
        }

    def _validate_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Validate a single configuration file."""
        result = {
            "path": str(config_path),
            "exists": config_path.exists(),
            "valid": False,
            "timestamp": datetime.now().isoformat()
        }
        
        if not config_path.exists():
            return result
        
        try:
            if config_path.is_file():
                # Check file permissions
                result["readable"] = os.access(config_path, os.R_OK)
                result["size"] = config_path.stat().st_size
                
                # Calculate file hash for integrity checking
                with open(config_path, 'rb') as f:
                    result["sha256"] = hashlib.sha256(f.read()).hexdigest()
                
                # Validate file format based on extension
                if config_path.suffix in ['.yaml', '.yml']:
                    result.update(self._validate_yaml_file(config_path))
                elif config_path.suffix == '.json':
                    result.update(self._validate_json_file(config_path))
                elif config_path.suffix == '.toml':
                    result.update(self._validate_toml_file(config_path))
                elif config_path.name == '.env':
                    result.update(self._validate_env_file(config_path))
                else:
                    result["valid"] = True  # Assume valid for unknown formats
                    result["format"] = "unknown"
            
            elif config_path.is_dir():
                # Validate directory structure
                result["type"] = "directory"
                result["files"] = [str(f.relative_to(config_path)) for f in config_path.rglob('*') if f.is_file()]
                result["valid"] = True
        
        except Exception as e:
            result["error"] = str(e)
            result["valid"] = False
        
        return result

    def _validate_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Validate YAML configuration file."""
        try:
            import yaml
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            return {"valid": True, "format": "yaml", "keys": list(data.keys()) if isinstance(data, dict) else None}
        except Exception as e:
            return {"valid": False, "format": "yaml", "error": str(e)}

    def _validate_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Validate JSON configuration file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return {"valid": True, "format": "json", "keys": list(data.keys()) if isinstance(data, dict) else None}
        except Exception as e:
            return {"valid": False, "format": "json", "error": str(e)}

    def _validate_toml_file(self, file_path: Path) -> Dict[str, Any]:
        """Validate TOML configuration file."""
        try:
            import tomli
            with open(file_path, 'rb') as f:
                data = tomli.load(f)
            return {"valid": True, "format": "toml", "keys": list(data.keys()) if isinstance(data, dict) else None}
        except Exception as e:
            return {"valid": False, "format": "toml", "error": str(e)}

    def _validate_env_file(self, file_path: Path) -> Dict[str, Any]:
        """Validate .env file."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            env_vars = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, _ = line.split('=', 1)
                        env_vars.append(key.strip())
            
            return {"valid": True, "format": "env", "variables": env_vars, "line_count": len(lines)}
        except Exception as e:
            return {"valid": False, "format": "env", "error": str(e)}

    def _backup_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Create backup of configuration file or directory."""
        try:
            relative_path = config_path.relative_to(self.project_root) if config_path.is_relative_to(self.project_root) else config_path.relative_to(Path.home())
            backup_path = self.backup_dir / "configs" / relative_path
            
            # Ensure backup directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            if config_path.is_file():
                shutil.copy2(config_path, backup_path)
            elif config_path.is_dir():
                shutil.copytree(config_path, backup_path, dirs_exist_ok=True)
            
            return {
                "source": str(config_path),
                "backup": str(backup_path),
                "success": True,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            return {
                "source": str(config_path),
                "backup": None,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _analyze_module_structure(self) -> Dict[str, Any]:
        """
        Analyze current module structure and import dependencies.
        
        Returns:
            Dict containing module analysis results
        """
        modules_to_analyze = [
            # Current NCP modules
            "ncp.ec2.info",
            "ncp.s3.info", 
            "ncp.vpc.info",
            "ncp.sg.info",
            "ncp_module.rds.info",
            "ncp_module.client",
            
            # Current NCPGOV modules
            "ncpgov.ec2.info",
            "ncpgov.s3.info",
            "ncpgov.vpc.info", 
            "ncpgov.sg.info",
            "ncpgov_module.rds.info",
            "ncpgov_module.client",
            
            # New unified modules (if they exist)
            "src.ic.platforms.ncp.ec2.info",
            "src.ic.platforms.ncp.s3.info",
            "src.ic.platforms.ncp.vpc.info",
            "src.ic.platforms.ncp.sg.info",
            "src.ic.platforms.ncp.rds.info",
            "src.ic.platforms.ncp.client",
            
            "src.ic.platforms.ncpgov.ec2.info",
            "src.ic.platforms.ncpgov.s3.info",
            "src.ic.platforms.ncpgov.vpc.info",
            "src.ic.platforms.ncpgov.sg.info",
            "src.ic.platforms.ncpgov.rds.info",
            "src.ic.platforms.ncpgov.client",
        ]
        
        module_analysis = []
        
        for module_path in modules_to_analyze:
            try:
                result = self._analyze_single_module(module_path)
                module_analysis.append(result)
                logger.debug(f"Analyzed module: {module_path}")
            except Exception as e:
                logger.error(f"Failed to analyze module {module_path}: {e}")
                module_analysis.append(ModuleImportResult(
                    module_path=module_path,
                    success=False,
                    error_message=str(e)
                ))
        
        # Save module analysis results
        module_analysis_file = self.validation_dir / "module_analysis.json"
        with open(module_analysis_file, 'w') as f:
            json.dump([asdict(result) for result in module_analysis], f, indent=2)
        
        return {
            "total_modules_analyzed": len(modules_to_analyze),
            "successful_imports": len([r for r in module_analysis if r.success]),
            "failed_imports": len([r for r in module_analysis if not r.success]),
            "analysis_results": [asdict(result) for result in module_analysis],
            "analysis_file": str(module_analysis_file)
        }

    def _analyze_single_module(self, module_path: str) -> ModuleImportResult:
        """Analyze a single module for import validation."""
        try:
            # Try to import the module
            module = importlib.import_module(module_path)
            
            # Get list of functions and classes
            functions_found = []
            for attr_name in dir(module):
                if not attr_name.startswith('_'):
                    attr = getattr(module, attr_name)
                    if callable(attr):
                        functions_found.append(attr_name)
            
            return ModuleImportResult(
                module_path=module_path,
                success=True,
                functions_found=functions_found
            )
            
        except ImportError as e:
            return ModuleImportResult(
                module_path=module_path,
                success=False,
                error_message=f"ImportError: {e}"
            )
        except Exception as e:
            return ModuleImportResult(
                module_path=module_path,
                success=False,
                error_message=f"Unexpected error: {e}"
            )

    def _create_comprehensive_backup(self) -> Dict[str, Any]:
        """
        Create comprehensive backup of current project state.
        
        Returns:
            Dict containing backup information
        """
        backup_items = [
            # Module directories
            ("ncp", self.project_root / "ncp"),
            ("ncp_module", self.project_root / "ncp_module"),
            ("ncpgov", self.project_root / "ncpgov"),
            ("ncpgov_module", self.project_root / "ncpgov_module"),
            
            # Unified modules (if they exist)
            ("src_ic_platforms", self.project_root / "src" / "ic" / "platforms"),
            
            # Test directories
            ("tests", self.project_root / "tests"),
            
            # CLI file
            ("cli", self.project_root / "src" / "ic" / "cli.py"),
            
            # Configuration files
            ("project_configs", self.project_root / ".ic"),
        ]
        
        backup_results = []
        
        for item_name, source_path in backup_items:
            if source_path.exists():
                try:
                    backup_path = self.backup_dir / "modules" / item_name
                    
                    if source_path.is_file():
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, backup_path)
                    elif source_path.is_dir():
                        shutil.copytree(source_path, backup_path, dirs_exist_ok=True)
                    
                    backup_results.append({
                        "item": item_name,
                        "source": str(source_path),
                        "backup": str(backup_path),
                        "success": True,
                        "size": self._get_directory_size(backup_path) if backup_path.exists() else 0
                    })
                    
                    logger.debug(f"Backed up {item_name}: {source_path} -> {backup_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to backup {item_name}: {e}")
                    backup_results.append({
                        "item": item_name,
                        "source": str(source_path),
                        "backup": None,
                        "success": False,
                        "error": str(e)
                    })
            else:
                backup_results.append({
                    "item": item_name,
                    "source": str(source_path),
                    "backup": None,
                    "success": False,
                    "error": "Source path does not exist"
                })
        
        # Create backup manifest
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "backup_directory": str(self.backup_dir),
            "backup_items": backup_results,
            "total_size": sum(item.get("size", 0) for item in backup_results)
        }
        
        manifest_file = self.backup_dir / "backup_manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)
        
        return manifest

    def _get_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes."""
        total_size = 0
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.debug(f"Failed to calculate size for {directory}: {e}")
        return total_size

    def _generate_validation_report(self, validation_data: Dict[str, Any]) -> None:
        """Generate human-readable validation report."""
        report_file = self.validation_dir / "validation_report.md"
        
        with open(report_file, 'w') as f:
            f.write("# Pre-Migration Validation Report\n\n")
            f.write(f"**Generated:** {validation_data['timestamp']}\n")
            f.write(f"**Project Root:** {validation_data['project_root']}\n\n")
            
            # CLI Baselines Summary
            cli_data = validation_data.get('cli_baselines', {})
            f.write("## CLI Command Baselines\n\n")
            f.write(f"- **Total Commands:** {cli_data.get('total_commands', 0)}\n")
            f.write(f"- **Successful:** {cli_data.get('successful_commands', 0)}\n")
            f.write(f"- **Failed:** {cli_data.get('failed_commands', 0)}\n\n")
            
            # Test Baselines Summary
            test_data = validation_data.get('test_baselines', {})
            f.write("## Test Execution Baselines\n\n")
            f.write(f"- **Total Test Suites:** {test_data.get('total_test_suites', 0)}\n")
            f.write(f"- **Successful:** {test_data.get('successful_test_suites', 0)}\n")
            f.write(f"- **Failed:** {test_data.get('failed_test_suites', 0)}\n\n")
            
            # Configuration Validation Summary
            config_data = validation_data.get('configuration_validation', {})
            f.write("## Configuration Validation\n\n")
            f.write(f"- **Total Configs Checked:** {config_data.get('total_configs_checked', 0)}\n")
            f.write(f"- **Existing Configs:** {config_data.get('existing_configs', 0)}\n")
            f.write(f"- **Valid Configs:** {config_data.get('valid_configs', 0)}\n\n")
            
            # Module Analysis Summary
            module_data = validation_data.get('module_analysis', {})
            f.write("## Module Structure Analysis\n\n")
            f.write(f"- **Total Modules Analyzed:** {module_data.get('total_modules_analyzed', 0)}\n")
            f.write(f"- **Successful Imports:** {module_data.get('successful_imports', 0)}\n")
            f.write(f"- **Failed Imports:** {module_data.get('failed_imports', 0)}\n\n")
            
            # Backup Information
            backup_data = validation_data.get('backup_info', {})
            f.write("## Backup Information\n\n")
            f.write(f"- **Backup Directory:** {backup_data.get('backup_directory', 'N/A')}\n")
            f.write(f"- **Total Backup Size:** {backup_data.get('total_size', 0):,} bytes\n")
            f.write(f"- **Backup Items:** {len(backup_data.get('backup_items', []))}\n\n")
            
            f.write("## Files Generated\n\n")
            f.write(f"- CLI Baselines: `{cli_data.get('baseline_file', 'N/A')}`\n")
            f.write(f"- Test Baselines: `{test_data.get('baseline_file', 'N/A')}`\n")
            f.write(f"- Config Validation: `{config_data.get('validation_file', 'N/A')}`\n")
            f.write(f"- Module Analysis: `{module_data.get('analysis_file', 'N/A')}`\n")
            f.write(f"- Backup Manifest: `{backup_data.get('backup_directory', 'N/A')}/backup_manifest.json`\n\n")
            
            f.write("## Next Steps\n\n")
            f.write("1. Review validation results for any critical issues\n")
            f.write("2. Ensure all CLI commands are working as expected\n")
            f.write("3. Verify test baselines are comprehensive\n")
            f.write("4. Confirm configuration backups are complete\n")
            f.write("5. Proceed with migration using post-migration validation\n")
        
        logger.info(f"Validation report generated: {report_file}")


def main():
    """Main entry point for pre-migration validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pre-migration validation system for IC CLI")
    parser.add_argument("--project-root", type=Path, help="Project root directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        validator = PreMigrationValidator(args.project_root)
        validation_data = validator.validate_all()
        
        print("\n✅ Pre-migration validation completed successfully!")
        print(f"📁 Validation data: {validator.validation_dir}")
        print(f"💾 Backup location: {validator.backup_dir}")
        print(f"📊 Report: {validator.validation_dir / 'validation_report.md'}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Pre-migration validation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())