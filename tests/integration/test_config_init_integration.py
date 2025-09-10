"""
Integration Tests for Config Init Command

This module provides integration tests for the config init command functionality
as required by task 20.

Requirements covered:
- 10.4: Create integration tests for config init command functionality
"""

import pytest
import tempfile
import shutil
import os
import yaml
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from argparse import Namespace

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.ic.commands.config import ConfigCommands
from src.ic.config.manager import ConfigManager
from src.ic.config.security import SecurityManager


class TestConfigInitIntegration:
    """Integration tests for config init command."""
    
    def setup_method(self):
        """Set up test environment for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create config commands instance
        self.config_commands = ConfigCommands()
    
    def teardown_method(self):
        """Clean up test environment after each test."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_init_minimal_template(self):
        """Test config init with minimal template."""
        args = Namespace(
            output="ic.yaml",
            template="minimal",
            force=False
        )
        
        # Mock user confirmation to avoid interactive prompts
        with patch('rich.prompt.Confirm.ask', return_value=True):
            self.config_commands.init_config(args)
        
        # Verify config file was created
        config_path = Path("ic.yaml")
        assert config_path.exists()
        
        # Verify config content
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert 'version' in config_data
        assert 'logging' in config_data
        assert 'security' in config_data
        
        # Minimal template should not include cloud-specific sections
        assert 'aws' not in config_data
        assert 'azure' not in config_data
        assert 'gcp' not in config_data
    
    def test_config_init_aws_template(self):
        """Test config init with AWS template."""
        args = Namespace(
            output="ic.yaml",
            template="aws",
            force=False
        )
        
        # Mock interactive prompts
        with patch('rich.prompt.Confirm.ask', return_value=True), \
             patch('rich.prompt.Prompt.ask', side_effect=["123456789012", "us-east-1,us-west-2"]):
            self.config_commands.init_config(args)
        
        # Verify config file was created
        config_path = Path("ic.yaml")
        assert config_path.exists()
        
        # Verify AWS-specific content
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert 'aws' in config_data
        assert 'accounts' in config_data['aws']
        assert 'regions' in config_data['aws']
        assert config_data['aws']['accounts'] == ["123456789012"]
        assert config_data['aws']['regions'] == ["us-east-1", "us-west-2"]
    
    def test_config_init_multi_cloud_template(self):
        """Test config init with multi-cloud template."""
        args = Namespace(
            output="ic.yaml",
            template="multi-cloud",
            force=False
        )
        
        # Mock interactive prompts for all cloud providers
        with patch('rich.prompt.Confirm.ask', return_value=True), \
             patch('rich.prompt.Prompt.ask', side_effect=[
                 "123456789012",  # AWS accounts
                 "us-east-1",     # AWS regions
                 "sub-12345",     # Azure subscription
                 "my-gcp-project" # GCP project
             ]):
            self.config_commands.init_config(args)
        
        # Verify config file was created
        config_path = Path("ic.yaml")
        assert config_path.exists()
        
        # Verify multi-cloud content
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert 'aws' in config_data
        assert 'azure' in config_data
        assert 'gcp' in config_data
        assert config_data['aws']['accounts'] == ["123456789012"]
        assert config_data['azure']['subscription_id'] == "sub-12345"
        assert config_data['gcp']['project_id'] == "my-gcp-project"
    
    def test_config_init_force_overwrite(self):
        """Test config init with force overwrite of existing file."""
        # Create existing config file
        existing_config = {"version": "1.0", "existing": "data"}
        with open("ic.yaml", 'w') as f:
            yaml.dump(existing_config, f)
        
        args = Namespace(
            output="ic.yaml",
            template="minimal",
            force=True
        )
        
        self.config_commands.init_config(args)
        
        # Verify file was overwritten
        with open("ic.yaml", 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert 'existing' not in config_data  # Old data should be gone
        assert 'logging' in config_data       # New data should be present
    
    def test_config_init_creates_env_example(self):
        """Test that config init creates .env.example file."""
        args = Namespace(
            output="ic.yaml",
            template="aws",
            force=False
        )
        
        with patch('rich.prompt.Confirm.ask', return_value=True), \
             patch('rich.prompt.Prompt.ask', return_value=""):
            self.config_commands.init_config(args)
        
        # Verify .env.example was created
        env_example_path = Path(".env.example")
        assert env_example_path.exists()
        
        # Verify content includes AWS variables
        with open(env_example_path, 'r') as f:
            content = f.read()
        
        assert "AWS_PROFILE" in content
        assert "AWS_ACCOUNTS" in content
        assert "AWS_REGIONS" in content
    
    def test_config_init_updates_gitignore(self):
        """Test that config init updates .gitignore with security entries."""
        args = Namespace(
            output="ic.yaml",
            template="minimal",
            force=False
        )
        
        # Create existing .gitignore
        with open(".gitignore", 'w') as f:
            f.write("*.pyc\n__pycache__/\n")
        
        with patch('rich.prompt.Confirm.ask', return_value=True):
            self.config_commands.init_config(args)
        
        # Verify .gitignore was updated
        with open(".gitignore", 'r') as f:
            content = f.read()
        
        # Should contain original content
        assert "*.pyc" in content
        assert "__pycache__/" in content
        
        # Should contain security entries (these depend on SecurityManager implementation)
        # At minimum, should protect sensitive files
        assert ".env" in content or "secrets" in content.lower()
    
    def test_config_init_custom_output_path(self):
        """Test config init with custom output path."""
        custom_path = "custom/config.yaml"
        args = Namespace(
            output=custom_path,
            template="minimal",
            force=False
        )
        
        with patch('rich.prompt.Confirm.ask', return_value=True):
            self.config_commands.init_config(args)
        
        # Verify config file was created at custom path
        config_path = Path(custom_path)
        assert config_path.exists()
        
        # Verify parent directory was created
        assert config_path.parent.exists()
    
    def test_config_init_user_cancellation(self):
        """Test config init when user cancels overwrite."""
        # Create existing config file
        existing_config = {"version": "1.0", "existing": "data"}
        with open("ic.yaml", 'w') as f:
            yaml.dump(existing_config, f)
        
        args = Namespace(
            output="ic.yaml",
            template="minimal",
            force=False
        )
        
        # Mock user declining overwrite
        with patch('rich.prompt.Confirm.ask', return_value=False):
            self.config_commands.init_config(args)
        
        # Verify original file was not modified
        with open("ic.yaml", 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert config_data == existing_config
    
    def test_config_init_error_handling(self):
        """Test config init error handling."""
        args = Namespace(
            output="/invalid/path/config.yaml",  # Invalid path
            template="minimal",
            force=False
        )
        
        # Should handle permission/path errors gracefully
        with pytest.raises(SystemExit):
            self.config_commands.init_config(args)


class TestConfigInitTemplates:
    """Test different configuration templates."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        self.config_commands = ConfigCommands()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_template_config_structure_minimal(self):
        """Test minimal template configuration structure."""
        template_config = self.config_commands._get_template_config("minimal")
        
        required_sections = ["version", "logging", "security"]
        for section in required_sections:
            assert section in template_config
        
        # Should not include cloud-specific sections
        cloud_sections = ["aws", "azure", "gcp"]
        for section in cloud_sections:
            assert section not in template_config
    
    def test_template_config_structure_aws(self):
        """Test AWS template configuration structure."""
        template_config = self.config_commands._get_template_config("aws")
        
        required_sections = ["version", "logging", "security", "aws"]
        for section in required_sections:
            assert section in template_config
        
        # AWS section should have expected structure
        aws_config = template_config["aws"]
        assert isinstance(aws_config, dict)
    
    def test_template_config_structure_azure(self):
        """Test Azure template configuration structure."""
        template_config = self.config_commands._get_template_config("azure")
        
        required_sections = ["version", "logging", "security", "azure"]
        for section in required_sections:
            assert section in template_config
    
    def test_template_config_structure_gcp(self):
        """Test GCP template configuration structure."""
        template_config = self.config_commands._get_template_config("gcp")
        
        required_sections = ["version", "logging", "security", "gcp"]
        for section in required_sections:
            assert section in template_config
    
    def test_template_config_structure_multi_cloud(self):
        """Test multi-cloud template configuration structure."""
        template_config = self.config_commands._get_template_config("multi-cloud")
        
        required_sections = ["version", "logging", "security", "aws", "azure", "gcp"]
        for section in required_sections:
            assert section in template_config
    
    def test_interactive_config_setup_aws(self):
        """Test interactive configuration setup for AWS."""
        base_config = self.config_commands._get_template_config("aws")
        
        with patch('rich.prompt.Prompt.ask', side_effect=["123456789012,987654321098", "us-east-1,us-west-2"]):
            result_config = self.config_commands._interactive_config_setup(base_config, "aws")
        
        assert result_config["aws"]["accounts"] == ["123456789012", "987654321098"]
        assert result_config["aws"]["regions"] == ["us-east-1", "us-west-2"]
    
    def test_interactive_config_setup_empty_responses(self):
        """Test interactive setup with empty responses."""
        base_config = self.config_commands._get_template_config("aws")
        
        with patch('rich.prompt.Prompt.ask', return_value=""):
            result_config = self.config_commands._interactive_config_setup(base_config, "aws")
        
        # Should handle empty responses gracefully
        assert "aws" in result_config


class TestConfigInitEnvExample:
    """Test .env.example file creation."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        self.config_commands = ConfigCommands()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_env_example_minimal(self):
        """Test .env.example creation for minimal template."""
        env_path = Path(".env.example")
        self.config_commands._create_env_example(env_path, "minimal")
        
        assert env_path.exists()
        
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Should contain basic sections
        assert "IC Configuration Environment Variables" in content
        assert "IC_LOG_LEVEL" in content
        assert "DO NOT commit .env to version control" in content
    
    def test_create_env_example_aws(self):
        """Test .env.example creation for AWS template."""
        env_path = Path(".env.example")
        self.config_commands._create_env_example(env_path, "aws")
        
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Should contain AWS-specific variables
        assert "AWS_PROFILE" in content
        assert "AWS_ACCOUNTS" in content
        assert "AWS_REGIONS" in content
        assert "AWS_CROSS_ACCOUNT_ROLE" in content
    
    def test_create_env_example_multi_cloud(self):
        """Test .env.example creation for multi-cloud template."""
        env_path = Path(".env.example")
        self.config_commands._create_env_example(env_path, "multi-cloud")
        
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Should contain all cloud provider variables
        assert "AWS_PROFILE" in content
        assert "AZURE_SUBSCRIPTION_ID" in content
        assert "GCP_PROJECT_ID" in content
        assert "GOOGLE_APPLICATION_CREDENTIALS" in content
    
    def test_env_example_security_warnings(self):
        """Test that .env.example includes security warnings."""
        env_path = Path(".env.example")
        self.config_commands._create_env_example(env_path, "aws")
        
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Should contain security warnings
        security_keywords = ["DO NOT commit", "version control", "security", "secret"]
        assert any(keyword.lower() in content.lower() for keyword in security_keywords)


class TestConfigInitGitignore:
    """Test .gitignore updates."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        self.config_commands = ConfigCommands()
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_update_gitignore_new_file(self):
        """Test .gitignore creation when file doesn't exist."""
        self.config_commands._update_gitignore()
        
        gitignore_path = Path(".gitignore")
        assert gitignore_path.exists()
        
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        # Should contain security entries
        assert len(content.strip()) > 0
    
    def test_update_gitignore_existing_file(self):
        """Test .gitignore update when file already exists."""
        # Create existing .gitignore
        existing_content = "*.pyc\n__pycache__/\n"
        with open(".gitignore", 'w') as f:
            f.write(existing_content)
        
        self.config_commands._update_gitignore()
        
        with open(".gitignore", 'r') as f:
            content = f.read()
        
        # Should preserve existing content
        assert "*.pyc" in content
        assert "__pycache__/" in content
        
        # Should add new security entries
        assert len(content) > len(existing_content)
    
    def test_update_gitignore_no_duplicates(self):
        """Test that .gitignore doesn't add duplicate entries."""
        # Run update twice
        self.config_commands._update_gitignore()
        
        with open(".gitignore", 'r') as f:
            first_content = f.read()
        
        self.config_commands._update_gitignore()
        
        with open(".gitignore", 'r') as f:
            second_content = f.read()
        
        # Content should be identical (no duplicates added)
        assert first_content == second_content


class TestConfigInitEndToEnd:
    """End-to-end integration tests for config init."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_config_init_workflow(self):
        """Test complete config init workflow from start to finish."""
        # Simulate command line arguments
        args = Namespace(
            output="ic.yaml",
            template="aws",
            force=False
        )
        
        config_commands = ConfigCommands()
        
        # Mock all interactive prompts
        with patch('rich.prompt.Confirm.ask', return_value=True), \
             patch('rich.prompt.Prompt.ask', side_effect=["123456789012", "us-east-1"]):
            config_commands.init_config(args)
        
        # Verify all expected files were created
        assert Path("ic.yaml").exists()
        assert Path(".env.example").exists()
        assert Path(".gitignore").exists()
        
        # Verify config file is valid YAML and has expected structure
        with open("ic.yaml", 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert isinstance(config_data, dict)
        assert 'version' in config_data
        assert 'aws' in config_data
        
        # Verify .env.example has AWS content
        with open(".env.example", 'r') as f:
            env_content = f.read()
        
        assert "AWS_" in env_content
        
        # Verify .gitignore has security entries
        with open(".gitignore", 'r') as f:
            gitignore_content = f.read()
        
        assert len(gitignore_content.strip()) > 0
    
    def test_config_validation_after_init(self):
        """Test that initialized config passes validation."""
        args = Namespace(
            output="ic.yaml",
            template="minimal",
            force=False
        )
        
        config_commands = ConfigCommands()
        
        with patch('rich.prompt.Confirm.ask', return_value=True):
            config_commands.init_config(args)
        
        # Try to load and validate the created config
        try:
            config_manager = ConfigManager()
            config_data = config_manager._load_config_file(Path("ic.yaml"))
            errors = config_manager.validate_config(config_data)
            
            # Should have minimal validation errors (minimal template may not include all sections)
            # Allow for missing cloud provider sections in minimal template
            allowed_errors = [
                'Configuration missing required section: aws',
                'Configuration missing required section: azure', 
                'Configuration missing required section: gcp'
            ]
            
            unexpected_errors = [error for error in errors if error not in allowed_errors]
            assert len(unexpected_errors) == 0, f"Unexpected validation errors: {unexpected_errors}"
            
        except Exception as e:
            pytest.fail(f"Config validation failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])