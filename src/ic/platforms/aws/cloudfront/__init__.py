"""
AWS CloudFront module for distribution information and management.

This module provides functionality to collect and display CloudFront distribution
information including origins, domains, and price classes.
"""

__version__ = "1.0.0"
__author__ = "IC Development Team"

from .info import CloudFrontCollector, CloudFrontRenderer

__all__ = [
    "CloudFrontCollector",
    "CloudFrontRenderer"
]