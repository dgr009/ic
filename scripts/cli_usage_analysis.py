#!/usr/bin/env python3
"""
CLI Usage Analysis Script

This script analyzes the actual import patterns in the CLI to identify which modules
are actively used and creates a comprehensive backup system for safe refactoring.

Requirements addressed:
- 1.1: Automated CLI import analysis to identify actual usage patterns
- 1.2: Comprehensive backup system for existing modules and configurations
"""

import ast
import os
import sys
import json
import shutil
import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass, asdict
import argparse


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module_path: str
    imported_name: str
    alias: str
    line_number: int
    import_type: str  # 'from_import' or 'direct_import'


@dataclass
class ModuleUsage:
    """Usage information for a module."""
    module_path: str
    imports: List[ImportInfo]
    is_used_by_cli: bool
    functions_used: Set[str]
    dependencies: Set[str]


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    timestamp: str
    cli_file_path: str
    total_imports: int
    ncp_imports: List[ImportInfo]
    ncpgov_imports: List[ImportInfo]
    aws_imports: List[ImportInfo]
    gcp_imports: List[ImportInfo]
    oci_imports: List[ImportInfo]
    azure_imports: List[ImportInfo]
    other_imports: List[ImportInfo]
    module_usage_map: Dict[str, ModuleUsage]
    dependency_graph: Dict[str, List[str]]
    consolidation_recommendations: Dict[str, Any]


class CLIUsageAnalyzer:
    """Analyzes CLI import patterns and usage."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cli_file = project_root / "src" / "ic" / "cli.py"
        self.analysis_result = None
        
    def analyze_cli_imports(self) -> AnalysisResult:
        """Analyze all imports in the CLI file."""
        print("🔍 Analyzing CLI import patterns...")
        
        if not self.cli_file.exists():
            raise FileNotFoundError(f"CLI file not found: {self.cli_file}")
        
        with open(self.cli_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        # Extract all imports
        imports = self._extract_imports(tree, content)
        
        # Categorize imports by platform
        categorized_imports = self._categorize_imports(imports)
        
        # Analyze module usage
        module_usage_map = self._analyze_module_usage(imports)
        
        # Build dependency graph
        dependency_graph = self._build_dependency_graph(module_usage_map)
        
        # Generate consolidation recommendations
        recommendations = self._generate_consolidation_recommendations(categorized_imports)
        
        self.analysis_result = AnalysisResult(
            timestamp=datetime.datetime.now().isoformat(),
            cli_file_path=str(self.cli_file),
            total_imports=len(imports),
            ncp_imports=categorized_imports['ncp'],
            ncpgov_imports=categorized_imports['ncpgov'],
            aws_imports=categorized_imports['aws'],
            gcp_imports=categorized_imports['gcp'],
            oci_imports=categorized_imports['oci'],
            azure_imports=categorized_imports['azure'],
            other_imports=categorized_imports['other'],
            module_usage_map=module_usage_map,
            dependency_graph=dependency_graph,
            consolidation_recommendations=recommendations
        )
        
        return self.analysis_result
    
    def _extract_imports(self, tree: ast.AST, content: str) -> List[ImportInfo]:
        """Extract all import statements from the AST."""
        imports = []
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(ImportInfo(
                        module_path=module,
                        imported_name=alias.name,
                        alias=alias.asname or alias.name,
                        line_number=node.lineno,
                        import_type='from_import'
                    ))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module_path=alias.name,
                        imported_name=alias.name,
                        alias=alias.asname or alias.name,
                        line_number=node.lineno,
                        import_type='direct_import'
                    ))
        
        return imports
    
    def _categorize_imports(self, imports: List[ImportInfo]) -> Dict[str, List[ImportInfo]]:
        """Categorize imports by platform."""
        categories = {
            'ncp': [],
            'ncpgov': [],
            'aws': [],
            'gcp': [],
            'oci': [],
            'azure': [],
            'other': []
        }
        
        for imp in imports:
            module_path = imp.module_path.lower()
            
            if module_path.startswith('ncp.') or module_path.startswith('ncp_module.'):
                categories['ncp'].append(imp)
            elif module_path.startswith('ncpgov.') or module_path.startswith('ncpgov_module.'):
                categories['ncpgov'].append(imp)
            elif module_path.startswith('aws.'):
                categories['aws'].append(imp)
            elif module_path.startswith('gcp.'):
                categories['gcp'].append(imp)
            elif module_path.startswith('oci_module.'):
                categories['oci'].append(imp)
            elif module_path.startswith('azure_module.'):
                categories['azure'].append(imp)
            else:
                categories['other'].append(imp)
        
        return categories
    
    def _analyze_module_usage(self, imports: List[ImportInfo]) -> Dict[str, ModuleUsage]:
        """Analyze how each module is used."""
        usage_map = {}
        
        for imp in imports:
            module_key = imp.module_path
            
            if module_key not in usage_map:
                usage_map[module_key] = ModuleUsage(
                    module_path=module_key,
                    imports=[],
                    is_used_by_cli=True,  # All imports in CLI are used
                    functions_used=set(),
                    dependencies=set()
                )
            
            usage_map[module_key].imports.append(imp)
            usage_map[module_key].functions_used.add(imp.imported_name)
        
        return usage_map
    
    def _build_dependency_graph(self, usage_map: Dict[str, ModuleUsage]) -> Dict[str, List[str]]:
        """Build a dependency graph between modules."""
        graph = {}
        
        for module_path, usage in usage_map.items():
            graph[module_path] = []
            
            # Analyze dependencies by checking what each module imports
            module_file_path = self._get_module_file_path(module_path)
            if module_file_path and module_file_path.exists():
                deps = self._analyze_module_dependencies(module_file_path)
                graph[module_path] = list(deps)
        
        return graph
    
    def _get_module_file_path(self, module_path: str) -> Path:
        """Convert module path to file path."""
        if not module_path:
            return None
            
        # Convert module path to file path
        parts = module_path.split('.')
        
        # Try different possible locations
        possible_paths = [
            self.project_root / '/'.join(parts) / '__init__.py',
            self.project_root / '/'.join(parts[:-1]) / f"{parts[-1]}.py",
            self.project_root / f"{'/'.join(parts)}.py"
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    def _analyze_module_dependencies(self, module_file: Path) -> Set[str]:
        """Analyze dependencies of a specific module file."""
        dependencies = set()
        
        try:
            with open(module_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    dependencies.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        dependencies.add(alias.name)
        
        except Exception as e:
            print(f"Warning: Could not analyze dependencies for {module_file}: {e}")
        
        return dependencies
    
    def _generate_consolidation_recommendations(self, categorized_imports: Dict[str, List[ImportInfo]]) -> Dict[str, Any]:
        """Generate recommendations for module consolidation."""
        recommendations = {
            'ncp_consolidation': self._analyze_ncp_consolidation(categorized_imports['ncp']),
            'ncpgov_consolidation': self._analyze_ncpgov_consolidation(categorized_imports['ncpgov']),
            'duplicate_detection': self._detect_duplicates(categorized_imports),
            'migration_plan': self._create_migration_plan(categorized_imports)
        }
        
        return recommendations
    
    def _analyze_ncp_consolidation(self, ncp_imports: List[ImportInfo]) -> Dict[str, Any]:
        """Analyze NCP module consolidation opportunities."""
        ncp_modules = set()
        ncp_module_modules = set()
        
        for imp in ncp_imports:
            if imp.module_path.startswith('ncp.'):
                ncp_modules.add(imp.module_path)
            elif imp.module_path.startswith('ncp_module.'):
                ncp_module_modules.add(imp.module_path)
        
        return {
            'ncp_modules': list(ncp_modules),
            'ncp_module_modules': list(ncp_module_modules),
            'consolidation_target': 'src/ic/platforms/ncp/',
            'services_to_merge': {
                'from_ncp': ['ec2', 's3', 'vpc', 'sg'],
                'from_ncp_module': ['rds', 'client']
            },
            'recommended_structure': {
                'ec2': 'from ncp.ec2',
                's3': 'from ncp.s3',
                'vpc': 'from ncp.vpc',
                'sg': 'from ncp.sg',
                'rds': 'from ncp_module.rds',
                'client': 'from ncp_module.client'
            }
        }
    
    def _analyze_ncpgov_consolidation(self, ncpgov_imports: List[ImportInfo]) -> Dict[str, Any]:
        """Analyze NCPGOV module consolidation opportunities."""
        ncpgov_modules = set()
        ncpgov_module_modules = set()
        
        for imp in ncpgov_imports:
            if imp.module_path.startswith('ncpgov.'):
                ncpgov_modules.add(imp.module_path)
            elif imp.module_path.startswith('ncpgov_module.'):
                ncpgov_module_modules.add(imp.module_path)
        
        return {
            'ncpgov_modules': list(ncpgov_modules),
            'ncpgov_module_modules': list(ncpgov_module_modules),
            'consolidation_target': 'src/ic/platforms/ncpgov/',
            'services_to_merge': {
                'from_ncpgov': ['ec2', 's3', 'vpc', 'sg'],
                'from_ncpgov_module': ['rds', 'client']
            },
            'recommended_structure': {
                'ec2': 'from ncpgov.ec2',
                's3': 'from ncpgov.s3',
                'vpc': 'from ncpgov.vpc',
                'sg': 'from ncpgov.sg',
                'rds': 'from ncpgov_module.rds',
                'client': 'from ncpgov_module.client'
            }
        }
    
    def _detect_duplicates(self, categorized_imports: Dict[str, List[ImportInfo]]) -> Dict[str, Any]:
        """Detect potential duplicate functionality."""
        duplicates = {
            'ncp_duplicates': [],
            'ncpgov_duplicates': [],
            'cross_platform_duplicates': []
        }
        
        # Check for NCP duplicates
        ncp_services = set()
        ncp_module_services = set()
        
        for imp in categorized_imports['ncp']:
            if imp.module_path.startswith('ncp.'):
                service = imp.module_path.split('.')[1] if len(imp.module_path.split('.')) > 1 else None
                if service:
                    ncp_services.add(service)
            elif imp.module_path.startswith('ncp_module.'):
                service = imp.module_path.split('.')[1] if len(imp.module_path.split('.')) > 1 else None
                if service:
                    ncp_module_services.add(service)
        
        # Find overlapping services
        overlapping_ncp = ncp_services.intersection(ncp_module_services)
        if overlapping_ncp:
            duplicates['ncp_duplicates'] = list(overlapping_ncp)
        
        # Similar analysis for NCPGOV
        ncpgov_services = set()
        ncpgov_module_services = set()
        
        for imp in categorized_imports['ncpgov']:
            if imp.module_path.startswith('ncpgov.'):
                service = imp.module_path.split('.')[1] if len(imp.module_path.split('.')) > 1 else None
                if service:
                    ncpgov_services.add(service)
            elif imp.module_path.startswith('ncpgov_module.'):
                service = imp.module_path.split('.')[1] if len(imp.module_path.split('.')) > 1 else None
                if service:
                    ncpgov_module_services.add(service)
        
        overlapping_ncpgov = ncpgov_services.intersection(ncpgov_module_services)
        if overlapping_ncpgov:
            duplicates['ncpgov_duplicates'] = list(overlapping_ncpgov)
        
        return duplicates
    
    def _create_migration_plan(self, categorized_imports: Dict[str, List[ImportInfo]]) -> Dict[str, Any]:
        """Create a detailed migration plan."""
        return {
            'phase_1_backup': {
                'description': 'Create comprehensive backup of existing modules',
                'targets': ['ncp/', 'ncp_module/', 'ncpgov/', 'ncpgov_module/']
            },
            'phase_2_consolidation': {
                'description': 'Consolidate modules into unified structure',
                'ncp_target': 'src/ic/platforms/ncp/',
                'ncpgov_target': 'src/ic/platforms/ncpgov/'
            },
            'phase_3_import_updates': {
                'description': 'Update CLI import statements',
                'files_to_update': ['src/ic/cli.py'],
                'import_mappings': self._generate_import_mappings(categorized_imports)
            },
            'phase_4_validation': {
                'description': 'Validate all CLI commands still work',
                'test_commands': self._generate_test_commands(categorized_imports)
            }
        }
    
    def _generate_import_mappings(self, categorized_imports: Dict[str, List[ImportInfo]]) -> Dict[str, str]:
        """Generate import mapping for migration."""
        mappings = {}
        
        for imp in categorized_imports['ncp']:
            old_import = f"from {imp.module_path} import {imp.imported_name}"
            if imp.module_path.startswith('ncp.'):
                service = imp.module_path.split('.')[1]
                new_import = f"from src.ic.platforms.ncp.{service} import {imp.imported_name}"
            elif imp.module_path.startswith('ncp_module.'):
                service = imp.module_path.split('.')[1]
                new_import = f"from src.ic.platforms.ncp.{service} import {imp.imported_name}"
            else:
                new_import = old_import
            
            mappings[old_import] = new_import
        
        for imp in categorized_imports['ncpgov']:
            old_import = f"from {imp.module_path} import {imp.imported_name}"
            if imp.module_path.startswith('ncpgov.'):
                service = imp.module_path.split('.')[1]
                new_import = f"from src.ic.platforms.ncpgov.{service} import {imp.imported_name}"
            elif imp.module_path.startswith('ncpgov_module.'):
                service = imp.module_path.split('.')[1]
                new_import = f"from src.ic.platforms.ncpgov.{service} import {imp.imported_name}"
            else:
                new_import = old_import
            
            mappings[old_import] = new_import
        
        return mappings
    
    def _generate_test_commands(self, categorized_imports: Dict[str, List[ImportInfo]]) -> List[str]:
        """Generate test commands to validate CLI functionality."""
        commands = []
        
        # NCP commands
        ncp_services = set()
        for imp in categorized_imports['ncp']:
            if '.' in imp.module_path:
                service = imp.module_path.split('.')[1]
                ncp_services.add(service)
        
        for service in ncp_services:
            commands.append(f"ic ncp {service} --help")
        
        # NCPGOV commands
        ncpgov_services = set()
        for imp in categorized_imports['ncpgov']:
            if '.' in imp.module_path:
                service = imp.module_path.split('.')[1]
                ncpgov_services.add(service)
        
        for service in ncpgov_services:
            commands.append(f"ic ncpgov {service} --help")
        
        return commands
    
    def save_analysis_report(self, output_file: Path) -> None:
        """Save the analysis report to a JSON file."""
        if not self.analysis_result:
            raise ValueError("No analysis result available. Run analyze_cli_imports() first.")
        
        # Convert dataclasses to dictionaries for JSON serialization
        report_data = {
            'timestamp': self.analysis_result.timestamp,
            'cli_file_path': self.analysis_result.cli_file_path,
            'total_imports': self.analysis_result.total_imports,
            'ncp_imports': [asdict(imp) for imp in self.analysis_result.ncp_imports],
            'ncpgov_imports': [asdict(imp) for imp in self.analysis_result.ncpgov_imports],
            'aws_imports': [asdict(imp) for imp in self.analysis_result.aws_imports],
            'gcp_imports': [asdict(imp) for imp in self.analysis_result.gcp_imports],
            'oci_imports': [asdict(imp) for imp in self.analysis_result.oci_imports],
            'azure_imports': [asdict(imp) for imp in self.analysis_result.azure_imports],
            'other_imports': [asdict(imp) for imp in self.analysis_result.other_imports],
            'module_usage_map': {
                k: {
                    'module_path': v.module_path,
                    'imports': [asdict(imp) for imp in v.imports],
                    'is_used_by_cli': v.is_used_by_cli,
                    'functions_used': list(v.functions_used),
                    'dependencies': list(v.dependencies)
                }
                for k, v in self.analysis_result.module_usage_map.items()
            },
            'dependency_graph': self.analysis_result.dependency_graph,
            'consolidation_recommendations': self.analysis_result.consolidation_recommendations
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Analysis report saved to: {output_file}")
    
    def print_summary(self) -> None:
        """Print a summary of the analysis results."""
        if not self.analysis_result:
            print("❌ No analysis results available")
            return
        
        result = self.analysis_result
        
        print("\n" + "="*60)
        print("📊 CLI USAGE ANALYSIS SUMMARY")
        print("="*60)
        print(f"📅 Analysis Date: {result.timestamp}")
        print(f"📁 CLI File: {result.cli_file_path}")
        print(f"📦 Total Imports: {result.total_imports}")
        
        print(f"\n🔍 Platform Import Breakdown:")
        print(f"  • NCP: {len(result.ncp_imports)} imports")
        print(f"  • NCPGOV: {len(result.ncpgov_imports)} imports")
        print(f"  • AWS: {len(result.aws_imports)} imports")
        print(f"  • GCP: {len(result.gcp_imports)} imports")
        print(f"  • OCI: {len(result.oci_imports)} imports")
        print(f"  • Azure: {len(result.azure_imports)} imports")
        print(f"  • Other: {len(result.other_imports)} imports")
        
        # NCP Analysis
        if result.ncp_imports:
            print(f"\n🔧 NCP Module Analysis:")
            ncp_modules = set()
            ncp_module_modules = set()
            
            for imp in result.ncp_imports:
                if imp.module_path.startswith('ncp.'):
                    ncp_modules.add(imp.module_path)
                elif imp.module_path.startswith('ncp_module.'):
                    ncp_module_modules.add(imp.module_path)
            
            print(f"  • ncp/ modules: {list(ncp_modules)}")
            print(f"  • ncp_module/ modules: {list(ncp_module_modules)}")
        
        # NCPGOV Analysis
        if result.ncpgov_imports:
            print(f"\n🔧 NCPGOV Module Analysis:")
            ncpgov_modules = set()
            ncpgov_module_modules = set()
            
            for imp in result.ncpgov_imports:
                if imp.module_path.startswith('ncpgov.'):
                    ncpgov_modules.add(imp.module_path)
                elif imp.module_path.startswith('ncpgov_module.'):
                    ncpgov_module_modules.add(imp.module_path)
            
            print(f"  • ncpgov/ modules: {list(ncpgov_modules)}")
            print(f"  • ncpgov_module/ modules: {list(ncpgov_module_modules)}")
        
        # Consolidation Recommendations
        print(f"\n💡 Consolidation Recommendations:")
        ncp_rec = result.consolidation_recommendations.get('ncp_consolidation', {})
        if ncp_rec:
            print(f"  • NCP Target: {ncp_rec.get('consolidation_target', 'N/A')}")
            services = ncp_rec.get('services_to_merge', {})
            if services:
                print(f"    - From ncp/: {services.get('from_ncp', [])}")
                print(f"    - From ncp_module/: {services.get('from_ncp_module', [])}")
        
        ncpgov_rec = result.consolidation_recommendations.get('ncpgov_consolidation', {})
        if ncpgov_rec:
            print(f"  • NCPGOV Target: {ncpgov_rec.get('consolidation_target', 'N/A')}")
            services = ncpgov_rec.get('services_to_merge', {})
            if services:
                print(f"    - From ncpgov/: {services.get('from_ncpgov', [])}")
                print(f"    - From ncpgov_module/: {services.get('from_ncpgov_module', [])}")
        
        print("\n" + "="*60)


class BackupManager:
    """Manages comprehensive backup of existing modules and configurations."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backup_root = project_root / "backup" / f"cli_refactor_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def create_comprehensive_backup(self) -> Path:
        """Create a comprehensive backup of all modules and configurations."""
        print("💾 Creating comprehensive backup...")
        
        # Create backup directory
        self.backup_root.mkdir(parents=True, exist_ok=True)
        
        # Backup modules
        modules_to_backup = [
            'ncp',
            'ncp_module', 
            'ncpgov',
            'ncpgov_module',
            'aws',
            'gcp',
            'oci_module',
            'azure_module',
            'src/ic'
        ]
        
        for module in modules_to_backup:
            module_path = self.project_root / module
            if module_path.exists():
                backup_path = self.backup_root / "modules" / module
                self._backup_directory(module_path, backup_path)
                print(f"  ✅ Backed up: {module}")
        
        # Backup configuration files
        config_files = [
            '.env',
            '.ncp/config.example',
            '.ncpgov/config.example',
            'pyproject.toml',
            'requirements.txt',
            'setup.py'
        ]
        
        config_backup_dir = self.backup_root / "configs"
        config_backup_dir.mkdir(parents=True, exist_ok=True)
        
        for config_file in config_files:
            config_path = self.project_root / config_file
            if config_path.exists():
                if config_path.is_file():
                    shutil.copy2(config_path, config_backup_dir / config_file.replace('/', '_'))
                else:
                    backup_path = config_backup_dir / config_file.replace('/', '_')
                    self._backup_directory(config_path, backup_path)
                print(f"  ✅ Backed up config: {config_file}")
        
        # Backup test files
        test_dirs = ['tests']
        for test_dir in test_dirs:
            test_path = self.project_root / test_dir
            if test_path.exists():
                backup_path = self.backup_root / "tests" / test_dir
                self._backup_directory(test_path, backup_path)
                print(f"  ✅ Backed up tests: {test_dir}")
        
        # Create backup manifest
        self._create_backup_manifest()
        
        print(f"✅ Comprehensive backup completed: {self.backup_root}")
        return self.backup_root
    
    def _backup_directory(self, source: Path, destination: Path) -> None:
        """Backup a directory recursively."""
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        else:
            shutil.copytree(source, destination, dirs_exist_ok=True)
    
    def _create_backup_manifest(self) -> None:
        """Create a manifest file describing the backup."""
        manifest = {
            'backup_timestamp': datetime.datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'backup_root': str(self.backup_root),
            'purpose': 'CLI refactoring and module consolidation',
            'backed_up_items': [],
            'git_info': self._get_git_info()
        }
        
        # List all backed up items
        for item in self.backup_root.rglob('*'):
            if item.is_file():
                relative_path = item.relative_to(self.backup_root)
                manifest['backed_up_items'].append(str(relative_path))
        
        manifest_file = self.backup_root / 'backup_manifest.json'
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        print(f"  ✅ Created backup manifest: {manifest_file}")
    
    def _get_git_info(self) -> Dict[str, str]:
        """Get current git information for backup reference."""
        git_info = {}
        
        try:
            import subprocess
            
            # Get current commit hash
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, cwd=self.project_root)
            if result.returncode == 0:
                git_info['commit_hash'] = result.stdout.strip()
            
            # Get current branch
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                  capture_output=True, text=True, cwd=self.project_root)
            if result.returncode == 0:
                git_info['branch'] = result.stdout.strip()
            
            # Get git status
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True, cwd=self.project_root)
            if result.returncode == 0:
                git_info['has_uncommitted_changes'] = bool(result.stdout.strip())
                git_info['status'] = result.stdout.strip()
        
        except Exception as e:
            git_info['error'] = f"Could not get git info: {e}"
        
        return git_info


def main():
    """Main function to run CLI usage analysis and backup."""
    parser = argparse.ArgumentParser(
        description="CLI Usage Analysis and Backup System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--project-root',
        type=Path,
        default=Path.cwd(),
        help='Project root directory (default: current directory)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path.cwd() / 'analysis_output',
        help='Output directory for analysis results'
    )
    
    parser.add_argument(
        '--skip-backup',
        action='store_true',
        help='Skip creating backup (analysis only)'
    )
    
    args = parser.parse_args()
    
    # Ensure project root exists
    if not args.project_root.exists():
        print(f"❌ Project root does not exist: {args.project_root}")
        sys.exit(1)
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Run CLI usage analysis
        print("🚀 Starting CLI Usage Analysis and Backup System")
        print(f"📁 Project Root: {args.project_root}")
        print(f"📊 Output Directory: {args.output_dir}")
        
        analyzer = CLIUsageAnalyzer(args.project_root)
        analysis_result = analyzer.analyze_cli_imports()
        
        # Save analysis report
        report_file = args.output_dir / f"cli_analysis_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        analyzer.save_analysis_report(report_file)
        
        # Print summary
        analyzer.print_summary()
        
        # Create backup if not skipped
        if not args.skip_backup:
            backup_manager = BackupManager(args.project_root)
            backup_path = backup_manager.create_comprehensive_backup()
            
            print(f"\n💾 Backup Information:")
            print(f"  📁 Backup Location: {backup_path}")
            print(f"  📋 Backup Manifest: {backup_path / 'backup_manifest.json'}")
        
        print(f"\n🎉 Analysis and backup completed successfully!")
        print(f"📊 Analysis Report: {report_file}")
        
        if not args.skip_backup:
            print(f"💾 Backup Directory: {backup_path}")
        
        print(f"\n📋 Next Steps:")
        print(f"  1. Review the analysis report: {report_file}")
        print(f"  2. Examine consolidation recommendations")
        print(f"  3. Proceed with module consolidation using the backup as safety net")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()