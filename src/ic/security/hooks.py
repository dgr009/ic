"""
Pre-commit hook infrastructure for security scanning
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .scanner import SecurityScanner
from .config import SecurityConfig


class PreCommitHook:
    """Pre-commit hook for security scanning"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = SecurityConfig(config_path)
        self.scanner = SecurityScanner(config_path)
    
    def install_hook(self, repo_path: Path = None) -> bool:
        """Install pre-commit hook in git repository"""
        if repo_path is None:
            repo_path = Path.cwd()
        
        git_hooks_dir = repo_path / '.git' / 'hooks'
        
        # Check if we're in a git repository
        if not git_hooks_dir.exists():
            print("❌ Error: Not in a git repository or .git/hooks directory not found")
            return False
        
        hook_path = git_hooks_dir / 'pre-commit'
        
        # Create the hook script
        hook_script = self._generate_hook_script()
        
        try:
            with open(hook_path, 'w') as f:
                f.write(hook_script)
            
            # Make the hook executable (owner only for security)
            os.chmod(hook_path, 0o700)  # More restrictive permissions
            
            print(f"✅ Pre-commit hook installed at {hook_path}")
            return True
            
        except (IOError, OSError) as e:
            print(f"❌ Error installing pre-commit hook: {e}")
            return False
    
    def uninstall_hook(self, repo_path: Path = None) -> bool:
        """Uninstall pre-commit hook from git repository"""
        if repo_path is None:
            repo_path = Path.cwd()
        
        hook_path = repo_path / '.git' / 'hooks' / 'pre-commit'
        
        if not hook_path.exists():
            print("ℹ️  Pre-commit hook is not installed")
            return True
        
        try:
            # Check if it's our hook by looking for our signature
            with open(hook_path, 'r') as f:
                content = f.read()
            
            if 'IC_CLI_SECURITY_HOOK' not in content:
                print("⚠️  Pre-commit hook exists but is not the IC CLI security hook")
                print("   Manual removal required to avoid overwriting custom hooks")
                return False
            
            hook_path.unlink()
            print("✅ Pre-commit hook uninstalled")
            return True
            
        except (IOError, OSError) as e:
            print(f"❌ Error uninstalling pre-commit hook: {e}")
            return False
    
    def _generate_hook_script(self) -> str:
        """Generate the pre-commit hook script"""
        python_executable = sys.executable
        
        hook_script = f'''#!/bin/bash
# IC_CLI_SECURITY_HOOK - Auto-generated security pre-commit hook
# This hook scans staged files for sensitive data before allowing commits

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

echo "🔍 Running IC CLI security scan on staged files..."

# Run the security scan using Python
{python_executable} -c "
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path.cwd()
sys.path.insert(0, str(project_root / 'src'))

try:
    from ic.security.hooks import PreCommitHook
    
    hook = PreCommitHook()
    exit_code = hook.run_pre_commit_scan()
    sys.exit(exit_code)
    
except ImportError as e:
    print(f'❌ Error: Could not import IC CLI security module: {{e}}')
    print('   Make sure IC CLI is properly installed')
    sys.exit(1)
except Exception as e:
    print(f'❌ Error running security scan: {{e}}')
    sys.exit(1)
"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo -e "${{GREEN}}✅ Security scan passed - commit allowed${{NC}}"
elif [ $exit_code -eq 1 ]; then
    echo -e "${{RED}}🚨 Security scan failed - commit blocked${{NC}}"
    echo -e "${{YELLOW}}Fix the security issues above and try committing again${{NC}}"
elif [ $exit_code -eq 2 ]; then
    echo -e "${{YELLOW}}⚠️  Security scan completed with warnings${{NC}}"
    echo -e "${{YELLOW}}Review the issues above before proceeding${{NC}}"
fi

exit $exit_code
'''
        return hook_script
    
    def run_pre_commit_scan(self) -> int:
        """Run security scan on staged files (called by pre-commit hook)"""
        if not self.config.is_enabled():
            print("ℹ️  Security scanning is disabled")
            return 0
        
        try:
            # Scan staged files
            scan_result = self.scanner.scan_staged_files()
            
            if scan_result.total_detections == 0:
                print("✅ No sensitive data detected in staged files")
                return 0
            
            # Display results
            print(self.scanner.format_scan_results(scan_result, detailed=True))
            
            # Determine if commit should be blocked
            if self.scanner.should_block_commit(scan_result):
                print("\\n" + self.scanner.get_commit_block_message(scan_result))
                return 1
            else:
                print("\\n⚠️  Security issues found but commit allowed")
                print("Consider fixing these issues for better security")
                return 2
                
        except Exception as e:
            print(f"❌ Error during security scan: {e}")
            return 1
    
    def check_hook_status(self, repo_path: Path = None) -> Tuple[bool, str]:
        """Check if pre-commit hook is installed and working"""
        if repo_path is None:
            repo_path = Path.cwd()
        
        git_hooks_dir = repo_path / '.git' / 'hooks'
        hook_path = git_hooks_dir / 'pre-commit'
        
        if not git_hooks_dir.exists():
            return False, "Not in a git repository"
        
        if not hook_path.exists():
            return False, "Pre-commit hook not installed"
        
        try:
            with open(hook_path, 'r') as f:
                content = f.read()
            
            if 'IC_CLI_SECURITY_HOOK' not in content:
                return False, "Pre-commit hook exists but is not IC CLI security hook"
            
            # Check if hook is executable
            if not os.access(hook_path, os.X_OK):
                return False, "Pre-commit hook is not executable"
            
            return True, "Pre-commit hook is installed and ready"
            
        except (IOError, OSError) as e:
            return False, f"Error checking hook: {e}"
    
    def test_hook(self, repo_path: Path = None) -> bool:
        """Test the pre-commit hook without actually committing"""
        print("🧪 Testing pre-commit hook...")
        
        try:
            exit_code = self.run_pre_commit_scan()
            
            if exit_code == 0:
                print("✅ Hook test passed - no security issues found")
            elif exit_code == 1:
                print("🚨 Hook test found security issues that would block commit")
            elif exit_code == 2:
                print("⚠️  Hook test found security warnings")
            
            return True
            
        except Exception as e:
            print(f"❌ Hook test failed: {e}")
            return False


class HookManager:
    """Manages pre-commit hooks for the IC CLI"""
    
    def __init__(self):
        self.hook = PreCommitHook()
    
    def setup_hooks(self, repo_path: Path = None) -> bool:
        """Set up all security hooks"""
        print("🔧 Setting up IC CLI security hooks...")
        
        success = self.hook.install_hook(repo_path)
        
        if success:
            print("\\n✅ Security hooks setup complete!")
            print("\\nNext steps:")
            print("1. Test the hook: ic security test-hook")
            print("2. Configure patterns: ic security config")
            print("3. Run a scan: ic security scan")
        
        return success
    
    def remove_hooks(self, repo_path: Path = None) -> bool:
        """Remove all security hooks"""
        print("🗑️  Removing IC CLI security hooks...")
        
        success = self.hook.uninstall_hook(repo_path)
        
        if success:
            print("✅ Security hooks removed")
        
        return success
    
    def status(self, repo_path: Path = None) -> None:
        """Show status of security hooks"""
        is_installed, message = self.hook.check_hook_status(repo_path)
        
        print("🔍 Security Hook Status:")
        print(f"   Status: {'✅ Installed' if is_installed else '❌ Not Installed'}")
        print(f"   Details: {message}")
        
        if is_installed:
            config = SecurityConfig()
            print(f"   Enabled: {'✅ Yes' if config.is_enabled() else '❌ No'}")
            print(f"   Block on high severity: {'✅ Yes' if config.should_block_on_severity('high') else '❌ No'}")
            print(f"   Block on medium severity: {'✅ Yes' if config.should_block_on_severity('medium') else '❌ No'}")
    
    def test_all_hooks(self, repo_path: Path = None) -> bool:
        """Test all installed hooks"""
        return self.hook.test_hook(repo_path)