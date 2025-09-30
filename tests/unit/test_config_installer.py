#!/usr/bin/env python3
"""
Unit tests for configuration installer module.

This module tests the configuration installer and default config generator functionality.
"""

import unittest
import tempfile
import os
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import modules to test
from ic.config.installer import ConfigInstaller, DefaultConfigGenerator


class TestConfigInstaller(unittest.TestCase):
    """Test cases for ConfigInstaller class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.installer = ConfigInstaller()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_install_default_configs_new_directory(self):
        """Test installation in new directory."""
        target_dir = os.path.join(self.temp_dir, 'new_config')
        
        result = self.installer.install_default_configs(target_dir)
        
        # Verify installation success
        self.assertTrue(result)
        
        # Verify directory was created
        self.assertTrue(os.path.exists(target_dir))
        
        # Verify files were created
        default_yaml = os.path.join(target_dir, 'default.yaml')
        secrets_example = os.path.join(target_dir, 'secrets.yaml.example')
        
        self.assertTrue(os.path.exists(default_yaml))
        self.assertTrue(os.path.exists(secrets_example))
        
        # Verify file contents are valid YAML
        with open(default_yaml, 'r') as f:
            config_data = yaml.safe_load(f)
            self.assertIsInstance(config_data, dict)
            self.assertIn('version', config_data)
    
    def test_install_default_configs_existing_files(self):
        """Test installation with existing files."""
        target_dir = os.path.join(self.temp_dir, 'existing_config')
        os.makedirs(target_dir)
        
        # Create existing file
        existing_file = os.path.join(target_dir, 'default.yaml')
        with open(existing_file, 'w') as f:
            f.write('existing: content')
        
        result = self.installer.install_default_configs(target_dir)
        
        # Should skip installation
        self.assertFalse(result)
        
        # Existing file should remain unchanged
        with open(existing_file, 'r') as f:
            content = f.read()
            self.assertIn('existing: content', content)
    
    def test_check_existing_configs(self):
        """Test checking for existing configuration files."""
        target_dir = os.path.join(self.temp_dir, 'check_config')
        os.makedirs(target_dir)
        
        # Create some files
        default_file = os.path.join(target_dir, 'default.yaml')
        with open(default_file, 'w') as f:
            f.write('test: content')
        
        result = self.installer.check_existing_configs(target_dir)
        
        # Verify results
        self.assertTrue(result['directory_exists'])
        self.assertTrue(result['default.yaml'])
        self.assertFalse(result['secrets.yaml'])
        self.assertFalse(result['secrets.yaml.example'])
    
    def test_create_config_directory(self):
        """Test configuration directory creation."""
        target_dir = os.path.join(self.temp_dir, 'new_dir', 'nested')
        
        self.installer.create_config_directory(target_dir)
        
        # Verify directory was created
        self.assertTrue(os.path.exists(target_dir))
        
        # Verify permissions (on Unix systems)
        if os.name != 'nt':
            stat_info = os.stat(target_dir)
            permissions = oct(stat_info.st_mode)[-3:]
            self.assertEqual(permissions, '700')


class TestDefaultConfigGenerator(unittest.TestCase):
    """Test cases for DefaultConfigGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = DefaultConfigGenerator()
    
    def test_generate_default_yaml(self):
        """Test default YAML configuration generation."""
        result = self.generator.generate_default_yaml()
        
        # Verify it's a string
        self.assertIsInstance(result, str)
        
        # Verify it contains expected sections
        self.assertIn('version:', result)
        self.assertIn('logging:', result)
        self.assertIn('security:', result)
        self.assertIn('aws:', result)
        self.assertIn('azure:', result)
        self.assertIn('gcp:', result)
        self.assertIn('oci:', result)
        self.assertIn('cloudflare:', result)
        
        # Verify it contains comments
        self.assertIn('# IC (Infrastructure CLI) Configuration File', result)
        self.assertIn('# AWS Configuration', result)
    
    def test_generate_secrets_example(self):
        """Test secrets example generation."""
        result = self.generator.generate_secrets_example()
        
        # Verify it's a string
        self.assertIsInstance(result, str)
        
        # Verify it contains expected sections
        self.assertIn('aws:', result)
        self.assertIn('azure:', result)
        self.assertIn('gcp:', result)
        self.assertIn('oci:', result)
        self.assertIn('cloudflare:', result)
        
        # Verify it contains security warnings
        self.assertIn('IMPORTANT SECURITY NOTES:', result)
        self.assertIn('NEVER commit secrets.yaml to version control', result)
        
        # Verify it contains example values
        self.assertIn('your-aws-profile-name', result)
        self.assertIn('your-azure-client-id', result)
    
    def test_add_yaml_comments(self):
        """Test YAML comments generation."""
        result = self.generator._add_yaml_comments()
        
        # Verify it's a string with proper structure
        self.assertIsInstance(result, str)
        
        # Verify it contains version and metadata
        self.assertIn("version: '2.0'", result)
        self.assertIn('metadata:', result)
        
        # Verify it contains all major sections with comments
        sections = ['logging', 'security', 'aws', 'azure', 'gcp', 'oci', 'cloudflare']
        for section in sections:
            self.assertIn(f'{section}:', result)
        
        # Verify it contains helpful comments
        self.assertIn('# Logging configuration', result)
        self.assertIn('# Security settings', result)
        self.assertIn('# AWS Configuration', result)
    
    def test_add_secrets_comments(self):
        """Test secrets comments generation."""
        result = self.generator._add_secrets_comments()
        
        # Verify it's a string
        self.assertIsInstance(result, str)
        
        # Verify it contains security warnings
        self.assertIn('IMPORTANT SECURITY NOTES:', result)
        self.assertIn('Copy this file to \'secrets.yaml\'', result)
        self.assertIn('NEVER commit secrets.yaml to version control', result)
        
        # Verify it contains all service sections
        services = ['aws', 'azure', 'gcp', 'oci', 'cloudflare']
        for service in services:
            self.assertIn(f'{service}:', result)
        
        # Verify it contains environment variable references
        self.assertIn('Environment Variables Reference:', result)
        self.assertIn('AWS_PROFILE', result)
        self.assertIn('AZURE_CLIENT_ID', result)


if __name__ == '__main__':
    unittest.main()