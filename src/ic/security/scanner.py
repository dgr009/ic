"""
Security scanner that orchestrates sensitive data detection
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Set

from .detector import SensitiveDataDetector, ScanResult, Detection
from .patterns import SecurityPatterns
from .guidance import SecurityGuidance


class SecurityScanner:
    """Main security scanner class that orchestrates detection and reporting"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.detector = SensitiveDataDetector(self.config)
        self.guidance = SecurityGuidance()
        
    def _load_config(self, config_path: Optional[Path]) -> Dict:
        """Load security configuration from file"""
        default_config = {
            "enabled": True,
            "scan_extensions": [".py", ".yaml", ".yml", ".json", ".txt", ".md", ".sh", ".env"],
            "exclude_patterns": [".git/*", "__pycache__/*", "*.pyc", "node_modules/*"],
            "severity_levels": ["high", "medium", "low"],
            "block_on_high_severity": True,
            "custom_patterns": []
        }
        
        if not config_path or not config_path.exists():
            return default_config
        
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except (json.JSONDecodeError, IOError):
            pass
        
        return default_config
    
    def scan_repository(self, repo_path: Path = None) -> ScanResult:
        """Scan entire repository for sensitive data"""
        if repo_path is None:
            repo_path = Path.cwd()
        
        # Load .gitignore patterns
        gitignore_path = repo_path / '.gitignore'
        gitignore_patterns = self.detector.load_gitignore_patterns(gitignore_path)
        
        # Add custom exclude patterns from config
        for pattern in self.config.get('exclude_patterns', []):
            gitignore_patterns.add(pattern)
        
        return self.detector.scan_directory(repo_path, gitignore_patterns)
    
    def scan_staged_files(self) -> ScanResult:
        """Scan only git staged files for sensitive data"""
        import subprocess
        
        try:
            # Get list of staged files
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only'],
                capture_output=True,
                text=True,
                check=True
            )
            staged_files = result.stdout.strip().split('\n')
            staged_files = [f for f in staged_files if f]  # Remove empty strings
        except (subprocess.CalledProcessError, FileNotFoundError):
            # If git is not available or not in a git repo, scan current directory
            return self.scan_repository()
        
        all_detections = []
        files_scanned = 0
        
        # Load .gitignore patterns
        gitignore_path = Path.cwd() / '.gitignore'
        gitignore_patterns = self.detector.load_gitignore_patterns(gitignore_path)
        
        for file_path_str in staged_files:
            file_path = Path(file_path_str)
            
            if self.detector.should_scan_file(file_path, gitignore_patterns):
                files_scanned += 1
                file_detections = self.detector.scan_file(file_path)
                all_detections.extend(file_detections)
        
        files_with_issues = len({d.file_path for d in all_detections})
        
        return ScanResult(
            total_files_scanned=files_scanned,
            files_with_issues=files_with_issues,
            total_detections=len(all_detections),
            detections=all_detections
        )
    
    def should_block_commit(self, scan_result: ScanResult) -> bool:
        """Determine if commit should be blocked based on scan results"""
        if not self.config.get('enabled', True):
            return False
        
        if self.config.get('block_on_high_severity', True):
            return scan_result.has_high_severity_issues()
        
        return scan_result.total_detections > 0
    
    def format_scan_results(self, scan_result: ScanResult, detailed: bool = True) -> str:
        """Format scan results for display"""
        if scan_result.total_detections == 0:
            return "✅ No sensitive data detected in scanned files."
        
        output = []
        output.append(f"🚨 Security Scan Results:")
        output.append(f"   Files scanned: {scan_result.total_files_scanned}")
        output.append(f"   Files with issues: {scan_result.files_with_issues}")
        output.append(f"   Total detections: {scan_result.total_detections}")
        output.append("")
        
        # Group detections by severity
        high_severity = scan_result.get_detections_by_severity('high')
        medium_severity = scan_result.get_detections_by_severity('medium')
        low_severity = scan_result.get_detections_by_severity('low')
        
        if high_severity:
            output.append("🔴 HIGH SEVERITY ISSUES:")
            for detection in high_severity:
                output.append(f"   {detection.file_path}:{detection.line_number}")
                output.append(f"   └─ {detection.description}")
                if detailed:
                    output.append(f"      Line: {detection.line_content}")
                    output.append(f"      Guidance: {detection.guidance}")
                output.append("")
        
        if medium_severity:
            output.append("🟡 MEDIUM SEVERITY ISSUES:")
            for detection in medium_severity:
                output.append(f"   {detection.file_path}:{detection.line_number}")
                output.append(f"   └─ {detection.description}")
                if detailed:
                    output.append(f"      Line: {detection.line_content}")
                    output.append(f"      Guidance: {detection.guidance}")
                output.append("")
        
        if low_severity:
            output.append("🟢 LOW SEVERITY ISSUES:")
            for detection in low_severity:
                output.append(f"   {detection.file_path}:{detection.line_number}")
                output.append(f"   └─ {detection.description}")
                if detailed:
                    output.append(f"      Line: {detection.line_content}")
                    output.append(f"      Guidance: {detection.guidance}")
                output.append("")
        
        return "\n".join(output)
    
    def generate_security_report(self, scan_result: ScanResult, output_path: Path) -> None:
        """Generate detailed security report"""
        report = {
            "scan_summary": {
                "total_files_scanned": scan_result.total_files_scanned,
                "files_with_issues": scan_result.files_with_issues,
                "total_detections": scan_result.total_detections,
                "has_high_severity": scan_result.has_high_severity_issues()
            },
            "detections": []
        }
        
        for detection in scan_result.detections:
            report["detections"].append({
                "file_path": detection.file_path,
                "line_number": detection.line_number,
                "pattern_name": detection.pattern_name,
                "description": detection.description,
                "severity": detection.severity,
                "matched_text": detection.matched_text,
                "guidance": detection.guidance,
                "line_content": detection.line_content
            })
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
    
    def get_remediation_guidance(self, detections: List[Detection]) -> Dict[str, List[str]]:
        """Get organized remediation guidance for detected issues"""
        guidance_by_type = {}
        
        for detection in detections:
            pattern_type = detection.pattern_name
            if pattern_type not in guidance_by_type:
                guidance_by_type[pattern_type] = []
            
            guidance_entry = f"{detection.file_path}:{detection.line_number} - {detection.guidance}"
            if guidance_entry not in guidance_by_type[pattern_type]:
                guidance_by_type[pattern_type].append(guidance_entry)
        
        return guidance_by_type
    
    def generate_remediation_guide(self, scan_result: ScanResult) -> str:
        """Generate comprehensive remediation guide"""
        return self.guidance.generate_remediation_report(scan_result)
    
    def get_commit_block_message(self, scan_result: ScanResult) -> str:
        """Get message to display when blocking commits"""
        return self.guidance.generate_commit_block_message(scan_result)