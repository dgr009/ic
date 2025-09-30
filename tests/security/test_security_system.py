"""
Test the security system functionality
"""

import pytest
from pathlib import Path
import tempfile
import os

from ic.security import SecurityScanner, SensitiveDataDetector, SecurityConfig


class TestSecuritySystem:
    """Test security scanning and detection"""
    
    def test_ncp_access_key_detection(self):
        """Test detection of NCP access keys"""
        detector = SensitiveDataDetector()
        
        test_content = '''
        # Configuration file
        ncp_access_key = "AKIA1234567890ABCDEF"
        ncp_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        '''
        
        detections = detector.scan_content(test_content, "test_file.py")
        
        # Should detect both access key and secret key
        assert len(detections) >= 2
        
        # Check for access key detection
        access_key_detections = [d for d in detections if d.pattern_name == 'ncp_access_key']
        assert len(access_key_detections) == 1
        assert access_key_detections[0].severity == 'high'
        
        # Check for secret key detection
        secret_key_detections = [d for d in detections if d.pattern_name == 'ncp_secret_key']
        assert len(secret_key_detections) == 1
        assert secret_key_detections[0].severity == 'high'
    
    def test_slack_token_detection(self):
        """Test detection of Slack tokens"""
        detector = SensitiveDataDetector()
        
        test_content = '''
        slack_token = "xoxb-1234567890-1234567890-abcdefghijklmnopqrstuvwx"
        webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        '''
        
        detections = detector.scan_content(test_content, "slack_config.py")
        
        # Should detect slack token and webhook
        assert len(detections) >= 1
        
        slack_detections = [d for d in detections if 'slack' in d.pattern_name]
        assert len(slack_detections) >= 1
    
    def test_email_detection(self):
        """Test detection of email addresses"""
        detector = SensitiveDataDetector()
        
        test_content = '''
        admin_email = "admin@company.com"
        support_contact = "support@example.org"
        '''
        
        detections = detector.scan_content(test_content, "config.py")
        
        # Should detect email addresses
        email_detections = [d for d in detections if d.pattern_name == 'email_address']
        assert len(email_detections) >= 1
        assert email_detections[0].severity == 'medium'
    
    def test_scanner_integration(self):
        """Test the full scanner integration"""
        scanner = SecurityScanner()
        
        # Create a temporary file with sensitive data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write('''
            # Test configuration
            ncp_access_key = "AKIA1234567890ABCDEF"
            api_key = "sk-1234567890abcdefghijklmnopqrstuvwx"
            email = "test@company.com"
            ''')
            temp_file = f.name
        
        try:
            # Scan the temporary file
            temp_path = Path(temp_file)
            scan_result = scanner.detector.scan_file(temp_path)
            
            # Should detect multiple issues
            assert len(scan_result) >= 2
            
            # Should have high severity issues
            high_severity = [d for d in scan_result if d.severity == 'high']
            assert len(high_severity) >= 1
            
        finally:
            # Clean up
            os.unlink(temp_file)
    
    def test_gitignore_respect(self):
        """Test that scanner respects .gitignore patterns"""
        detector = SensitiveDataDetector()
        
        # Test gitignore pattern matching
        gitignore_patterns = {'*.log', 'temp/*', '.env'}
        
        # These should be excluded
        assert not detector.should_scan_file(Path('debug.log'), gitignore_patterns)
        assert not detector.should_scan_file(Path('temp/config.py'), gitignore_patterns)
        assert not detector.should_scan_file(Path('.env'), gitignore_patterns)
        
        # These should be included
        assert detector.should_scan_file(Path('src/main.py'), gitignore_patterns)
        assert detector.should_scan_file(Path('config.yaml'), gitignore_patterns)
    
    def test_security_config(self):
        """Test security configuration management"""
        # Create temporary config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"enabled": true, "block_on_high_severity": true}')
            config_path = f.name
        
        try:
            config = SecurityConfig(Path(config_path))
            
            assert config.is_enabled() == True
            assert config.should_block_on_severity('high') == True
            assert config.should_block_on_severity('medium') == False
            
        finally:
            os.unlink(config_path)
    
    def test_remediation_guidance(self):
        """Test that remediation guidance is generated"""
        scanner = SecurityScanner()
        
        # Create mock scan result
        from ic.security.detector import Detection, ScanResult
        
        detections = [
            Detection(
                file_path="test.py",
                line_number=1,
                pattern_name="ncp_access_key",
                description="NCP Access Key detected",
                severity="high",
                matched_text="ncp_access_key = \"AKIA123\"",
                guidance="Move to secure configuration",
                line_content="ncp_access_key = \"AKIA123\""
            )
        ]
        
        scan_result = ScanResult(
            total_files_scanned=1,
            files_with_issues=1,
            total_detections=1,
            detections=detections
        )
        
        # Generate remediation guide
        remediation_guide = scanner.generate_remediation_guide(scan_result)
        
        # Should contain guidance
        assert "REMEDIATION GUIDE" in remediation_guide
        assert "NCP Access Key" in remediation_guide
        assert "Remediation Steps" in remediation_guide
        assert "Prevention Tips" in remediation_guide


if __name__ == "__main__":
    pytest.main([__file__])