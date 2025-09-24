"""
Sensitive data detector for scanning files and content
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, NamedTuple
from dataclasses import dataclass

from .patterns import SecurityPatterns, DetectionPattern


class Detection(NamedTuple):
    """Represents a detection of sensitive data"""
    file_path: str
    line_number: int
    pattern_name: str
    description: str
    severity: str
    matched_text: str
    guidance: str
    line_content: str


@dataclass
class ScanResult:
    """Results from scanning files for sensitive data"""
    total_files_scanned: int
    files_with_issues: int
    total_detections: int
    detections: List[Detection]
    
    def has_high_severity_issues(self) -> bool:
        """Check if any high severity issues were found"""
        return any(d.severity == 'high' for d in self.detections)
    
    def get_detections_by_severity(self, severity: str) -> List[Detection]:
        """Get detections filtered by severity"""
        return [d for d in self.detections if d.severity == severity]
    
    def get_files_with_issues(self) -> Set[str]:
        """Get unique file paths that have issues"""
        return {d.file_path for d in self.detections}


class SensitiveDataDetector:
    """Detects sensitive data in files using configurable patterns"""
    
    def __init__(self, custom_config: Optional[Dict] = None):
        self.patterns = SecurityPatterns()
        if custom_config:
            self.patterns.load_custom_patterns_from_config(custom_config)
        
        # Default file extensions to scan
        self.scannable_extensions = {
            '.py', '.yaml', '.yml', '.json', '.txt', '.md', '.sh', '.env',
            '.cfg', '.conf', '.ini', '.toml', '.properties', '.js', '.ts',
            '.java', '.go', '.rs', '.cpp', '.c', '.h', '.hpp'
        }
        
        # Files and directories to always exclude
        self.default_excludes = {
            '.git', '__pycache__', '.pytest_cache', 'node_modules',
            '.venv', 'venv', '.env', 'env', 'build', 'dist',
            '.coverage', '.tox', '.mypy_cache'
        }
    
    def should_scan_file(self, file_path: Path, gitignore_patterns: Set[str] = None) -> bool:
        """Determine if a file should be scanned"""
        
        # Skip if file doesn't exist or is not a file
        if not file_path.is_file():
            return False
        
        # Skip binary files
        if self._is_binary_file(file_path):
            return False
        
        # Skip files in default exclude directories
        for part in file_path.parts:
            if part in self.default_excludes:
                return False
        
        # Skip files that don't have scannable extensions
        if file_path.suffix not in self.scannable_extensions:
            return False
        
        # Check gitignore patterns if provided
        if gitignore_patterns:
            file_str = str(file_path)
            for pattern in gitignore_patterns:
                if self._matches_gitignore_pattern(file_str, pattern):
                    return False
        
        return True
    
    def _is_binary_file(self, file_path: Path) -> bool:
        """Check if file is binary by reading first few bytes"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except (IOError, OSError):
            return True  # Assume binary if can't read
    
    def _matches_gitignore_pattern(self, file_path: str, pattern: str) -> bool:
        """Simple gitignore pattern matching"""
        # Remove leading/trailing whitespace and comments
        pattern = pattern.strip()
        if not pattern or pattern.startswith('#'):
            return False
        
        # Convert gitignore pattern to regex
        # This is a simplified implementation
        pattern = pattern.replace('*', '.*')
        pattern = pattern.replace('?', '.')
        
        try:
            return bool(re.search(pattern, file_path))
        except re.error:
            return False
    
    def scan_file(self, file_path: Path) -> List[Detection]:
        """Scan a single file for sensitive data"""
        detections = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.splitlines()
        except (IOError, OSError, UnicodeDecodeError):
            return detections
        
        for pattern in self.patterns.get_patterns():
            matches = pattern.pattern.finditer(content)
            
            for match in matches:
                # Find line number
                line_start = content.rfind('\n', 0, match.start()) + 1
                line_number = content[:match.start()].count('\n') + 1
                line_end = content.find('\n', match.end())
                if line_end == -1:
                    line_end = len(content)
                
                line_content = content[line_start:line_end]
                
                detection = Detection(
                    file_path=str(file_path),
                    line_number=line_number,
                    pattern_name=pattern.name,
                    description=pattern.description,
                    severity=pattern.severity,
                    matched_text=match.group(0),
                    guidance=pattern.guidance,
                    line_content=line_content.strip()
                )
                detections.append(detection)
        
        return detections
    
    def scan_directory(self, directory: Path, gitignore_patterns: Set[str] = None) -> ScanResult:
        """Scan a directory recursively for sensitive data"""
        all_detections = []
        files_scanned = 0
        
        for file_path in directory.rglob('*'):
            if self.should_scan_file(file_path, gitignore_patterns):
                files_scanned += 1
                file_detections = self.scan_file(file_path)
                all_detections.extend(file_detections)
        
        files_with_issues = len({d.file_path for d in all_detections})
        
        return ScanResult(
            total_files_scanned=files_scanned,
            files_with_issues=files_with_issues,
            total_detections=len(all_detections),
            detections=all_detections
        )
    
    def scan_content(self, content: str, file_path: str = "<content>") -> List[Detection]:
        """Scan content string for sensitive data"""
        detections = []
        lines = content.splitlines()
        
        for pattern in self.patterns.get_patterns():
            matches = pattern.pattern.finditer(content)
            
            for match in matches:
                line_number = content[:match.start()].count('\n') + 1
                line_content = lines[line_number - 1] if line_number <= len(lines) else ""
                
                detection = Detection(
                    file_path=file_path,
                    line_number=line_number,
                    pattern_name=pattern.name,
                    description=pattern.description,
                    severity=pattern.severity,
                    matched_text=match.group(0),
                    guidance=pattern.guidance,
                    line_content=line_content.strip()
                )
                detections.append(detection)
        
        return detections
    
    def load_gitignore_patterns(self, gitignore_path: Path) -> Set[str]:
        """Load patterns from .gitignore file"""
        patterns = set()
        
        if not gitignore_path.exists():
            return patterns
        
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.add(line)
        except (IOError, OSError):
            pass
        
        return patterns