"""
OCI Compartment module for hierarchical compartment visualization.

This module provides functionality to build and display OCI compartment
hierarchies in a tree structure format.
"""

__version__ = "1.0.0"
__author__ = "IC Development Team"

from .info import CompartmentTreeBuilder, CompartmentTreeRenderer

__all__ = [
    "CompartmentTreeBuilder",
    "CompartmentTreeRenderer"
]