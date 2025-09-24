#!/usr/bin/env python3
"""
Dependency Mapping Script

This script generates detailed dependency mappings between modules and CLI commands
to ensure safe refactoring without breaking functionality.

Requirements addressed:
- Generate dependency mapping between modules and CLI commands
- Identify cross-module dependencies and potential conflicts
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass, asdict
import datetime
import argparse


@dataclass
class FunctionCall:
    """Information about a function call."""
    function_name: str
    module_source: str
    line_number: int
    context: str


@dataclass
class ModuleDependency:
    """Dependency information for a module."""
    module_path: str
    imports: List[str]
    function_calls: List[FunctionCall]
    internal_dependencies: Set[str]
    external_dependencies: Set[str]
    cli_commands_using: List[str]


@dataclass
class DependencyMap:
    """Complete dependency mapping."""
    timestamp: str
    project_root: str
    modules: Dict[str, ModuleDependency]
    cli_command_mappings: Dict[str, List[str]]
    cross_platform_dependencies: Dict[str, List[str]]
    potential_conflicts: List[Dict[str, Any]]
    consolidation_safety_analysis: Dict[str, Any]


class DependencyMapper:
    """Maps dependencies between modules and CLI commands."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cli_file = project_root / "src" / "ic" / "cli.py"
        
    def create_dependency_map(self) -> DependencyMap:
        """Create a comprehensive dependency map."""
        print("🗺️  Creating dependency map...")
        
        # Analyze CLI command structure
        cli_commands = self._analyze_cli_commands()
        
        # Map modules to dependencies
        module_dependencies = self._map_module_dependencies()
        
        # Analyze cross-platform dependencies
        cross_platform_deps = self._analyze_cross_platform_dependencies(module_dependencies)
        
        # Identify potential conflicts
        conflicts = self._identify_potential_conflicts(module_dependencies)
        
        # Analyze consolidation safety
        safety_analysis = self._analyze_consolidation_safety(module_dependencies, cli_commands)
        
        return DependencyMap(
            timestamp=datetime.datetime.now().isoformat(),
            project_root=str(self.project_root),
            modules=module_dependencies,
            cli_command_mappings=cli_commands,
            cross_platform_dependencies=cross_platform_deps,
            potential_conflicts=conflicts,
            consolidation_safety_analysis=safety_analysis
        )
    
    def _analyze_cli_commands(self) -> Dict[str, List[str]]:
        """Analyze CLI command structure and map to modules."""
        print("  📋 Analyzing CLI command structure...")
        
        if not self.cli_file.exists():
            raise FileNotFoundError(f"CLI file not found: {self.cli_file}")
        
        with open(self.cli_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse CLI structure
        tree = ast.parse(content)
        
        command_mappings = {}
        
        # Look for parser definitions and command mappings
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for add_parser calls
                if (hasattr(node.func, 'attr') and 
                    node.func.attr == 'add_parser' and 
                    node.args):
                    
                    if isinstance(node.args[0], ast.Constant):
                        command_name = node.args[0].value
                        
                        # Try to find associated modules
                        associated_modules = self._find_associated_modules(command_name, content)
                        command_mappings[command_name] = associated_modules
        
        return command_mappings
    
    def _find_associated_modules(self, command_name: str, cli_content: str) -> List[str]:
        """Find modules associated with a CLI command."""
        associated_modules = []
        
        # Look for import statements that might be related to this command
        lines = cli_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if (line.startswith('from ') and 
                command_name in line.lower()):
                
                # Extract module path
                if ' import ' in line:
                    module_part = line.split(' import ')[0].replace('from ', '')
                    associated_modules.append(module_part)
        
        return associated_modules
    
    def _map_module_dependencies(self) -> Dict[str, ModuleDependency]:
        """Map dependencies for all relevant modules."""
        print("  🔍 Mapping module dependencies...")
        
        module_dependencies = {}
        
        # Define modules to analyze
        modules_to_analyze = [
            'ncp',
            'ncp_module',
            'ncpgov', 
            'ncpgov_module',
            'aws',
            'gcp',
            'oci_module',
            'azure_module'
        ]
        
        for module_name in modules_to_analyze:
            module_path = self.project_root / module_name
            if module_path.exists():
                deps = self._analyze_module_directory(module_path, module_name)
                module_dependencies.update(deps)
        
        return module_dependencies
    
    def _analyze_module_directory(self, module_path: Path, module_name: str) -> Dict[str, ModuleDependency]:
        """Analyze dependencies for all files in a module directory."""
        dependencies = {}
        
        # Find all Python files in the module
        for py_file in module_path.rglob('*.py'):
            if py_file.name == '__init__.py':
                continue
                
            relative_path = py_file.relative_to(self.project_root)
            module_key = str(relative_path).replace('/', '.').replace('.py', '')
            
            try:
                dep = self._analyze_single_file(py_file, module_key)
                dependencies[module_key] = dep
            except Exception as e:
                print(f"    ⚠️  Warning: Could not analyze {py_file}: {e}")
        
        return dependencies
    
    def _analyze_single_file(self, file_path: Path, module_key: str) -> ModuleDependency:
        """Analyze dependencies for a single Python file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        imports = []
        function_calls = []
        internal_deps = set()
        external_deps = set()
        
        # Analyze imports
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
                    
                    # Categorize as internal or external
                    if self._is_internal_module(node.module):
                        internal_deps.add(node.module)
                    else:
                        external_deps.add(node.module)
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
                    
                    if self._is_internal_module(alias.name):
                        internal_deps.add(alias.name)
                    else:
                        external_deps.add(alias.name)
            
            # Analyze function calls
            elif isinstance(node, ast.Call):
                if hasattr(node.func, 'id'):
                    func_name = node.func.id
                elif hasattr(node.func, 'attr'):
                    func_name = node.func.attr
                else:
                    continue
                
                # Get context (surrounding code)
                context = self._get_node_context(content, node.lineno)
                
                function_calls.append(FunctionCall(
                    function_name=func_name,
                    module_source=module_key,
                    line_number=node.lineno,
                    context=context
                ))
        
        # Find CLI commands that use this module
        cli_commands = self._find_cli_commands_using_module(module_key)
        
        return ModuleDependency(
            module_path=module_key,
            imports=imports,
            function_calls=function_calls,
            internal_dependencies=internal_deps,
            external_dependencies=external_deps,
            cli_commands_using=cli_commands
        )
    
    def _is_internal_module(self, module_name: str) -> bool:
        """Check if a module is internal to the project."""
        internal_prefixes = [
            'ncp', 'ncpgov', 'aws', 'gcp', 'oci_module', 'azure_module',
            'common', 'src.ic', 'ic', 'ssh', 'cf'
        ]
        
        return any(module_name.startswith(prefix) for prefix in internal_prefixes)
    
    def _get_node_context(self, content: str, line_number: int, context_lines: int = 2) -> str:
        """Get context around a specific line number."""
        lines = content.split('\n')
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        context_lines_list = lines[start:end]
        return '\n'.join(context_lines_list)
    
    def _find_cli_commands_using_module(self, module_key: str) -> List[str]:
        """Find CLI commands that use a specific module."""
        cli_commands = []
        
        if not self.cli_file.exists():
            return cli_commands
        
        with open(self.cli_file, 'r', encoding='utf-8') as f:
            cli_content = f.read()
        
        # Look for imports of this module in CLI
        module_parts = module_key.split('.')
        
        for line in cli_content.split('\n'):
            if 'import' in line and any(part in line for part in module_parts):
                # Try to extract command context
                # This is a simplified approach - could be enhanced
                if 'ncp' in line:
                    cli_commands.append('ncp')
                elif 'ncpgov' in line:
                    cli_commands.append('ncpgov')
                elif 'aws' in line:
                    cli_commands.append('aws')
                elif 'gcp' in line:
                    cli_commands.append('gcp')
                elif 'oci' in line:
                    cli_commands.append('oci')
                elif 'azure' in line:
                    cli_commands.append('azure')
        
        return cli_commands
    
    def _analyze_cross_platform_dependencies(self, module_dependencies: Dict[str, ModuleDependency]) -> Dict[str, List[str]]:
        """Analyze dependencies that cross platform boundaries."""
        print("  🔗 Analyzing cross-platform dependencies...")
        
        cross_platform_deps = {}
        
        for module_key, dependency in module_dependencies.items():
            platform = self._get_module_platform(module_key)
            
            cross_deps = []
            for dep in dependency.internal_dependencies:
                dep_platform = self._get_module_platform(dep)
                if dep_platform and dep_platform != platform:
                    cross_deps.append(dep)
            
            if cross_deps:
                cross_platform_deps[module_key] = cross_deps
        
        return cross_platform_deps
    
    def _get_module_platform(self, module_key: str) -> str:
        """Get the platform for a module."""
        if module_key.startswith('ncp.') or module_key.startswith('ncp_module.'):
            return 'ncp'
        elif module_key.startswith('ncpgov.') or module_key.startswith('ncpgov_module.'):
            return 'ncpgov'
        elif module_key.startswith('aws.'):
            return 'aws'
        elif module_key.startswith('gcp.'):
            return 'gcp'
        elif module_key.startswith('oci_module.'):
            return 'oci'
        elif module_key.startswith('azure_module.'):
            return 'azure'
        else:
            return 'common'
    
    def _identify_potential_conflicts(self, module_dependencies: Dict[str, ModuleDependency]) -> List[Dict[str, Any]]:
        """Identify potential conflicts during consolidation."""
        print("  ⚠️  Identifying potential conflicts...")
        
        conflicts = []
        
        # Check for duplicate function names within platforms
        platform_functions = {}
        
        for module_key, dependency in module_dependencies.items():
            platform = self._get_module_platform(module_key)
            
            if platform not in platform_functions:
                platform_functions[platform] = {}
            
            for func_call in dependency.function_calls:
                func_name = func_call.function_name
                
                if func_name not in platform_functions[platform]:
                    platform_functions[platform][func_name] = []
                
                platform_functions[platform][func_name].append({
                    'module': module_key,
                    'line': func_call.line_number,
                    'context': func_call.context
                })
        
        # Find conflicts (same function name in multiple modules of same platform)
        for platform, functions in platform_functions.items():
            for func_name, occurrences in functions.items():
                if len(occurrences) > 1:
                    # Check if they're actually different implementations
                    modules = set(occ['module'] for occ in occurrences)
                    if len(modules) > 1:
                        conflicts.append({
                            'type': 'duplicate_function',
                            'platform': platform,
                            'function_name': func_name,
                            'modules': list(modules),
                            'occurrences': occurrences,
                            'severity': 'medium'
                        })
        
        # Check for circular dependencies
        circular_deps = self._find_circular_dependencies(module_dependencies)
        for circular_dep in circular_deps:
            conflicts.append({
                'type': 'circular_dependency',
                'modules': circular_dep,
                'severity': 'high'
            })
        
        return conflicts
    
    def _find_circular_dependencies(self, module_dependencies: Dict[str, ModuleDependency]) -> List[List[str]]:
        """Find circular dependencies between modules."""
        circular_deps = []
        
        # Build dependency graph
        graph = {}
        for module_key, dependency in module_dependencies.items():
            graph[module_key] = list(dependency.internal_dependencies)
        
        # Use DFS to find cycles
        visited = set()
        rec_stack = set()
        
        def dfs(node, path):
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                circular_deps.append(cycle)
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor in graph:  # Only check internal modules
                    dfs(neighbor, path + [node])
            
            rec_stack.remove(node)
        
        for module in graph:
            if module not in visited:
                dfs(module, [])
        
        return circular_deps
    
    def _analyze_consolidation_safety(self, module_dependencies: Dict[str, ModuleDependency], 
                                    cli_commands: Dict[str, List[str]]) -> Dict[str, Any]:
        """Analyze the safety of proposed consolidations."""
        print("  🛡️  Analyzing consolidation safety...")
        
        safety_analysis = {
            'ncp_consolidation': self._analyze_ncp_consolidation_safety(module_dependencies),
            'ncpgov_consolidation': self._analyze_ncpgov_consolidation_safety(module_dependencies),
            'import_impact_analysis': self._analyze_import_impact(module_dependencies),
            'test_impact_analysis': self._analyze_test_impact(),
            'risk_assessment': self._assess_consolidation_risks(module_dependencies)
        }
        
        return safety_analysis
    
    def _analyze_ncp_consolidation_safety(self, module_dependencies: Dict[str, ModuleDependency]) -> Dict[str, Any]:
        """Analyze safety of NCP module consolidation."""
        ncp_modules = {k: v for k, v in module_dependencies.items() 
                      if k.startswith('ncp.') or k.startswith('ncp_module.')}
        
        # Check for conflicts between ncp and ncp_module
        conflicts = []
        ncp_functions = set()
        ncp_module_functions = set()
        
        for module_key, dependency in ncp_modules.items():
            functions = {fc.function_name for fc in dependency.function_calls}
            
            if module_key.startswith('ncp.'):
                ncp_functions.update(functions)
            else:
                ncp_module_functions.update(functions)
        
        overlapping_functions = ncp_functions.intersection(ncp_module_functions)
        
        return {
            'total_modules': len(ncp_modules),
            'ncp_modules': [k for k in ncp_modules.keys() if k.startswith('ncp.')],
            'ncp_module_modules': [k for k in ncp_modules.keys() if k.startswith('ncp_module.')],
            'overlapping_functions': list(overlapping_functions),
            'consolidation_safe': len(overlapping_functions) == 0,
            'risk_level': 'low' if len(overlapping_functions) == 0 else 'medium',
            'recommendations': self._generate_ncp_consolidation_recommendations(ncp_modules)
        }
    
    def _analyze_ncpgov_consolidation_safety(self, module_dependencies: Dict[str, ModuleDependency]) -> Dict[str, Any]:
        """Analyze safety of NCPGOV module consolidation."""
        ncpgov_modules = {k: v for k, v in module_dependencies.items() 
                         if k.startswith('ncpgov.') or k.startswith('ncpgov_module.')}
        
        # Similar analysis as NCP
        conflicts = []
        ncpgov_functions = set()
        ncpgov_module_functions = set()
        
        for module_key, dependency in ncpgov_modules.items():
            functions = {fc.function_name for fc in dependency.function_calls}
            
            if module_key.startswith('ncpgov.'):
                ncpgov_functions.update(functions)
            else:
                ncpgov_module_functions.update(functions)
        
        overlapping_functions = ncpgov_functions.intersection(ncpgov_module_functions)
        
        return {
            'total_modules': len(ncpgov_modules),
            'ncpgov_modules': [k for k in ncpgov_modules.keys() if k.startswith('ncpgov.')],
            'ncpgov_module_modules': [k for k in ncpgov_modules.keys() if k.startswith('ncpgov_module.')],
            'overlapping_functions': list(overlapping_functions),
            'consolidation_safe': len(overlapping_functions) == 0,
            'risk_level': 'low' if len(overlapping_functions) == 0 else 'medium',
            'recommendations': self._generate_ncpgov_consolidation_recommendations(ncpgov_modules)
        }
    
    def _analyze_import_impact(self, module_dependencies: Dict[str, ModuleDependency]) -> Dict[str, Any]:
        """Analyze the impact of changing import statements."""
        import_impact = {
            'files_to_update': [],
            'import_statements_to_change': 0,
            'potential_breaking_changes': []
        }
        
        # Find all files that import the modules being consolidated
        for module_key, dependency in module_dependencies.items():
            if module_key.startswith(('ncp.', 'ncp_module.', 'ncpgov.', 'ncpgov_module.')):
                # This module will be moved, so imports need to be updated
                import_impact['files_to_update'].append(module_key)
                import_impact['import_statements_to_change'] += 1
        
        return import_impact
    
    def _analyze_test_impact(self) -> Dict[str, Any]:
        """Analyze the impact on test files."""
        test_impact = {
            'test_files_to_update': [],
            'test_directories_affected': [],
            'estimated_test_changes': 0
        }
        
        # Find test files that might be affected
        test_dir = self.project_root / 'tests'
        if test_dir.exists():
            for test_file in test_dir.rglob('*.py'):
                if 'ncp' in test_file.name.lower():
                    test_impact['test_files_to_update'].append(str(test_file))
        
        return test_impact
    
    def _assess_consolidation_risks(self, module_dependencies: Dict[str, ModuleDependency]) -> Dict[str, Any]:
        """Assess overall risks of consolidation."""
        risks = {
            'high_risk_items': [],
            'medium_risk_items': [],
            'low_risk_items': [],
            'overall_risk_level': 'low',
            'mitigation_strategies': []
        }
        
        # Assess based on complexity and dependencies
        for module_key, dependency in module_dependencies.items():
            if module_key.startswith(('ncp.', 'ncp_module.', 'ncpgov.', 'ncpgov_module.')):
                risk_level = self._calculate_module_risk(dependency)
                
                risk_item = {
                    'module': module_key,
                    'risk_level': risk_level,
                    'reasons': self._get_risk_reasons(dependency)
                }
                
                if risk_level == 'high':
                    risks['high_risk_items'].append(risk_item)
                elif risk_level == 'medium':
                    risks['medium_risk_items'].append(risk_item)
                else:
                    risks['low_risk_items'].append(risk_item)
        
        # Determine overall risk level
        if risks['high_risk_items']:
            risks['overall_risk_level'] = 'high'
        elif risks['medium_risk_items']:
            risks['overall_risk_level'] = 'medium'
        
        # Generate mitigation strategies
        risks['mitigation_strategies'] = [
            'Create comprehensive backup before consolidation',
            'Test all CLI commands after each consolidation step',
            'Use gradual migration approach (one service at a time)',
            'Implement automated testing for import validation',
            'Keep rollback plan ready'
        ]
        
        return risks
    
    def _calculate_module_risk(self, dependency: ModuleDependency) -> str:
        """Calculate risk level for a module."""
        risk_score = 0
        
        # High number of dependencies increases risk
        if len(dependency.internal_dependencies) > 5:
            risk_score += 2
        elif len(dependency.internal_dependencies) > 2:
            risk_score += 1
        
        # High number of function calls increases risk
        if len(dependency.function_calls) > 20:
            risk_score += 2
        elif len(dependency.function_calls) > 10:
            risk_score += 1
        
        # CLI usage increases importance (and risk if broken)
        if dependency.cli_commands_using:
            risk_score += 1
        
        if risk_score >= 4:
            return 'high'
        elif risk_score >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _get_risk_reasons(self, dependency: ModuleDependency) -> List[str]:
        """Get reasons for the risk level."""
        reasons = []
        
        if len(dependency.internal_dependencies) > 5:
            reasons.append(f"High number of internal dependencies ({len(dependency.internal_dependencies)})")
        
        if len(dependency.function_calls) > 20:
            reasons.append(f"High number of function calls ({len(dependency.function_calls)})")
        
        if dependency.cli_commands_using:
            reasons.append(f"Used by CLI commands: {', '.join(dependency.cli_commands_using)}")
        
        return reasons
    
    def _generate_ncp_consolidation_recommendations(self, ncp_modules: Dict[str, ModuleDependency]) -> List[str]:
        """Generate specific recommendations for NCP consolidation."""
        recommendations = [
            "Consolidate ncp.ec2, ncp.s3, ncp.vpc, ncp.sg with ncp_module.rds into unified structure",
            "Preserve client.py functionality from ncp_module",
            "Update CLI imports to use new unified module paths",
            "Test each service consolidation individually before proceeding to next"
        ]
        
        return recommendations
    
    def _generate_ncpgov_consolidation_recommendations(self, ncpgov_modules: Dict[str, ModuleDependency]) -> List[str]:
        """Generate specific recommendations for NCPGOV consolidation."""
        recommendations = [
            "Consolidate ncpgov.ec2, ncpgov.s3, ncpgov.vpc, ncpgov.sg with ncpgov_module.rds into unified structure",
            "Preserve client.py functionality from ncpgov_module",
            "Update CLI imports to use new unified module paths",
            "Maintain security features specific to government cloud requirements"
        ]
        
        return recommendations
    
    def save_dependency_map(self, dependency_map: DependencyMap, output_file: Path) -> None:
        """Save the dependency map to a JSON file."""
        print(f"💾 Saving dependency map to: {output_file}")
        
        # Convert to serializable format
        serializable_data = {
            'timestamp': dependency_map.timestamp,
            'project_root': dependency_map.project_root,
            'modules': {
                k: {
                    'module_path': v.module_path,
                    'imports': v.imports,
                    'function_calls': [asdict(fc) for fc in v.function_calls],
                    'internal_dependencies': list(v.internal_dependencies),
                    'external_dependencies': list(v.external_dependencies),
                    'cli_commands_using': v.cli_commands_using
                }
                for k, v in dependency_map.modules.items()
            },
            'cli_command_mappings': dependency_map.cli_command_mappings,
            'cross_platform_dependencies': dependency_map.cross_platform_dependencies,
            'potential_conflicts': dependency_map.potential_conflicts,
            'consolidation_safety_analysis': dependency_map.consolidation_safety_analysis
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, indent=2, ensure_ascii=False)
        
        print("✅ Dependency map saved successfully")
    
    def print_dependency_summary(self, dependency_map: DependencyMap) -> None:
        """Print a summary of the dependency analysis."""
        print("\n" + "="*60)
        print("🗺️  DEPENDENCY MAPPING SUMMARY")
        print("="*60)
        print(f"📅 Analysis Date: {dependency_map.timestamp}")
        print(f"📁 Project Root: {dependency_map.project_root}")
        print(f"📦 Total Modules Analyzed: {len(dependency_map.modules)}")
        
        # Platform breakdown
        platform_counts = {}
        for module_key in dependency_map.modules.keys():
            platform = self._get_module_platform(module_key)
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        print(f"\n🔍 Platform Module Breakdown:")
        for platform, count in platform_counts.items():
            print(f"  • {platform.upper()}: {count} modules")
        
        # Cross-platform dependencies
        if dependency_map.cross_platform_dependencies:
            print(f"\n🔗 Cross-Platform Dependencies:")
            for module, deps in dependency_map.cross_platform_dependencies.items():
                print(f"  • {module} → {deps}")
        
        # Potential conflicts
        if dependency_map.potential_conflicts:
            print(f"\n⚠️  Potential Conflicts ({len(dependency_map.potential_conflicts)}):")
            for conflict in dependency_map.potential_conflicts:
                print(f"  • {conflict['type']}: {conflict.get('function_name', 'N/A')} (severity: {conflict['severity']})")
        
        # Safety analysis
        safety = dependency_map.consolidation_safety_analysis
        print(f"\n🛡️  Consolidation Safety Analysis:")
        
        if 'ncp_consolidation' in safety:
            ncp_safety = safety['ncp_consolidation']
            print(f"  • NCP Consolidation: {'✅ Safe' if ncp_safety.get('consolidation_safe') else '⚠️ Needs Review'}")
            print(f"    - Risk Level: {ncp_safety.get('risk_level', 'unknown')}")
        
        if 'ncpgov_consolidation' in safety:
            ncpgov_safety = safety['ncpgov_consolidation']
            print(f"  • NCPGOV Consolidation: {'✅ Safe' if ncpgov_safety.get('consolidation_safe') else '⚠️ Needs Review'}")
            print(f"    - Risk Level: {ncpgov_safety.get('risk_level', 'unknown')}")
        
        if 'risk_assessment' in safety:
            risk_assessment = safety['risk_assessment']
            print(f"  • Overall Risk Level: {risk_assessment.get('overall_risk_level', 'unknown')}")
            
            high_risk = len(risk_assessment.get('high_risk_items', []))
            medium_risk = len(risk_assessment.get('medium_risk_items', []))
            low_risk = len(risk_assessment.get('low_risk_items', []))
            
            print(f"    - High Risk Items: {high_risk}")
            print(f"    - Medium Risk Items: {medium_risk}")
            print(f"    - Low Risk Items: {low_risk}")
        
        print("\n" + "="*60)


def main():
    """Main function to run dependency mapping."""
    parser = argparse.ArgumentParser(
        description="Dependency Mapping System",
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
        help='Output directory for dependency map'
    )
    
    args = parser.parse_args()
    
    # Ensure project root exists
    if not args.project_root.exists():
        print(f"❌ Project root does not exist: {args.project_root}")
        sys.exit(1)
    
    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        print("🚀 Starting Dependency Mapping System")
        print(f"📁 Project Root: {args.project_root}")
        print(f"📊 Output Directory: {args.output_dir}")
        
        mapper = DependencyMapper(args.project_root)
        dependency_map = mapper.create_dependency_map()
        
        # Save dependency map
        map_file = args.output_dir / f"dependency_map_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        mapper.save_dependency_map(dependency_map, map_file)
        
        # Print summary
        mapper.print_dependency_summary(dependency_map)
        
        print(f"\n🎉 Dependency mapping completed successfully!")
        print(f"📊 Dependency Map: {map_file}")
        
        print(f"\n📋 Next Steps:")
        print(f"  1. Review the dependency map: {map_file}")
        print(f"  2. Address any high-risk conflicts identified")
        print(f"  3. Use this analysis to guide safe module consolidation")
        
    except Exception as e:
        print(f"❌ Error during dependency mapping: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()