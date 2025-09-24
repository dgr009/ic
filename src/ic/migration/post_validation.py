#!/usr/bin/env python3
"""
Post-migration validation system for IC CLI project structure refactoring.

This module provides comprehensive validation capabilities to ensure migration
was successful by comparing outputs, running tests, and validating configurations.
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import difflib
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ComparisonResult:
    """Result of comparing pre and post migration data."""
    item_type: str
    item_name: str
    matches: bool
    differences: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.differences is None:
            self.differences = []

@dataclass
class ValidationStatus:
    """Overall validation status."""
    success: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    critical_failures: List[str]
    warnings: List[str]
    timestamp: str

class PostMigrationValidator:
    """
    Comprehensive post-migration validation system.
    
    This class provides methods to:
    1. Compare CLI command outputs with pre-migration baselines
    2. Execute comprehensive test suites to verify no regressions
    3. Validate configuration loading for all platforms
    4. Generate detailed comparison reports
    """
    
    def __init__(self, project_root: Optional[Path] = None, pre_validation_dir: Optional[Path] = None):
        """Initialize the post-migration validator."""
        self.project_root = project_root or Path.cwd()
        self.validation_dir = self.project_root / ".migration_validation"
        self.pre_validation_dir = pre_validation_dir or self.validation_dir
        self.post_validation_dir = self.validation_dir / "post_migration"
        self.comparison_results: List[ComparisonResult] = []
        
        # Ensure validation directories exist
        self.post_validation_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized PostMigrationValidator with project root: {self.project_root}")
        logger.info(f"Pre-migration data: {self.pre_validation_dir}")
        logger.info(f"Post-migration data: {self.post_validation_dir}")

    def validate_all(self) -> ValidationStatus:
        """
        Run all post-migration validation checks.
        
        Returns:
            ValidationStatus with overall results
        """
        logger.info("Starting comprehensive post-migration validation...")
        
        validation_data = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "cli_comparison": {},
            "test_comparison": {},
            "configuration_validation": {},
            "regression_analysis": {}
        }
        
        critical_failures = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        
        try:
            # 1. CLI Command Output Comparison
            logger.info("Comparing CLI command outputs...")
            cli_result = self._compare_cli_outputs()
            validation_data["cli_comparison"] = cli_result
            total_checks += cli_result.get("total_comparisons", 0)
            passed_checks += cli_result.get("matching_outputs", 0)
            
            if cli_result.get("critical_differences"):
                critical_failures.extend(cli_result["critical_differences"])
            if cli_result.get("warnings"):
                warnings.extend(cli_result["warnings"])
            
            # 2. Comprehensive Test Suite Execution
            logger.info("Executing comprehensive test suite...")
            test_result = self._execute_comprehensive_tests()
            validation_data["test_comparison"] = test_result
            total_checks += test_result.get("total_test_suites", 0)
            passed_checks += test_result.get("successful_test_suites", 0)
            
            if test_result.get("critical_test_failures"):
                critical_failures.extend(test_result["critical_test_failures"])
            if test_result.get("test_warnings"):
                warnings.extend(test_result["test_warnings"])
            
            # 3. Configuration Loading Validation
            logger.info("Validating configuration loading...")
            config_result = self._validate_configuration_loading()
            validation_data["configuration_validation"] = config_result
            total_checks += config_result.get("total_configs", 0)
            passed_checks += config_result.get("successful_configs", 0)
            
            if config_result.get("config_failures"):
                critical_failures.extend(config_result["config_failures"])
            
            # 4. Regression Analysis
            logger.info("Performing regression analysis...")
            regression_result = self._perform_regression_analysis()
            validation_data["regression_analysis"] = regression_result
            
            if regression_result.get("regressions"):
                critical_failures.extend(regression_result["regressions"])
            
            # Save validation data
            validation_file = self.post_validation_dir / "post_migration_validation.json"
            with open(validation_file, 'w') as f:
                json.dump(validation_data, f, indent=2, default=str)
            
            # Generate comparison report
            self._generate_comparison_report(validation_data)
            
            # Create validation status
            validation_status = ValidationStatus(
                success=len(critical_failures) == 0,
                total_checks=total_checks,
                passed_checks=passed_checks,
                failed_checks=total_checks - passed_checks,
                critical_failures=critical_failures,
                warnings=warnings,
                timestamp=datetime.now().isoformat()
            )
            
            logger.info(f"Post-migration validation completed. Results saved to: {validation_file}")
            
            return validation_status
            
        except Exception as e:
            logger.error(f"Post-migration validation failed: {e}")
            return ValidationStatus(
                success=False,
                total_checks=total_checks,
                passed_checks=passed_checks,
                failed_checks=total_checks - passed_checks + 1,
                critical_failures=critical_failures + [f"Validation system error: {e}"],
                warnings=warnings,
                timestamp=datetime.now().isoformat()
            )

    def _compare_cli_outputs(self) -> Dict[str, Any]:
        """
        Compare CLI command outputs with pre-migration baselines.
        
        Returns:
            Dict containing comparison results
        """
        # Load pre-migration CLI baselines
        pre_baseline_file = self.pre_validation_dir / "cli_baselines.json"
        if not pre_baseline_file.exists():
            logger.error(f"Pre-migration CLI baselines not found: {pre_baseline_file}")
            return {
                "error": "Pre-migration baselines not found",
                "total_comparisons": 0,
                "matching_outputs": 0,
                "critical_differences": ["Pre-migration CLI baselines not found"]
            }
        
        with open(pre_baseline_file, 'r') as f:
            pre_baselines = json.load(f)
        
        # Execute same CLI commands and compare
        post_results = []
        comparison_results = []
        critical_differences = []
        warnings = []
        
        for pre_result in pre_baselines:
            command = pre_result["command"]
            
            try:
                # Execute the same command
                cmd_parts = command.split()
                start_time = datetime.now()
                result = subprocess.run(
                    cmd_parts,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                end_time = datetime.now()
                
                post_result = {
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_time": (end_time - start_time).total_seconds(),
                    "timestamp": start_time.isoformat()
                }
                
                post_results.append(post_result)
                
                # Compare results
                comparison = self._compare_cli_result(pre_result, post_result)
                comparison_results.append(comparison)
                
                if not comparison.matches:
                    if comparison.item_name in ["help", "version"]:
                        # Help and version differences are usually not critical
                        warnings.append(f"Non-critical difference in {command}: {', '.join(comparison.differences)}")
                    else:
                        critical_differences.append(f"Critical difference in {command}: {', '.join(comparison.differences)}")
                
                logger.debug(f"Compared CLI command: {command} (match: {comparison.matches})")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"CLI command timed out: {command}")
                post_results.append({
                    "command": command,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Command timed out",
                    "execution_time": 30.0,
                    "timestamp": datetime.now().isoformat()
                })
                critical_differences.append(f"Command timeout: {command}")
                
            except Exception as e:
                logger.error(f"Failed to execute CLI command {command}: {e}")
                post_results.append({
                    "command": command,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time": 0.0,
                    "timestamp": datetime.now().isoformat()
                })
                critical_differences.append(f"Command execution error: {command} - {e}")
        
        # Save post-migration CLI results
        post_baseline_file = self.post_validation_dir / "cli_baselines.json"
        with open(post_baseline_file, 'w') as f:
            json.dump(post_results, f, indent=2)
        
        # Save comparison results
        comparison_file = self.post_validation_dir / "cli_comparison.json"
        with open(comparison_file, 'w') as f:
            json.dump([asdict(comp) for comp in comparison_results], f, indent=2)
        
        return {
            "total_comparisons": len(comparison_results),
            "matching_outputs": len([c for c in comparison_results if c.matches]),
            "different_outputs": len([c for c in comparison_results if not c.matches]),
            "critical_differences": critical_differences,
            "warnings": warnings,
            "comparison_results": [asdict(comp) for comp in comparison_results],
            "post_baseline_file": str(post_baseline_file),
            "comparison_file": str(comparison_file)
        }

    def _compare_cli_result(self, pre_result: Dict[str, Any], post_result: Dict[str, Any]) -> ComparisonResult:
        """Compare individual CLI command results."""
        differences = []
        
        # Compare exit codes
        if pre_result["exit_code"] != post_result["exit_code"]:
            differences.append(f"Exit code changed: {pre_result['exit_code']} -> {post_result['exit_code']}")
        
        # Compare stdout (with some tolerance for timestamps and dynamic content)
        if not self._outputs_match(pre_result["stdout"], post_result["stdout"]):
            differences.append("Standard output differs")
        
        # Compare stderr (with some tolerance)
        if not self._outputs_match(pre_result["stderr"], post_result["stderr"]):
            differences.append("Standard error differs")
        
        # Determine command type for classification
        command_parts = pre_result["command"].split()
        command_type = "help" if "--help" in command_parts else "command"
        
        return ComparisonResult(
            item_type="cli_command",
            item_name=command_type,
            matches=len(differences) == 0,
            differences=differences,
            details={
                "command": pre_result["command"],
                "pre_exit_code": pre_result["exit_code"],
                "post_exit_code": post_result["exit_code"]
            }
        )

    def _outputs_match(self, pre_output: str, post_output: str) -> bool:
        """
        Compare outputs with tolerance for expected differences.
        
        This method allows for minor differences that are expected after migration,
        such as timestamps, file paths, or version numbers.
        """
        # If outputs are identical, they match
        if pre_output == post_output:
            return True
        
        # Normalize outputs for comparison
        pre_normalized = self._normalize_output(pre_output)
        post_normalized = self._normalize_output(post_output)
        
        # Calculate similarity ratio
        similarity = difflib.SequenceMatcher(None, pre_normalized, post_normalized).ratio()
        
        # Consider outputs matching if they're 95% similar
        # This allows for minor differences in timestamps, paths, etc.
        return similarity >= 0.95

    def _normalize_output(self, output: str) -> str:
        """Normalize output for comparison by removing dynamic content."""
        import re
        
        # Remove timestamps
        output = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '[TIMESTAMP]', output)
        
        # Remove file paths that might differ
        output = re.sub(r'/[^\s]+\.py', '[FILEPATH]', output)
        
        # Remove execution times
        output = re.sub(r'\d+\.\d+s', '[TIME]', output)
        
        # Remove memory addresses
        output = re.sub(r'0x[0-9a-fA-F]+', '[MEMORY]', output)
        
        # Normalize whitespace
        output = re.sub(r'\s+', ' ', output.strip())
        
        return output

    def _execute_comprehensive_tests(self) -> Dict[str, Any]:
        """
        Execute comprehensive test suite and compare with baselines.
        
        Returns:
            Dict containing test execution results
        """
        # Load pre-migration test baselines
        pre_baseline_file = self.pre_validation_dir / "test_baselines.json"
        pre_baselines = []
        
        if pre_baseline_file.exists():
            with open(pre_baseline_file, 'r') as f:
                pre_baselines = json.load(f)
        
        # Define comprehensive test commands
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
            
            # Migration-specific tests
            ["python", "-m", "pytest", "tests/", "-k", "migration", "-v", "--tb=short", "--no-header"],
        ]
        
        post_test_results = []
        critical_test_failures = []
        test_warnings = []
        
        for cmd in test_commands:
            try:
                start_time = datetime.now()
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes timeout
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
                
                post_test_results.append(test_result)
                
                # Check for test failures
                if result.returncode != 0:
                    if "tests/platforms/ncp" in " ".join(cmd) or "tests/platforms/ncpgov" in " ".join(cmd):
                        critical_test_failures.append(f"Critical platform tests failed: {' '.join(cmd)}")
                    else:
                        test_warnings.append(f"Test suite failed: {' '.join(cmd)}")
                
                # Compare with pre-migration if available
                pre_result = next((r for r in pre_baselines if r["command"] == " ".join(cmd)), None)
                if pre_result:
                    if pre_result["exit_code"] == 0 and result.returncode != 0:
                        critical_test_failures.append(f"Test regression detected: {' '.join(cmd)}")
                    elif pre_result["exit_code"] != 0 and result.returncode == 0:
                        test_warnings.append(f"Test improvement detected: {' '.join(cmd)}")
                
                logger.debug(f"Executed test suite: {' '.join(cmd)} (exit code: {result.returncode})")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"Test command timed out: {' '.join(cmd)}")
                post_test_results.append({
                    "command": " ".join(cmd),
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Test execution timed out",
                    "execution_time": 300.0,
                    "timestamp": datetime.now().isoformat(),
                    "test_summary": {"status": "timeout"}
                })
                critical_test_failures.append(f"Test timeout: {' '.join(cmd)}")
                
            except Exception as e:
                logger.error(f"Failed to execute test command {' '.join(cmd)}: {e}")
                post_test_results.append({
                    "command": " ".join(cmd),
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time": 0.0,
                    "timestamp": datetime.now().isoformat(),
                    "test_summary": {"status": "error", "error": str(e)}
                })
                critical_test_failures.append(f"Test execution error: {' '.join(cmd)} - {e}")
        
        # Save post-migration test results
        post_test_file = self.post_validation_dir / "test_baselines.json"
        with open(post_test_file, 'w') as f:
            json.dump(post_test_results, f, indent=2)
        
        return {
            "total_test_suites": len(test_commands),
            "successful_test_suites": len([r for r in post_test_results if r["exit_code"] == 0]),
            "failed_test_suites": len([r for r in post_test_results if r["exit_code"] != 0]),
            "critical_test_failures": critical_test_failures,
            "test_warnings": test_warnings,
            "test_results": post_test_results,
            "test_file": str(post_test_file)
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

    def _validate_configuration_loading(self) -> Dict[str, Any]:
        """
        Validate configuration loading for all platforms.
        
        Returns:
            Dict containing configuration validation results
        """
        config_tests = [
            # Test NCP configuration loading
            {
                "name": "NCP Config Loading",
                "test_code": """
try:
    from src.ic.platforms.ncp.client import NCPClient
    client = NCPClient()
    result = {"success": True, "message": "NCP client initialized successfully"}
except Exception as e:
    result = {"success": False, "message": f"NCP client initialization failed: {e}"}
print(result)
"""
            },
            
            # Test NCPGOV configuration loading
            {
                "name": "NCPGOV Config Loading",
                "test_code": """
try:
    from src.ic.platforms.ncpgov.client import NCPGovClient
    client = NCPGovClient()
    result = {"success": True, "message": "NCPGOV client initialized successfully"}
except Exception as e:
    result = {"success": False, "message": f"NCPGOV client initialization failed: {e}"}
print(result)
"""
            },
            
            # Test module imports
            {
                "name": "NCP Module Imports",
                "test_code": """
try:
    from src.ic.platforms.ncp.ec2 import info as ncp_ec2_info
    from src.ic.platforms.ncp.s3 import info as ncp_s3_info
    from src.ic.platforms.ncp.vpc import info as ncp_vpc_info
    from src.ic.platforms.ncp.sg import info as ncp_sg_info
    from src.ic.platforms.ncp.rds import info as ncp_rds_info
    result = {"success": True, "message": "All NCP modules imported successfully"}
except Exception as e:
    result = {"success": False, "message": f"NCP module import failed: {e}"}
print(result)
"""
            },
            
            # Test NCPGOV module imports
            {
                "name": "NCPGOV Module Imports",
                "test_code": """
try:
    from src.ic.platforms.ncpgov.ec2 import info as ncpgov_ec2_info
    from src.ic.platforms.ncpgov.s3 import info as ncpgov_s3_info
    from src.ic.platforms.ncpgov.vpc import info as ncpgov_vpc_info
    from src.ic.platforms.ncpgov.sg import info as ncpgov_sg_info
    from src.ic.platforms.ncpgov.rds import info as ncpgov_rds_info
    result = {"success": True, "message": "All NCPGOV modules imported successfully"}
except Exception as e:
    result = {"success": False, "message": f"NCPGOV module import failed: {e}"}
print(result)
"""
            }
        ]
        
        config_results = []
        config_failures = []
        
        for test in config_tests:
            try:
                # Create temporary Python script
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test["test_code"])
                    temp_script = f.name
                
                # Execute the test
                result = subprocess.run(
                    ["python", temp_script],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Parse result
                try:
                    import ast
                    test_result = ast.literal_eval(result.stdout.strip())
                except:
                    test_result = {
                        "success": result.returncode == 0,
                        "message": result.stdout or result.stderr
                    }
                
                config_results.append({
                    "name": test["name"],
                    "success": test_result.get("success", False),
                    "message": test_result.get("message", "Unknown result"),
                    "exit_code": result.returncode,
                    "timestamp": datetime.now().isoformat()
                })
                
                if not test_result.get("success", False):
                    config_failures.append(f"{test['name']}: {test_result.get('message', 'Unknown error')}")
                
                # Clean up temporary file
                os.unlink(temp_script)
                
                logger.debug(f"Configuration test completed: {test['name']} (success: {test_result.get('success', False)})")
                
            except Exception as e:
                logger.error(f"Configuration test failed: {test['name']} - {e}")
                config_results.append({
                    "name": test["name"],
                    "success": False,
                    "message": str(e),
                    "exit_code": -1,
                    "timestamp": datetime.now().isoformat()
                })
                config_failures.append(f"{test['name']}: {e}")
        
        # Save configuration validation results
        config_validation_file = self.post_validation_dir / "config_validation.json"
        with open(config_validation_file, 'w') as f:
            json.dump(config_results, f, indent=2)
        
        return {
            "total_configs": len(config_tests),
            "successful_configs": len([r for r in config_results if r["success"]]),
            "failed_configs": len([r for r in config_results if not r["success"]]),
            "config_failures": config_failures,
            "config_results": config_results,
            "validation_file": str(config_validation_file)
        }

    def _perform_regression_analysis(self) -> Dict[str, Any]:
        """
        Perform regression analysis by comparing key functionality.
        
        Returns:
            Dict containing regression analysis results
        """
        regression_tests = [
            # Test that old import paths no longer work (expected)
            {
                "name": "Old NCP Import Paths Removed",
                "expected_failure": True,
                "test_code": """
try:
    from ncp.ec2 import info
    result = {"success": True, "message": "Old import still works (unexpected)"}
except ImportError:
    result = {"success": True, "message": "Old import correctly removed"}
except Exception as e:
    result = {"success": False, "message": f"Unexpected error: {e}"}
print(result)
"""
            },
            
            # Test that new import paths work
            {
                "name": "New NCP Import Paths Work",
                "expected_failure": False,
                "test_code": """
try:
    from src.ic.platforms.ncp.ec2 import info
    result = {"success": True, "message": "New import paths work correctly"}
except Exception as e:
    result = {"success": False, "message": f"New import failed: {e}"}
print(result)
"""
            },
            
            # Test CLI functionality preservation
            {
                "name": "CLI Help Functionality",
                "expected_failure": False,
                "test_code": """
import subprocess
try:
    result = subprocess.run(["python", "-m", "src.ic.cli", "--help"], 
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0 and "usage:" in result.stdout.lower():
        result = {"success": True, "message": "CLI help works correctly"}
    else:
        result = {"success": False, "message": f"CLI help failed: {result.stderr}"}
except Exception as e:
    result = {"success": False, "message": f"CLI test failed: {e}"}
print(result)
"""
            }
        ]
        
        regression_results = []
        regressions = []
        
        for test in regression_tests:
            try:
                # Create temporary Python script
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test["test_code"])
                    temp_script = f.name
                
                # Execute the test
                result = subprocess.run(
                    ["python", temp_script],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                # Parse result
                try:
                    import ast
                    test_result = ast.literal_eval(result.stdout.strip())
                except:
                    test_result = {
                        "success": result.returncode == 0,
                        "message": result.stdout or result.stderr
                    }
                
                # Evaluate based on expected outcome
                actual_success = test_result.get("success", False)
                expected_success = not test.get("expected_failure", False)
                
                regression_detected = actual_success != expected_success
                
                regression_results.append({
                    "name": test["name"],
                    "success": actual_success,
                    "expected_failure": test.get("expected_failure", False),
                    "regression_detected": regression_detected,
                    "message": test_result.get("message", "Unknown result"),
                    "timestamp": datetime.now().isoformat()
                })
                
                if regression_detected:
                    regressions.append(f"{test['name']}: {test_result.get('message', 'Regression detected')}")
                
                # Clean up temporary file
                os.unlink(temp_script)
                
                logger.debug(f"Regression test completed: {test['name']} (regression: {regression_detected})")
                
            except Exception as e:
                logger.error(f"Regression test failed: {test['name']} - {e}")
                regression_results.append({
                    "name": test["name"],
                    "success": False,
                    "expected_failure": test.get("expected_failure", False),
                    "regression_detected": True,
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                regressions.append(f"{test['name']}: {e}")
        
        # Save regression analysis results
        regression_file = self.post_validation_dir / "regression_analysis.json"
        with open(regression_file, 'w') as f:
            json.dump(regression_results, f, indent=2)
        
        return {
            "total_regression_tests": len(regression_tests),
            "regressions_detected": len(regressions),
            "regressions": regressions,
            "regression_results": regression_results,
            "regression_file": str(regression_file)
        }

    def _generate_comparison_report(self, validation_data: Dict[str, Any]) -> None:
        """Generate human-readable comparison report."""
        report_file = self.post_validation_dir / "post_migration_report.md"
        
        with open(report_file, 'w') as f:
            f.write("# Post-Migration Validation Report\n\n")
            f.write(f"**Generated:** {validation_data['timestamp']}\n")
            f.write(f"**Project Root:** {validation_data['project_root']}\n\n")
            
            # CLI Comparison Summary
            cli_data = validation_data.get('cli_comparison', {})
            f.write("## CLI Command Comparison\n\n")
            f.write(f"- **Total Comparisons:** {cli_data.get('total_comparisons', 0)}\n")
            f.write(f"- **Matching Outputs:** {cli_data.get('matching_outputs', 0)}\n")
            f.write(f"- **Different Outputs:** {cli_data.get('different_outputs', 0)}\n")
            
            if cli_data.get('critical_differences'):
                f.write(f"- **Critical Differences:** {len(cli_data['critical_differences'])}\n")
                for diff in cli_data['critical_differences']:
                    f.write(f"  - ❌ {diff}\n")
            
            if cli_data.get('warnings'):
                f.write(f"- **Warnings:** {len(cli_data['warnings'])}\n")
                for warning in cli_data['warnings']:
                    f.write(f"  - ⚠️ {warning}\n")
            
            f.write("\n")
            
            # Test Comparison Summary
            test_data = validation_data.get('test_comparison', {})
            f.write("## Test Suite Execution\n\n")
            f.write(f"- **Total Test Suites:** {test_data.get('total_test_suites', 0)}\n")
            f.write(f"- **Successful:** {test_data.get('successful_test_suites', 0)}\n")
            f.write(f"- **Failed:** {test_data.get('failed_test_suites', 0)}\n")
            
            if test_data.get('critical_test_failures'):
                f.write(f"- **Critical Test Failures:** {len(test_data['critical_test_failures'])}\n")
                for failure in test_data['critical_test_failures']:
                    f.write(f"  - ❌ {failure}\n")
            
            if test_data.get('test_warnings'):
                f.write(f"- **Test Warnings:** {len(test_data['test_warnings'])}\n")
                for warning in test_data['test_warnings']:
                    f.write(f"  - ⚠️ {warning}\n")
            
            f.write("\n")
            
            # Configuration Validation Summary
            config_data = validation_data.get('configuration_validation', {})
            f.write("## Configuration Validation\n\n")
            f.write(f"- **Total Config Tests:** {config_data.get('total_configs', 0)}\n")
            f.write(f"- **Successful:** {config_data.get('successful_configs', 0)}\n")
            f.write(f"- **Failed:** {config_data.get('failed_configs', 0)}\n")
            
            if config_data.get('config_failures'):
                f.write(f"- **Configuration Failures:** {len(config_data['config_failures'])}\n")
                for failure in config_data['config_failures']:
                    f.write(f"  - ❌ {failure}\n")
            
            f.write("\n")
            
            # Regression Analysis Summary
            regression_data = validation_data.get('regression_analysis', {})
            f.write("## Regression Analysis\n\n")
            f.write(f"- **Total Regression Tests:** {regression_data.get('total_regression_tests', 0)}\n")
            f.write(f"- **Regressions Detected:** {regression_data.get('regressions_detected', 0)}\n")
            
            if regression_data.get('regressions'):
                f.write(f"- **Regressions:** {len(regression_data['regressions'])}\n")
                for regression in regression_data['regressions']:
                    f.write(f"  - ❌ {regression}\n")
            
            f.write("\n")
            
            # Overall Status
            total_issues = (
                len(cli_data.get('critical_differences', [])) +
                len(test_data.get('critical_test_failures', [])) +
                len(config_data.get('config_failures', [])) +
                len(regression_data.get('regressions', []))
            )
            
            if total_issues == 0:
                f.write("## ✅ Overall Status: PASSED\n\n")
                f.write("Migration validation completed successfully with no critical issues detected.\n")
            else:
                f.write("## ❌ Overall Status: FAILED\n\n")
                f.write(f"Migration validation detected {total_issues} critical issues that need to be addressed.\n")
            
            f.write("\n## Files Generated\n\n")
            f.write(f"- CLI Comparison: `{cli_data.get('comparison_file', 'N/A')}`\n")
            f.write(f"- Test Results: `{test_data.get('test_file', 'N/A')}`\n")
            f.write(f"- Config Validation: `{config_data.get('validation_file', 'N/A')}`\n")
            f.write(f"- Regression Analysis: `{regression_data.get('regression_file', 'N/A')}`\n")
        
        logger.info(f"Post-migration report generated: {report_file}")


def main():
    """Main entry point for post-migration validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Post-migration validation system for IC CLI")
    parser.add_argument("--project-root", type=Path, help="Project root directory")
    parser.add_argument("--pre-validation-dir", type=Path, help="Pre-migration validation directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        validator = PostMigrationValidator(args.project_root, args.pre_validation_dir)
        validation_status = validator.validate_all()
        
        if validation_status.success:
            print("\n✅ Post-migration validation completed successfully!")
            print(f"📊 Passed: {validation_status.passed_checks}/{validation_status.total_checks}")
            if validation_status.warnings:
                print(f"⚠️  Warnings: {len(validation_status.warnings)}")
        else:
            print("\n❌ Post-migration validation failed!")
            print(f"📊 Passed: {validation_status.passed_checks}/{validation_status.total_checks}")
            print(f"❌ Critical failures: {len(validation_status.critical_failures)}")
            for failure in validation_status.critical_failures:
                print(f"  - {failure}")
        
        print(f"📁 Validation data: {validator.post_validation_dir}")
        print(f"📊 Report: {validator.post_validation_dir / 'post_migration_report.md'}")
        
        return 0 if validation_status.success else 1
        
    except Exception as e:
        logger.error(f"Post-migration validation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())