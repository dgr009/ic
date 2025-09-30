#!/usr/bin/env python3
"""
Tests for migration validation and rollback system.

This module tests the comprehensive migration validation capabilities
including pre-migration validation, post-migration validation, and rollback.
"""

import os
import sys
import json
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ic.migration import (
    PreMigrationValidator,
    PostMigrationValidator,
    MigrationRollback,
    MigrationManager,
    ValidationResult,
    CLICommandResult,
    ComparisonResult,
    RollbackOperation
)


class TestPreMigrationValidator:
    """Test pre-migration validation functionality."""
    
    @pytest.fixture
    def temp_project(self):
        """Create temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            
            # Create basic project structure
            (project_root / "src" / "ic").mkdir(parents=True)
            (project_root / "ncp" / "ec2").mkdir(parents=True)
            (project_root / "ncp_module" / "rds").mkdir(parents=True)
            (project_root / "ncpgov" / "ec2").mkdir(parents=True)
            (project_root / "ncpgov_module" / "rds").mkdir(parents=True)
            (project_root / "tests").mkdir()
            
            # Create CLI file
            cli_file = project_root / "src" / "ic" / "cli.py"
            cli_file.write_text("""
#!/usr/bin/env python3
import argparse

def main():
    parser = argparse.ArgumentParser(description="IC CLI")
    parser.add_argument("--help", action="help")
    args = parser.parse_args()

if __name__ == "__main__":
    main()
""")
            
            # Create module files
            for module_path in [
                "ncp/ec2/info.py",
                "ncp_module/rds/info.py", 
                "ncpgov/ec2/info.py",
                "ncpgov_module/rds/info.py"
            ]:
                module_file = project_root / module_path
                module_file.write_text("""
def main():
    print("Module info")

def add_arguments(parser):
    pass
""")
            
            yield project_root
    
    def test_validator_initialization(self, temp_project):
        """Test validator initialization."""
        validator = PreMigrationValidator(temp_project)
        
        assert validator.project_root == temp_project
        assert validator.validation_dir.exists()
        assert validator.backup_dir.exists()
    
    @patch('subprocess.run')
    def test_capture_cli_baselines(self, mock_run, temp_project):
        """Test CLI baseline capture."""
        # Mock subprocess results
        mock_run.return_value = Mock(
            returncode=0,
            stdout="usage: cli.py [-h]",
            stderr=""
        )
        
        validator = PreMigrationValidator(temp_project)
        result = validator._capture_cli_baselines()
        
        assert result["total_commands"] > 0
        assert result["successful_commands"] >= 0
        assert "results" in result
        assert "baseline_file" in result
    
    @patch('subprocess.run')
    def test_record_test_baselines(self, mock_run, temp_project):
        """Test test baseline recording."""
        # Mock pytest results
        mock_run.return_value = Mock(
            returncode=0,
            stdout="===== 5 passed in 0.1s =====",
            stderr=""
        )
        
        validator = PreMigrationValidator(temp_project)
        result = validator._record_test_baselines()
        
        assert result["total_test_suites"] > 0
        assert "results" in result
        assert "baseline_file" in result
    
    def test_validate_config_file_yaml(self, temp_project):
        """Test YAML configuration file validation."""
        # Create test YAML file
        config_file = temp_project / "test_config.yaml"
        config_file.write_text("""
key1: value1
key2:
  nested: value2
""")
        
        validator = PreMigrationValidator(temp_project)
        result = validator._validate_config_file(config_file)
        
        assert result["exists"] is True
        assert result["valid"] is True
        assert result["format"] == "yaml"
        assert "sha256" in result
    
    def test_validate_config_file_json(self, temp_project):
        """Test JSON configuration file validation."""
        # Create test JSON file
        config_file = temp_project / "test_config.json"
        config_file.write_text('{"key1": "value1", "key2": {"nested": "value2"}}')
        
        validator = PreMigrationValidator(temp_project)
        result = validator._validate_config_file(config_file)
        
        assert result["exists"] is True
        assert result["valid"] is True
        assert result["format"] == "json"
    
    def test_validate_config_file_env(self, temp_project):
        """Test .env file validation."""
        # Create test .env file
        env_file = temp_project / ".env"
        env_file.write_text("""
# Test environment file
KEY1=value1
KEY2=value2
# Comment line
KEY3=value3
""")
        
        validator = PreMigrationValidator(temp_project)
        result = validator._validate_config_file(env_file)
        
        assert result["exists"] is True
        assert result["valid"] is True
        assert result["format"] == "env"
        assert len(result["variables"]) == 3
    
    def test_analyze_single_module_success(self, temp_project):
        """Test successful module analysis."""
        validator = PreMigrationValidator(temp_project)
        
        # Create a simple module for testing
        test_module = temp_project / "test_module.py"
        test_module.write_text("""
def test_function():
    pass

class TestClass:
    def method(self):
        pass
""")
        
        # Add to Python path temporarily
        sys.path.insert(0, str(temp_project))
        
        try:
            result = validator._analyze_single_module("test_module")
            assert result.success is True
            assert "test_function" in result.functions_found
            assert "TestClass" in result.functions_found
        finally:
            sys.path.remove(str(temp_project))
            if test_module.exists():
                test_module.unlink()
    
    def test_analyze_single_module_failure(self, temp_project):
        """Test module analysis failure."""
        validator = PreMigrationValidator(temp_project)
        result = validator._analyze_single_module("nonexistent_module")
        
        assert result.success is False
        assert "ImportError" in result.error_message


class TestPostMigrationValidator:
    """Test post-migration validation functionality."""
    
    @pytest.fixture
    def temp_project_with_validation(self):
        """Create temporary project with pre-migration validation data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            validation_dir = project_root / ".migration_validation"
            validation_dir.mkdir()
            
            # Create mock pre-migration baselines
            cli_baselines = [
                {
                    "command": "python -m src.ic.cli --help",
                    "exit_code": 0,
                    "stdout": "usage: cli.py [-h]",
                    "stderr": "",
                    "execution_time": 0.1,
                    "timestamp": "2024-01-01T00:00:00"
                }
            ]
            
            with open(validation_dir / "cli_baselines.json", 'w') as f:
                json.dump(cli_baselines, f)
            
            test_baselines = [
                {
                    "command": "python -m pytest tests/ -v",
                    "exit_code": 0,
                    "stdout": "===== 5 passed in 0.1s =====",
                    "stderr": "",
                    "execution_time": 1.0,
                    "timestamp": "2024-01-01T00:00:00",
                    "test_summary": {"status": "passed", "passed": 5}
                }
            ]
            
            with open(validation_dir / "test_baselines.json", 'w') as f:
                json.dump(test_baselines, f)
            
            yield project_root
    
    def test_validator_initialization(self, temp_project_with_validation):
        """Test post-migration validator initialization."""
        validator = PostMigrationValidator(temp_project_with_validation)
        
        assert validator.project_root == temp_project_with_validation
        assert validator.post_validation_dir.exists()
    
    def test_outputs_match_identical(self, temp_project_with_validation):
        """Test output matching with identical outputs."""
        validator = PostMigrationValidator(temp_project_with_validation)
        
        output1 = "usage: cli.py [-h]"
        output2 = "usage: cli.py [-h]"
        
        assert validator._outputs_match(output1, output2) is True
    
    def test_outputs_match_similar(self, temp_project_with_validation):
        """Test output matching with similar outputs."""
        validator = PostMigrationValidator(temp_project_with_validation)
        
        output1 = "usage: cli.py [-h] at 2024-01-01 12:00:00"
        output2 = "usage: cli.py [-h] at 2024-01-01 12:01:00"
        
        # Should match due to timestamp normalization
        assert validator._outputs_match(output1, output2) is True
    
    def test_outputs_match_different(self, temp_project_with_validation):
        """Test output matching with different outputs."""
        validator = PostMigrationValidator(temp_project_with_validation)
        
        output1 = "usage: cli.py [-h]"
        output2 = "error: command not found"
        
        assert validator._outputs_match(output1, output2) is False
    
    def test_normalize_output(self, temp_project_with_validation):
        """Test output normalization."""
        validator = PostMigrationValidator(temp_project_with_validation)
        
        output = "File /path/to/file.py at 2024-01-01T12:00:00 took 1.23s (0x12345678)"
        normalized = validator._normalize_output(output)
        
        assert "[FILEPATH]" in normalized
        assert "[TIMESTAMP]" in normalized
        assert "[TIME]" in normalized
        assert "[MEMORY]" in normalized
    
    def test_parse_pytest_output_passed(self, temp_project_with_validation):
        """Test pytest output parsing for passed tests."""
        validator = PostMigrationValidator(temp_project_with_validation)
        
        output = "===== 5 passed in 0.1s ====="
        result = validator._parse_pytest_output(output)
        
        assert result["status"] == "passed"
        assert result["passed"] == 5
    
    def test_parse_pytest_output_mixed(self, temp_project_with_validation):
        """Test pytest output parsing for mixed results."""
        validator = PostMigrationValidator(temp_project_with_validation)
        
        output = "===== 3 passed, 2 failed in 0.5s ====="
        result = validator._parse_pytest_output(output)
        
        assert result["status"] == "mixed"
        assert result["passed"] == 3
        assert result["failed"] == 2


class TestMigrationRollback:
    """Test migration rollback functionality."""
    
    @pytest.fixture
    def temp_project_with_backup(self):
        """Create temporary project with backup structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            
            # Create backup structure
            backup_dir = project_root / "backup" / "pre_migration_20240101_120000"
            backup_dir.mkdir(parents=True)
            
            # Create backup manifest
            manifest = {
                "timestamp": "2024-01-01T12:00:00",
                "project_root": str(project_root),
                "backup_directory": str(backup_dir),
                "backup_items": [
                    {
                        "item": "ncp",
                        "source": str(project_root / "ncp"),
                        "backup": str(backup_dir / "modules" / "ncp"),
                        "success": True,
                        "size": 1024
                    },
                    {
                        "item": "cli",
                        "source": str(project_root / "src" / "ic" / "cli.py"),
                        "backup": str(backup_dir / "modules" / "cli"),
                        "success": True,
                        "size": 512
                    }
                ],
                "total_size": 1536
            }
            
            with open(backup_dir / "backup_manifest.json", 'w') as f:
                json.dump(manifest, f)
            
            # Create backup files
            (backup_dir / "modules" / "ncp").mkdir(parents=True)
            (backup_dir / "modules" / "ncp" / "ec2").mkdir()
            (backup_dir / "modules" / "ncp" / "ec2" / "info.py").write_text("# NCP EC2 info")
            
            (backup_dir / "modules").mkdir(exist_ok=True)
            (backup_dir / "modules" / "cli").write_text("#!/usr/bin/env python3\n# CLI file")
            
            yield project_root, backup_dir
    
    def test_rollback_initialization(self, temp_project_with_backup):
        """Test rollback system initialization."""
        project_root, backup_dir = temp_project_with_backup
        
        rollback = MigrationRollback(project_root, backup_dir)
        
        assert rollback.project_root == project_root
        assert rollback.backup_dir == backup_dir
        assert rollback.rollback_dir.exists()
    
    def test_load_backup_manifest(self, temp_project_with_backup):
        """Test loading backup manifest."""
        project_root, backup_dir = temp_project_with_backup
        
        rollback = MigrationRollback(project_root, backup_dir)
        manifest = rollback._load_backup_manifest()
        
        assert manifest is not None
        assert "backup_items" in manifest
        assert len(manifest["backup_items"]) == 2
    
    def test_find_latest_backup(self, temp_project_with_backup):
        """Test finding latest backup."""
        project_root, backup_dir = temp_project_with_backup
        
        # Create another backup (newer)
        newer_backup = project_root / "backup" / "pre_migration_20240102_120000"
        newer_backup.mkdir(parents=True)
        (newer_backup / "backup_manifest.json").write_text('{"test": true}')
        
        rollback = MigrationRollback(project_root)
        found_backup = rollback._find_latest_backup()
        
        assert found_backup == newer_backup
    
    def test_create_rollback_script(self, temp_project_with_backup):
        """Test emergency rollback script creation."""
        project_root, backup_dir = temp_project_with_backup
        
        rollback = MigrationRollback(project_root, backup_dir)
        script_path = rollback.create_rollback_script()
        
        assert script_path.exists()
        assert script_path.suffix == ".py"
        assert script_path.stat().st_mode & 0o111  # Check executable bit


class TestMigrationManager:
    """Test migration manager functionality."""
    
    @pytest.fixture
    def temp_project_full(self):
        """Create full temporary project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            
            # Create project structure
            (project_root / "src" / "ic").mkdir(parents=True)
            (project_root / "ncp" / "ec2").mkdir(parents=True)
            (project_root / "tests").mkdir()
            
            # Create CLI file
            cli_file = project_root / "src" / "ic" / "cli.py"
            cli_file.write_text("""
import argparse
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--help", action="help")
""")
            
            yield project_root
    
    def test_manager_initialization(self, temp_project_full):
        """Test migration manager initialization."""
        manager = MigrationManager(temp_project_full)
        
        assert manager.project_root == temp_project_full
        assert manager.validation_dir.exists()
    
    @patch.object(PreMigrationValidator, 'validate_all')
    def test_run_pre_migration_validation(self, mock_validate, temp_project_full):
        """Test pre-migration validation execution."""
        mock_validate.return_value = {
            "cli_baselines": {"failed_commands": 0},
            "test_baselines": {"failed_test_suites": 0},
            "configuration_validation": {"existing_configs": 2, "valid_configs": 2},
            "module_analysis": {"failed_imports": 0}
        }
        
        manager = MigrationManager(temp_project_full)
        result = manager.run_pre_migration_validation()
        
        assert result["ready_for_migration"] is True
        assert "critical_issues" not in result or len(result["critical_issues"]) == 0
    
    @patch.object(PostMigrationValidator, 'validate_all')
    def test_run_post_migration_validation(self, mock_validate, temp_project_full):
        """Test post-migration validation execution."""
        from ic.migration.post_validation import ValidationStatus
        
        mock_validate.return_value = ValidationStatus(
            success=True,
            total_checks=10,
            passed_checks=10,
            failed_checks=0,
            critical_failures=[],
            warnings=[],
            timestamp="2024-01-01T12:00:00"
        )
        
        manager = MigrationManager(temp_project_full)
        result = manager.run_post_migration_validation()
        
        assert result["success"] is True
        assert result["total_checks"] == 10
        assert result["passed_checks"] == 10
    
    def test_generate_migration_summary(self, temp_project_full):
        """Test migration summary generation."""
        manager = MigrationManager(temp_project_full)
        
        # Create some validation files
        validation_dir = temp_project_full / ".migration_validation"
        validation_dir.mkdir(exist_ok=True)
        (validation_dir / "validation_report.md").write_text("# Test report")
        
        summary = manager.generate_migration_summary()
        
        assert "timestamp" in summary
        assert "project_root" in summary
        assert "files_generated" in summary
        assert "status" in summary
    
    def test_check_pre_migration_issues(self, temp_project_full):
        """Test pre-migration issue checking."""
        manager = MigrationManager(temp_project_full)
        
        # Test with issues
        validation_data = {
            "cli_baselines": {"failed_commands": 2},
            "test_baselines": {"failed_test_suites": 1},
            "configuration_validation": {"existing_configs": 3, "valid_configs": 2},
            "module_analysis": {"failed_imports": 1}
        }
        
        issues = manager._check_pre_migration_issues(validation_data)
        
        assert len(issues) == 4
        assert any("CLI validation failed" in issue for issue in issues)
        assert any("Test validation failed" in issue for issue in issues)
        assert any("Configuration validation failed" in issue for issue in issues)
        assert any("Module analysis failed" in issue for issue in issues)


class TestDataClasses:
    """Test data classes and their functionality."""
    
    def test_validation_result(self):
        """Test ValidationResult dataclass."""
        result = ValidationResult(
            success=True,
            message="Test successful"
        )
        
        assert result.success is True
        assert result.message == "Test successful"
        assert result.timestamp is not None
    
    def test_cli_command_result(self):
        """Test CLICommandResult dataclass."""
        result = CLICommandResult(
            command="test command",
            exit_code=0,
            stdout="output",
            stderr="",
            execution_time=1.0,
            timestamp="2024-01-01T12:00:00"
        )
        
        assert result.command == "test command"
        assert result.exit_code == 0
        assert result.execution_time == 1.0
    
    def test_comparison_result(self):
        """Test ComparisonResult dataclass."""
        result = ComparisonResult(
            item_type="cli_command",
            item_name="help",
            matches=True
        )
        
        assert result.item_type == "cli_command"
        assert result.item_name == "help"
        assert result.matches is True
        assert result.timestamp is not None
    
    def test_rollback_operation(self):
        """Test RollbackOperation dataclass."""
        operation = RollbackOperation(
            operation_type="restore_file",
            source_path="/backup/file.py",
            target_path="/project/file.py",
            success=True
        )
        
        assert operation.operation_type == "restore_file"
        assert operation.success is True
        assert operation.timestamp is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])