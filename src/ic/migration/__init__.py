"""
Migration system for IC CLI project structure refactoring.

This package provides comprehensive migration validation and rollback capabilities
for safely refactoring the IC CLI project structure.

Components:
- PreMigrationValidator: Captures baselines and validates current state
- PostMigrationValidator: Compares post-migration state with baselines
- MigrationRollback: Provides rollback capabilities to restore previous state
- MigrationManager: Unified interface for managing the complete migration process

Usage:
    from src.ic.migration import MigrationManager
    
    manager = MigrationManager()
    
    # Run pre-migration validation
    pre_result = manager.run_pre_migration_validation()
    
    # After migration, run post-validation
    post_result = manager.run_post_migration_validation()
    
    # If needed, rollback
    rollback_result = manager.run_rollback()
"""

from .validation import PreMigrationValidator, ValidationResult, CLICommandResult, ModuleImportResult
from .post_validation import PostMigrationValidator, ComparisonResult, ValidationStatus
from .rollback import MigrationRollback, RollbackOperation, RollbackStatus
from .manager import MigrationManager

__all__ = [
    'PreMigrationValidator',
    'PostMigrationValidator', 
    'MigrationRollback',
    'MigrationManager',
    'ValidationResult',
    'CLICommandResult',
    'ModuleImportResult',
    'ComparisonResult',
    'ValidationStatus',
    'RollbackOperation',
    'RollbackStatus'
]

__version__ = '1.0.0'