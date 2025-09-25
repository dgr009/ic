"""
Security guidance and remediation system
Provides specific guidance for different types of sensitive data found
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path

from .detector import Detection, ScanResult


@dataclass
class RemediationStep:
    """Represents a single remediation step"""
    step_number: int
    description: str
    command: Optional[str] = None
    example: Optional[str] = None


@dataclass
class GuidanceEntry:
    """Represents guidance for a specific type of sensitive data"""
    pattern_name: str
    title: str
    description: str
    severity: str
    remediation_steps: List[RemediationStep]
    prevention_tips: List[str]
    related_patterns: List[str] = None


class SecurityGuidance:
    """Provides detailed security guidance and remediation instructions"""
    
    def __init__(self):
        self.guidance_entries = self._load_guidance_entries()
    
    def _load_guidance_entries(self) -> Dict[str, GuidanceEntry]:
        """Load predefined guidance entries for different pattern types"""
        entries = {}
        
        # NCP Access Key Guidance
        entries['ncp_access_key'] = GuidanceEntry(
            pattern_name='ncp_access_key',
            title='NCP Access Key Detected',
            description='NCP access keys provide authentication to Naver Cloud Platform services and should never be stored in code.',
            severity='high',
            remediation_steps=[
                RemediationStep(
                    step_number=1,
                    description='Remove the access key from the code',
                    example='# Remove lines like: ncp_access_key = "AKIA1234567890ABCDEF"'
                ),
                RemediationStep(
                    step_number=2,
                    description='Create NCP configuration directory',
                    command='mkdir -p ~/.ncp'
                ),
                RemediationStep(
                    step_number=3,
                    description='Create secure configuration file',
                    command='ic config init',
                    example='This will create ~/.ncp/config.yaml with proper structure'
                ),
                RemediationStep(
                    step_number=4,
                    description='Add credentials to configuration file',
                    example='Edit ~/.ncp/config.yaml:\\naccess_key: "YOUR_ACCESS_KEY"\\nsecret_key: "YOUR_SECRET_KEY"\\nregion: "KR"'
                ),
                RemediationStep(
                    step_number=5,
                    description='Update code to use configuration',
                    example='Use: from ic.platforms.ncp.client import NCPClient\\nclient = NCPClient()'
                )
            ],
            prevention_tips=[
                'Always use configuration files in home directory (~/.ncp/)',
                'Use environment variables for CI/CD: NCP_ACCESS_KEY, NCP_SECRET_KEY',
                'Add *.key, *.pem, config.yaml to .gitignore',
                'Use IC CLI configuration management: ic config init'
            ],
            related_patterns=['ncp_secret_key', 'ncpgov_access_key']
        )
        
        # NCP Secret Key Guidance
        entries['ncp_secret_key'] = GuidanceEntry(
            pattern_name='ncp_secret_key',
            title='NCP Secret Key Detected',
            description='NCP secret keys are used with access keys for authentication and must be kept secure.',
            severity='high',
            remediation_steps=[
                RemediationStep(
                    step_number=1,
                    description='Remove the secret key from the code immediately',
                    example='# Remove lines like: ncp_secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
                ),
                RemediationStep(
                    step_number=2,
                    description='Use IC CLI configuration system',
                    command='ic config init',
                    example='This creates ~/.ncp/config.yaml with secure permissions'
                ),
                RemediationStep(
                    step_number=3,
                    description='Store credentials securely',
                    example='Add to ~/.ncp/config.yaml (not in project):\\nsecret_key: "YOUR_SECRET_KEY"'
                )
            ],
            prevention_tips=[
                'Never commit secret keys to version control',
                'Use environment variables in CI/CD pipelines',
                'Rotate keys regularly',
                'Use IAM roles when possible instead of keys'
            ],
            related_patterns=['ncp_access_key', 'ncpgov_secret_key']
        )
        
        # NCPGOV Keys
        entries['ncpgov_access_key'] = GuidanceEntry(
            pattern_name='ncpgov_access_key',
            title='NCPGOV Access Key Detected',
            description='NCPGOV (Government Cloud) access keys require special security handling.',
            severity='high',
            remediation_steps=[
                RemediationStep(
                    step_number=1,
                    description='Remove access key from code immediately',
                    example='# Remove: ncpgov_access_key = "GOV1234567890ABCDEF"'
                ),
                RemediationStep(
                    step_number=2,
                    description='Create NCPGOV configuration',
                    command='mkdir -p ~/.ncpgov'
                ),
                RemediationStep(
                    step_number=3,
                    description='Initialize secure configuration',
                    command='ic config init',
                    example='Creates ~/.ncpgov/config.yaml with government cloud settings'
                )
            ],
            prevention_tips=[
                'Government cloud credentials require extra security measures',
                'Use dedicated configuration directory: ~/.ncpgov/',
                'Enable audit logging for all government cloud access',
                'Follow government security compliance requirements'
            ],
            related_patterns=['ncpgov_secret_key', 'ncp_access_key']
        )
        
        # Slack Tokens
        entries['slack_token'] = GuidanceEntry(
            pattern_name='slack_token',
            title='Slack API Token Detected',
            description='Slack tokens provide access to your Slack workspace and should be protected.',
            severity='high',
            remediation_steps=[
                RemediationStep(
                    step_number=1,
                    description='Remove Slack token from code',
                    example='# Remove: slack_token = "xoxb-1234567890-1234567890-abcdefghijklmnopqrstuvwx"'
                ),
                RemediationStep(
                    step_number=2,
                    description='Use environment variables',
                    command='export SLACK_TOKEN="your_token_here"  # EXAMPLE',
                    example='In your code: token = os.getenv("SLACK_TOKEN")'
                ),
                RemediationStep(
                    step_number=3,
                    description='Add to .env file (not committed)',
                    example='Create .env file:\\nSLACK_TOKEN=your_token_here\\n\\nAdd .env to .gitignore'
                )
            ],
            prevention_tips=[
                'Use environment variables for all tokens',
                'Add .env files to .gitignore',
                'Use Slack app configuration for production',
                'Rotate tokens regularly'
            ],
            related_patterns=['slack_webhook', 'slack_user_id']
        )
        
        # Generic API Keys
        entries['generic_api_key'] = GuidanceEntry(
            pattern_name='generic_api_key',
            title='Generic API Key Detected',
            description='API keys provide access to external services and should not be in code.',
            severity='high',
            remediation_steps=[
                RemediationStep(
                    step_number=1,
                    description='Remove API key from source code',
                    example='# Remove: api_key = "sk-1234567890abcdef"'
                ),
                RemediationStep(
                    step_number=2,
                    description='Use environment variables',
                    example='API_KEY=your_key_here\\n\\nIn code: api_key = os.getenv("API_KEY")'
                ),
                RemediationStep(
                    step_number=3,
                    description='Update application configuration',
                    example='Use configuration files outside the project directory'
                )
            ],
            prevention_tips=[
                'Use environment variables for all API keys',
                'Use secret management services in production',
                'Implement key rotation policies',
                'Monitor API key usage'
            ]
        )
        
        # Personal Information
        entries['email_address'] = GuidanceEntry(
            pattern_name='email_address',
            title='Email Address Detected',
            description='Email addresses are personal information that should not be hardcoded.',
            severity='medium',
            remediation_steps=[
                RemediationStep(
                    step_number=1,
                    description='Replace with generic placeholder',
                    example='Change: email = "john.doe@company.com"\\nTo: email = "[EMAIL]"'
                ),
                RemediationStep(
                    step_number=2,
                    description='Use configuration for real emails',
                    example='In config: notification_email = "admin@company.com"'
                )
            ],
            prevention_tips=[
                'Use placeholders in examples and documentation',
                'Store real email addresses in configuration',
                'Use role-based emails (admin@, support@) instead of personal ones'
            ]
        )
        
        return entries
    
    def get_guidance_for_detection(self, detection: Detection) -> Optional[GuidanceEntry]:
        """Get specific guidance for a detection"""
        return self.guidance_entries.get(detection.pattern_name)
    
    def get_guidance_for_pattern(self, pattern_name: str) -> Optional[GuidanceEntry]:
        """Get guidance for a specific pattern name"""
        return self.guidance_entries.get(pattern_name)
    
    def generate_remediation_report(self, scan_result: ScanResult) -> str:
        """Generate a comprehensive remediation report"""
        if scan_result.total_detections == 0:
            return "✅ No security issues found - no remediation needed."
        
        output = []
        output.append("🔧 SECURITY REMEDIATION GUIDE")
        output.append("=" * 50)
        output.append("")
        
        # Group detections by pattern
        detections_by_pattern = {}
        for detection in scan_result.detections:
            pattern = detection.pattern_name
            if pattern not in detections_by_pattern:
                detections_by_pattern[pattern] = []
            detections_by_pattern[pattern].append(detection)
        
        # Generate guidance for each pattern
        for pattern_name, detections in detections_by_pattern.items():
            guidance = self.get_guidance_for_pattern(pattern_name)
            
            if guidance:
                output.append(f"🚨 {guidance.title}")
                output.append(f"   Severity: {guidance.severity.upper()}")
                output.append(f"   Occurrences: {len(detections)}")
                output.append("")
                output.append(f"📝 Description:")
                output.append(f"   {guidance.description}")
                output.append("")
                
                # List affected files
                affected_files = {d.file_path for d in detections}
                output.append(f"📁 Affected Files ({len(affected_files)}):")
                for file_path in sorted(affected_files):
                    file_detections = [d for d in detections if d.file_path == file_path]
                    lines = [str(d.line_number) for d in file_detections]
                    output.append(f"   • {file_path} (lines: {', '.join(lines)})")
                output.append("")
                
                # Remediation steps
                output.append("🔧 Remediation Steps:")
                for step in guidance.remediation_steps:
                    output.append(f"   {step.step_number}. {step.description}")
                    if step.command:
                        output.append(f"      Command: {step.command}")
                    if step.example:
                        output.append(f"      Example: {step.example}")
                    output.append("")
                
                # Prevention tips
                output.append("💡 Prevention Tips:")
                for tip in guidance.prevention_tips:
                    output.append(f"   • {tip}")
                output.append("")
                
                output.append("-" * 50)
                output.append("")
        
        # General recommendations
        output.append("🎯 GENERAL SECURITY RECOMMENDATIONS")
        output.append("")
        output.append("1. Install pre-commit hooks to prevent future issues:")
        output.append("   ic security install-hooks")
        output.append("")
        output.append("2. Run security scans regularly:")
        output.append("   ic security scan")
        output.append("")
        output.append("3. Configure security settings:")
        output.append("   ic security config")
        output.append("")
        output.append("4. Add sensitive patterns to .gitignore:")
        output.append("   echo '*.key' >> .gitignore")
        output.append("   echo '*.pem' >> .gitignore")
        output.append("   echo '.env' >> .gitignore")
        output.append("")
        
        return "\\n".join(output)
    
    def get_quick_fix_suggestions(self, detections: List[Detection]) -> Dict[str, List[str]]:
        """Get quick fix suggestions organized by file"""
        suggestions_by_file = {}
        
        for detection in detections:
            file_path = detection.file_path
            if file_path not in suggestions_by_file:
                suggestions_by_file[file_path] = []
            
            guidance = self.get_guidance_for_detection(detection)
            if guidance and guidance.remediation_steps:
                # Get the first (most important) remediation step
                first_step = guidance.remediation_steps[0]
                suggestion = f"Line {detection.line_number}: {first_step.description}"
                if first_step.example:
                    suggestion += f" ({first_step.example})"
                
                suggestions_by_file[file_path].append(suggestion)
        
        return suggestions_by_file
    
    def generate_commit_block_message(self, scan_result: ScanResult) -> str:
        """Generate message to display when blocking a commit"""
        output = []
        output.append("🚨 COMMIT BLOCKED - Security Issues Detected")
        output.append("")
        
        high_severity = scan_result.get_detections_by_severity('high')
        if high_severity:
            output.append(f"❌ {len(high_severity)} HIGH SEVERITY issues found:")
            for detection in high_severity[:3]:  # Show first 3
                output.append(f"   • {detection.file_path}:{detection.line_number} - {detection.description}")
            if len(high_severity) > 3:
                output.append(f"   ... and {len(high_severity) - 3} more")
            output.append("")
        
        output.append("🔧 Quick Fixes:")
        quick_fixes = self.get_quick_fix_suggestions(scan_result.detections[:5])
        for file_path, suggestions in list(quick_fixes.items())[:2]:
            output.append(f"   {file_path}:")
            for suggestion in suggestions[:2]:
                output.append(f"     - {suggestion}")
        output.append("")
        
        output.append("📖 For detailed remediation guide:")
        output.append("   ic security scan --report security_report.json")
        output.append("")
        output.append("🔧 To fix and retry:")
        output.append("   1. Fix the security issues above")
        output.append("   2. Run: ic security scan --staged")
        output.append("   3. Retry your commit")
        
        return "\\n".join(output)