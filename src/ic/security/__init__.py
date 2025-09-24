"""
Security module for IC CLI
Provides sensitive data detection and security scanning capabilities
"""

from .detector import SensitiveDataDetector, Detection, ScanResult
from .patterns import SecurityPatterns, DetectionPattern
from .scanner import SecurityScanner
from .config import SecurityConfig
from .hooks import PreCommitHook, HookManager
from .guidance import SecurityGuidance, GuidanceEntry, RemediationStep

__all__ = [
    'SensitiveDataDetector', 
    'SecurityPatterns', 
    'SecurityScanner', 
    'SecurityConfig',
    'PreCommitHook',
    'HookManager',
    'SecurityGuidance',
    'Detection',
    'DetectionPattern',
    'ScanResult',
    'GuidanceEntry',
    'RemediationStep'
]