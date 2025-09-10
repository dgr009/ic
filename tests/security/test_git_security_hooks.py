"""
Security-focused tests for Git security validation and pre-commit hooks.

Tests Git integration, pre-commit hooks, and repository security validation.
"""

import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ic.config.security import GitSecurityChecker, SecurityManager


class TestGitSecurityHooks:
    """Security tests for Git integration and hooks."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.security_manager = SecurityManager()
        self.git_checker = GitSecurityChecker(self.security_manager)
    
    def create_temp_git_repo(self):
        """Create temporary Git repository for testing."""
        temp_dir = tempfile.mkdtemp()
        
        # Initialize git repository
        subprocess.run(['git', 'init'], cwd=temp_dir, capture_output=True, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_dir, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=temp_dir, capture_output=True)
        
        return temp_dir
    
    def test_pre_commit_hook_generation(self):
        """Test pre-commit hook script generation."""
        hook_content = self.git_checker._generate_pre_commit_hook()
        
        # Verify hook structure
        assert hook_content.startswith('#!/bin/bash')
        assert 'IC Security Pre-commit Hook' in hook_content
        
        # Verify security checks
        assert 'git diff --cached --name-only' in hook_content
        assert 'credentials|service-account' in hook_content
        assert 'password|token|secret|key' in hook_content
        
        # Verify exit conditions
        assert 'exit 1' in hook_content  # For blocking commits
        assert 'exit 0' in hook_content  # For allowing commits
        
        # Verify informative messages
        assert 'ERROR: Attempting to commit sensitive files!' in hook_content
        assert 'WARNING: Potential secrets found' in hook_content
        assert 'Security checks passed' in hook_content
    
    def test_pre_commit_hook_installation(self):
        """Test pre-commit hook installation process."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                # Install hook
                success = self.git_checker.install_pre_commit_hook()
                assert success is True
                
                # Verify hook file exists
                hook_file = Path(temp_repo) / '.git' / 'hooks' / 'pre-commit'
                assert hook_file.exists()
                
                # Verify hook is executable
                assert os.access(hook_file, os.X_OK)
                
                # Verify hook content
                with open(hook_file, 'r') as f:
                    content = f.read()
                
                assert '#!/bin/bash' in content
                assert 'IC Security Pre-commit Hook' in content
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_pre_commit_hook_installation_no_git(self):
        """Test pre-commit hook installation outside Git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Should fail gracefully when not in git repo
                success = self.git_checker.install_pre_commit_hook()
                assert success is False
                
            finally:
                os.chdir(original_cwd)
    
    def test_staged_files_security_scanning(self):
        """Test security scanning of staged files."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            # Create files with various security issues
            test_files = {
                'safe_config.py': '''
# Safe configuration
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
DEBUG = True
TIMEOUT = 30
''',
                'secrets.py': '''
# File with secrets
DATABASE_PASSWORD = "secret123456"
API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
GITHUB_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"
''',
                'mixed_config.py': '''
# Mixed safe and sensitive data
HOST = "api.example.com"
PORT = 443
SECRET_KEY = "very-secret-key-12345"
TIMEOUT = 60
WEBHOOK_URL = "https://hooks.slack.com/services/T00/B00/secret"
''',
                'credentials.json': '''
{
    "type": "service_account",
    "project_id": "my-project",
    "private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC..."
}
''',
                'normal_code.py': '''
# Normal Python code
def hello_world():
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self, name):
        self.name = name
'''
            }
            
            # Create files
            for filename, content in test_files.items():
                file_path = Path(temp_repo) / filename
                with open(file_path, 'w') as f:
                    f.write(content)
            
            # Add files to git
            for filename in test_files.keys():
                subprocess.run(['git', 'add', filename], cwd=temp_repo, capture_output=True)
            
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                # Check staged files
                warnings = self.git_checker.check_staged_files()
                
                # Should detect secrets in multiple files
                assert len(warnings) > 0
                
                # Should detect secrets.py
                assert any('secrets.py' in warning for warning in warnings)
                
                # Should detect mixed_config.py
                assert any('mixed_config.py' in warning for warning in warnings)
                
                # Should detect credentials.json
                assert any('credentials.json' in warning for warning in warnings)
                
                # Should not warn about safe files
                assert not any('safe_config.py' in warning for warning in warnings)
                assert not any('normal_code.py' in warning for warning in warnings)
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_file_type_filtering(self):
        """Test filtering of file types for security scanning."""
        # Should check these files
        checkable_files = [
            'config.py',
            'settings.yaml',
            'environment.json',
            'README.md',
            'Dockerfile',
            'requirements.txt',

            'script.sh'
        ]
        
        for filename in checkable_files:
            assert self.git_checker._should_check_file(filename), f"Should check {filename}"
        
        # Should not check these files
        non_checkable_files = [
            'binary.exe',
            'image.jpg',
            'document.pdf',
            'archive.zip',
            'library.so',
            'program.dll',
            '__pycache__/module.pyc',
            '.git/config',
            'node_modules/package.json',
            '.pytest_cache/file.cache',
            'logs/app.log'
        ]
        
        for filename in non_checkable_files:
            assert not self.git_checker._should_check_file(filename), f"Should not check {filename}"
    
    def test_secret_pattern_detection_in_files(self):
        """Test secret pattern detection in file content."""
        test_contents = [
            # Should detect secrets
            ('password = "secret123456"', True),
            ('api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"', True),
            ('github_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"', True),
            ('aws_access_key = "AKIA1234567890ABCDEF"', True),
            ('private_key = "-----BEGIN PRIVATE KEY-----"', True),
            ('webhook_secret = "webhook-secret-12345"', True),
            ('DATABASE_PASSWORD="very-secret-password"', True),
            ('export API_TOKEN=sk-abcdef123456', True),
            
            # Should not detect secrets (normal content)
            ('username = "testuser"', False),
            ('host = "localhost"', False),
            ('port = 5432', False),
            ('debug = True', False),
            ('print("Hello World")', False),
            ('def my_function():', False),
            ('# This is a comment', False),
            ('import os', False)
        ]
        
        for content, should_detect in test_contents:
            result = self.git_checker._contains_secrets(content)
            assert result == should_detect, f"Content '{content}' should {'be' if should_detect else 'not be'} detected as containing secrets"
    
    def test_comprehensive_secret_patterns(self):
        """Test comprehensive secret pattern detection."""
        secret_patterns = [
            # Password patterns
            'password = "secret123"',
            'PASSWORD: secret456',
            'pwd=mypassword',
            'database_password = "dbsecret"',
            
            # API key patterns
            'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"',
            'apikey: "key123456789012345678901234567890"',
            'API_KEY="AKIA1234567890ABCDEF"',
            
            # Token patterns
            'token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"',
            'access_token: "xoxb-1234567890-abcdefghijklmnopqrstuvwxyz"',
            'bearer_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"',
            
            # Secret patterns
            'secret = "webhook-secret-123"',
            'client_secret: "client-secret-456"',
            'shared_secret = "shared-secret-789"',
            
            # Private key patterns
            'private_key = "-----BEGIN PRIVATE KEY-----"',
            'ssh_key = "-----BEGIN RSA PRIVATE KEY-----"',
            
            # AWS patterns
            'aws_access_key = "AKIA1234567890ABCDEF"',
            'aws_secret_key = "secret123456789012345678901234567890"'
        ]
        
        for pattern in secret_patterns:
            assert self.git_checker._contains_secrets(pattern), f"Pattern '{pattern}' should be detected as secret"
    
    def test_git_command_error_handling(self):
        """Test error handling for Git command failures."""
        # Test when not in a git repository
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Should handle gracefully when git commands fail
                warnings = self.git_checker.check_staged_files()
                assert warnings == []  # Should return empty list, not raise exception
                
            finally:
                os.chdir(original_cwd)
    
    def test_file_read_error_handling(self):
        """Test error handling for file read failures."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            # Create a file and add it to git
            test_file = Path(temp_repo) / 'test.py'
            with open(test_file, 'w') as f:
                f.write('password = "secret"')
            
            subprocess.run(['git', 'add', 'test.py'], cwd=temp_repo, capture_output=True)
            
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                # Mock file reading to fail
                with patch('builtins.open', side_effect=IOError("Permission denied")):
                    warnings = self.git_checker.check_staged_files()
                    
                    # Should handle file read errors gracefully
                    assert isinstance(warnings, list)
                    # May be empty due to read failure, but shouldn't crash
                    
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_pre_commit_hook_execution_simulation(self):
        """Test simulated pre-commit hook execution."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            # Install hook
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                success = self.git_checker.install_pre_commit_hook()
                assert success is True
                
                # Create files that should trigger hook
                sensitive_file = Path(temp_repo) / 'secrets.env'
                with open(sensitive_file, 'w') as f:
                    f.write('PASSWORD=secret123\nAPI_KEY=sk-1234567890abcdefghijklmnopqrstuvwxyz\n')
                
                key_file = Path(temp_repo) / 'private.key'
                with open(key_file, 'w') as f:
                    f.write('-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n')
                
                # Add files to git
                subprocess.run(['git', 'add', 'secrets.env'], capture_output=True)
                subprocess.run(['git', 'add', 'private.key'], capture_output=True)
                
                # Simulate hook execution by checking staged files
                warnings = self.git_checker.check_staged_files()
                
                # Should detect issues in both files
                assert len(warnings) >= 2
                assert any('secrets.env' in warning for warning in warnings)
                assert any('private.key' in warning for warning in warnings)
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_hook_content_security_patterns(self):
        """Test that hook content includes comprehensive security patterns."""
        hook_content = self.git_checker._generate_pre_commit_hook()
        
        # Should check for sensitive file extensions
        assert '.key' in hook_content
        assert '.pem' in hook_content
        assert '.p12' in hook_content
        assert '.pfx' in hook_content
        
        # Should check for credential files
        assert 'credentials' in hook_content
        assert 'service-account' in hook_content
        
        # Should check for secret patterns in content
        assert 'password' in hook_content
        assert 'token' in hook_content
        assert 'secret' in hook_content
        assert 'key' in hook_content
        
        # Should have proper exit codes
        assert 'exit 1' in hook_content  # Block commits with issues
        assert 'exit 0' in hook_content  # Allow safe commits
    
    def test_multiple_file_types_scanning(self):
        """Test scanning multiple file types for secrets."""
        temp_repo = self.create_temp_git_repo()
        
        try:
            # Create various file types with secrets
            file_contents = {
                'config.py': 'API_KEY = "sk-1234567890abcdefghijklmnopqrstuvwxyz"',
                'settings.yaml': 'password: "secret123"',
                'environment.json': '{"token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz"}',
                '.env': 'DATABASE_PASSWORD=dbsecret123',
                'Dockerfile': 'ENV SECRET_KEY=secret-key-456',
                'script.sh': 'export API_TOKEN="token123456789012345678901234567890"',
                'README.md': 'Use token `sk-example123456` for authentication',
                'safe_file.txt': 'This file contains no secrets, just normal text.'
            }
            
            # Create files
            for filename, content in file_contents.items():
                file_path = Path(temp_repo) / filename
                with open(file_path, 'w') as f:
                    f.write(content)
                subprocess.run(['git', 'add', filename], cwd=temp_repo, capture_output=True)
            
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                warnings = self.git_checker.check_staged_files()
                
                # Should detect secrets in most files
                assert len(warnings) >= 6  # All except safe_file.txt and maybe README.md
                
                # Should detect specific files
                secret_files = ['config.py', 'settings.yaml', 'environment.json', '.env', 'Dockerfile', 'script.sh']
                for secret_file in secret_files:
                    assert any(secret_file in warning for warning in warnings), f"Should detect secrets in {secret_file}"
                
                # Should not detect secrets in safe file
                assert not any('safe_file.txt' in warning for warning in warnings)
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)
    
    def test_performance_with_many_files(self):
        """Test performance of security scanning with many files."""
        import time
        
        temp_repo = self.create_temp_git_repo()
        
        try:
            # Create many files (some with secrets, most without)
            for i in range(100):
                filename = f'file_{i:03d}.py'
                file_path = Path(temp_repo) / filename
                
                if i % 10 == 0:  # Every 10th file has secrets
                    content = f'# File {i}\nAPI_KEY = "sk-{i:032d}"\nprint("Hello from file {i}")'
                else:
                    content = f'# File {i}\nprint("Hello from file {i}")\ndef function_{i}():\n    return {i}'
                
                with open(file_path, 'w') as f:
                    f.write(content)
                
                subprocess.run(['git', 'add', filename], cwd=temp_repo, capture_output=True)
            
            original_cwd = os.getcwd()
            os.chdir(temp_repo)
            
            try:
                # Measure scanning performance
                start_time = time.time()
                
                warnings = self.git_checker.check_staged_files()
                
                scan_time = time.time() - start_time
                
                # Should complete scanning in reasonable time (less than 5 seconds)
                assert scan_time < 5.0, f"Scanning took {scan_time:.2f}s, which is too slow"
                
                # Should detect secrets in 10 files (every 10th file)
                assert len(warnings) == 10
                
            finally:
                os.chdir(original_cwd)
                
        finally:
            import shutil
            shutil.rmtree(temp_repo)


if __name__ == '__main__':
    pytest.main([__file__])