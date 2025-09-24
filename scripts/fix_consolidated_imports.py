#!/usr/bin/env python3
"""
Fix Consolidated Module Imports

This script fixes import issues in consolidated modules by copying implementations
from legacy modules that were moved to backup.
"""

import os
import shutil
from pathlib import Path

def fix_consolidated_imports():
    """Fix all import issues in consolidated modules"""
    
    # Define the mappings of what needs to be copied
    legacy_backup_path = Path("backup/legacy_modules_cleanup_20250924_174148")
    consolidated_path = Path("src/ic/platforms")
    
    # Services to copy for NCP
    ncp_services = ['s3', 'vpc', 'sg', 'rds']
    
    # Services to copy for NCPGOV  
    ncpgov_services = ['ec2', 's3', 'vpc', 'sg', 'rds']
    
    print("🔧 Fixing consolidated module imports...")
    
    # Fix NCP services
    for service in ncp_services:
        legacy_file = legacy_backup_path / "ncp_module" / service / "info.py"
        consolidated_file = consolidated_path / "ncp" / service / "info.py"
        
        if legacy_file.exists():
            print(f"  📋 Copying NCP {service} implementation...")
            
            # Read legacy implementation
            with open(legacy_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix imports in the content
            content = content.replace(
                "from ncp_module.client import NCPClient, NCPAPIError",
                "from src.ic.platforms.ncp.client import NCPClient, NCPAPIError"
            )
            
            # Write to consolidated location
            with open(consolidated_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"  ✅ Fixed NCP {service} imports")
    
    # Fix NCPGOV services
    for service in ncpgov_services:
        # Try both legacy locations
        legacy_file = legacy_backup_path / "ncpgov_module" / service / "info.py"
        if not legacy_file.exists():
            legacy_file = legacy_backup_path / "ncpgov" / service / "info.py"
        
        consolidated_file = consolidated_path / "ncpgov" / service / "info.py"
        
        if legacy_file.exists():
            print(f"  📋 Copying NCPGOV {service} implementation...")
            
            # Read legacy implementation
            with open(legacy_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Fix imports in the content
            content = content.replace(
                "from ncpgov_module.client import NCPGovClient, NCPAPIError",
                "from src.ic.platforms.ncpgov.client import NCPGovClient, NCPAPIError"
            )
            content = content.replace(
                "from ncp_module.client import NCPClient, NCPAPIError", 
                "from src.ic.platforms.ncp.client import NCPClient, NCPAPIError"
            )
            
            # Write to consolidated location
            with open(consolidated_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"  ✅ Fixed NCPGOV {service} imports")
    
    # Copy NCPGOV client if it exists
    ncpgov_client_legacy = legacy_backup_path / "ncpgov_module" / "client.py"
    ncpgov_client_consolidated = consolidated_path / "ncpgov" / "client.py"
    
    if ncpgov_client_legacy.exists():
        print("  📋 Copying NCPGOV client implementation...")
        shutil.copy2(ncpgov_client_legacy, ncpgov_client_consolidated)
        print("  ✅ Fixed NCPGOV client")
    
    print("✅ All consolidated module imports fixed!")

if __name__ == "__main__":
    fix_consolidated_imports()