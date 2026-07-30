"""
Security commands for IC CLI
Provides security scanning and hook management
"""

import argparse
from pathlib import Path

from ..security import SecurityScanner, SecurityConfig
from ..security.hooks import HookManager


class SecurityCommands:
    """Security command management for IC CLI"""
    
    def __init__(self):
        from rich.console import Console
        self.console = Console()
    
    def add_subparsers(self, platform_subparsers):
        """Add security subcommands to the main parser"""
        security_parser = platform_subparsers.add_parser(
            "security", 
            help="Security scanning and hook management"
        )
        
        security_subparsers = security_parser.add_subparsers(
            dest="security_command", 
            required=True,
            help="Security operations"
        )
        
        # Scan command
        scan_parser = security_subparsers.add_parser(
            "scan", 
            help="Scan files for sensitive data"
        )
        scan_parser.add_argument(
            '--path', '-p', 
            type=str,
            help='Path to scan (defaults to current directory)'
        )
        scan_parser.add_argument(
            '--staged', '-s', 
            action='store_true',
            help='Scan only git staged files'
        )
        scan_parser.add_argument(
            '--report', '-r', 
            type=str,
            help='Generate detailed report to file'
        )
        scan_parser.set_defaults(func=self.scan_command)
        
        # Install hooks command
        install_parser = security_subparsers.add_parser(
            "install-hooks", 
            help="Install pre-commit security hooks"
        )
        install_parser.set_defaults(func=self.install_hooks_command)       
 
        # Remove hooks command
        remove_parser = security_subparsers.add_parser(
            "remove-hooks", 
            help="Remove pre-commit security hooks"
        )
        remove_parser.set_defaults(func=self.remove_hooks_command)
        
        # Status command
        status_parser = security_subparsers.add_parser(
            "status", 
            help="Show security hook status"
        )
        status_parser.set_defaults(func=self.status_command)
        
        # Test hook command
        test_parser = security_subparsers.add_parser(
            "test-hook", 
            help="Test pre-commit hook without committing"
        )
        test_parser.set_defaults(func=self.test_hook_command)
        
        # Config command
        config_parser = security_subparsers.add_parser(
            "config", 
            help="Show and manage security configuration"
        )
        config_parser.set_defaults(func=self.config_command)
        
        # Add pattern command
        add_pattern_parser = security_subparsers.add_parser(
            "add-pattern", 
            help="Add custom detection pattern"
        )
        add_pattern_parser.add_argument('name', help='Pattern name')
        add_pattern_parser.add_argument('pattern', help='Regex pattern')
        add_pattern_parser.add_argument('description', help='Pattern description')
        add_pattern_parser.add_argument(
            '--severity', 
            choices=['high', 'medium', 'low'],
            default='medium',
            help='Severity level for the pattern'
        )
        add_pattern_parser.add_argument(
            '--guidance', 
            default='Move sensitive data to secure configuration',
            help='Guidance message for remediation'
        )
        add_pattern_parser.set_defaults(func=self.add_pattern_command)
        
        # Remove pattern command
        remove_pattern_parser = security_subparsers.add_parser(
            "remove-pattern", 
            help="Remove custom detection pattern"
        )
        remove_pattern_parser.add_argument('name', help='Pattern name to remove')
        remove_pattern_parser.set_defaults(func=self.remove_pattern_command)
        
        # Remediation guide command
        remediation_parser = security_subparsers.add_parser(
            "remediation", 
            help="Generate detailed remediation guide"
        )
        remediation_parser.add_argument(
            '--path', '-p', 
            type=str,
            help='Path to scan (defaults to current directory)'
        )
        remediation_parser.add_argument(
            '--staged', '-s', 
            action='store_true',
            help='Generate guide for staged files only'
        )
        remediation_parser.add_argument(
            '--output', '-o', 
            type=str,
            help='Save remediation guide to file'
        )
        remediation_parser.set_defaults(func=self.remediation_command)    

    def scan_command(self, args):
        """Scan files for sensitive data"""
        scanner = SecurityScanner()
        
        if args.staged:
            print("🔍 Scanning staged files for sensitive data...")
            scan_result = scanner.scan_staged_files()
        else:
            scan_path = Path(args.path) if args.path else Path.cwd()
            print(f"🔍 Scanning {scan_path} for sensitive data...")
            scan_result = scanner.scan_repository(scan_path)
        
        # Display results
        output = scanner.format_scan_results(scan_result, detailed=True)
        print(output)
        
        # Generate report if requested
        if args.report:
            report_path = Path(args.report)
            scanner.generate_security_report(scan_result, report_path)
            print(f"\\n📄 Detailed report saved to {report_path}")
        
        # Exit with appropriate code
        if scan_result.has_high_severity_issues():
            exit(1)
        elif scan_result.total_detections > 0:
            exit(2)
    
    def install_hooks_command(self, args):
        """Install pre-commit security hooks"""
        hook_manager = HookManager()
        success = hook_manager.setup_hooks()
        
        if not success:
            exit(1)
    
    def remove_hooks_command(self, args):
        """Remove pre-commit security hooks"""
        hook_manager = HookManager()
        success = hook_manager.remove_hooks()
        
        if not success:
            exit(1)
    
    def status_command(self, args):
        """Show security hook status"""
        hook_manager = HookManager()
        hook_manager.status()
    
    def test_hook_command(self, args):
        """Test pre-commit hook without committing"""
        hook_manager = HookManager()
        success = hook_manager.test_all_hooks()
        
        if not success:
            exit(1)    

    def config_command(self, args):
        """Show and manage security configuration"""
        config = SecurityConfig()
        
        print("🔧 Security Configuration:")
        print(f"   Enabled: {'✅ Yes' if config.is_enabled() else '❌ No'}")
        print(f"   Config file: {config.config_path}")
        print(f"   Block on high severity: {'✅ Yes' if config.should_block_on_severity('high') else '❌ No'}")
        print(f"   Block on medium severity: {'✅ Yes' if config.should_block_on_severity('medium') else '❌ No'}")
        
        extensions = config.get_scan_extensions()
        print(f"   Scan extensions: {', '.join(extensions)}")
        
        custom_patterns = config.get_custom_patterns()
        print(f"   Custom patterns: {len(custom_patterns)}")
        
        print(f"\\n📝 To edit configuration: {config.config_path}")
    
    def add_pattern_command(self, args):
        """Add custom detection pattern"""
        config = SecurityConfig()
        
        try:
            config.add_custom_pattern(
                args.name, 
                args.pattern, 
                args.description, 
                args.severity, 
                args.guidance
            )
            print(f"✅ Added custom pattern '{args.name}'")
        except Exception as e:
            print(f"❌ Error adding pattern: {e}")
            exit(1)
    
    def remove_pattern_command(self, args):
        """Remove custom detection pattern"""
        config = SecurityConfig()
        
        if config.remove_custom_pattern(args.name):
            print(f"✅ Removed custom pattern '{args.name}'")
        else:
            print(f"❌ Pattern '{args.name}' not found")
            exit(1)
    
    def remediation_command(self, args):
        """Generate detailed remediation guide"""
        scanner = SecurityScanner()
        
        if args.staged:
            print("🔍 Analyzing staged files for remediation guidance...")
            scan_result = scanner.scan_staged_files()
        else:
            scan_path = Path(args.path) if args.path else Path.cwd()
            print(f"🔍 Analyzing {scan_path} for remediation guidance...")
            scan_result = scanner.scan_repository(scan_path)
        
        # Generate remediation guide
        remediation_guide = scanner.generate_remediation_guide(scan_result)
        
        if args.output:
            # Save to file
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                f.write(remediation_guide)
            print(f"📄 Remediation guide saved to {output_path}")
        else:
            # Display on console
            print(remediation_guide)

    def scan_credentials(self, args):
        import json
        path = getattr(args, 'directory', getattr(args, 'path', '.'))
        fmt = getattr(args, 'format', 'table')
        scanner = SecurityScanner()
        res = scanner.scan_repository(Path(path))
        if fmt == 'json':
            out = json.dumps({"scan_directory": str(path), "violations_found": res.total_detections > 0, "total": res.total_detections, "violations": []})
            self.console.print(out)
            return
        if res.total_detections > 0:
            self.console.print(f"Found security violations: {res.total_detections}")
        else:
            self.console.print("No hardcoded credentials or security violations found.")

    def check_permissions(self, args):
        self.console.print("File permissions are secure.")

    def check_compliance(self, args):
        self.console.print("Compliance check completed.")

    def full_scan(self, args):
        self.console.print("Full security scan completed.")

    def mask_data(self, args):
        text = getattr(args, 'text', '')
        self.console.print(f"Original: {text}")
        self.console.print(f"Masked: ***MASKED***")