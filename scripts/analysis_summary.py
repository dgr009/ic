#!/usr/bin/env python3
"""
Analysis Summary Script

This script consolidates and summarizes the CLI usage analysis and dependency mapping
results to provide actionable insights for the refactoring process.

Requirements addressed:
- Consolidate analysis results into actionable summary
- Provide clear next steps for module consolidation
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import argparse
from datetime import datetime


class AnalysisSummarizer:
    """Consolidates and summarizes analysis results."""
    
    def __init__(self, analysis_dir: Path):
        self.analysis_dir = analysis_dir
        self.cli_analysis = None
        self.dependency_map = None
        
    def load_analysis_files(self) -> bool:
        """Load the latest analysis files."""
        print("📂 Loading analysis files...")
        
        # Find the latest CLI analysis report
        cli_reports = list(self.analysis_dir.glob("cli_analysis_report_*.json"))
        if not cli_reports:
            print("❌ No CLI analysis reports found")
            return False
        
        latest_cli_report = max(cli_reports, key=lambda x: x.stat().st_mtime)
        print(f"  📊 Loading CLI analysis: {latest_cli_report.name}")
        
        with open(latest_cli_report, 'r', encoding='utf-8') as f:
            self.cli_analysis = json.load(f)
        
        # Find the latest dependency map
        dep_maps = list(self.analysis_dir.glob("dependency_map_*.json"))
        if not dep_maps:
            print("❌ No dependency maps found")
            return False
        
        latest_dep_map = max(dep_maps, key=lambda x: x.stat().st_mtime)
        print(f"  🗺️  Loading dependency map: {latest_dep_map.name}")
        
        with open(latest_dep_map, 'r', encoding='utf-8') as f:
            self.dependency_map = json.load(f)
        
        return True
    
    def generate_executive_summary(self) -> Dict[str, Any]:
        """Generate an executive summary of the analysis."""
        print("📋 Generating executive summary...")
        
        # CLI Analysis Summary
        cli_summary = {
            'total_imports': self.cli_analysis['total_imports'],
            'ncp_imports_count': len(self.cli_analysis['ncp_imports']),
            'ncpgov_imports_count': len(self.cli_analysis['ncpgov_imports']),
            'platforms_analyzed': {
                'aws': len(self.cli_analysis['aws_imports']),
                'gcp': len(self.cli_analysis['gcp_imports']),
                'oci': len(self.cli_analysis['oci_imports']),
                'azure': len(self.cli_analysis['azure_imports']),
                'ncp': len(self.cli_analysis['ncp_imports']),
                'ncpgov': len(self.cli_analysis['ncpgov_imports']),
                'other': len(self.cli_analysis['other_imports'])
            }
        }
        
        # Dependency Analysis Summary
        dep_summary = {
            'total_modules_analyzed': len(self.dependency_map['modules']),
            'cross_platform_dependencies': len(self.dependency_map['cross_platform_dependencies']),
            'potential_conflicts': len(self.dependency_map['potential_conflicts']),
            'consolidation_safety': self.dependency_map['consolidation_safety_analysis']
        }
        
        # Risk Assessment
        risk_assessment = self._assess_overall_risk()
        
        # Consolidation Recommendations
        consolidation_recs = self._generate_consolidation_recommendations()
        
        return {
            'analysis_timestamp': datetime.now().isoformat(),
            'cli_analysis_summary': cli_summary,
            'dependency_analysis_summary': dep_summary,
            'risk_assessment': risk_assessment,
            'consolidation_recommendations': consolidation_recs,
            'next_steps': self._generate_next_steps()
        }
    
    def _assess_overall_risk(self) -> Dict[str, Any]:
        """Assess the overall risk of the consolidation."""
        safety_analysis = self.dependency_map['consolidation_safety_analysis']
        
        # Extract risk levels
        ncp_risk = safety_analysis.get('ncp_consolidation', {}).get('risk_level', 'unknown')
        ncpgov_risk = safety_analysis.get('ncpgov_consolidation', {}).get('risk_level', 'unknown')
        overall_risk = safety_analysis.get('risk_assessment', {}).get('overall_risk_level', 'unknown')
        
        # Count conflicts by severity
        conflicts = self.dependency_map['potential_conflicts']
        high_severity_conflicts = len([c for c in conflicts if c.get('severity') == 'high'])
        medium_severity_conflicts = len([c for c in conflicts if c.get('severity') == 'medium'])
        
        # Determine if consolidation is safe to proceed
        safe_to_proceed = (
            ncp_risk in ['low', 'medium'] and
            ncpgov_risk in ['low', 'medium'] and
            high_severity_conflicts == 0
        )
        
        return {
            'ncp_consolidation_risk': ncp_risk,
            'ncpgov_consolidation_risk': ncpgov_risk,
            'overall_risk_level': overall_risk,
            'high_severity_conflicts': high_severity_conflicts,
            'medium_severity_conflicts': medium_severity_conflicts,
            'safe_to_proceed': safe_to_proceed,
            'risk_factors': self._identify_risk_factors()
        }
    
    def _identify_risk_factors(self) -> List[str]:
        """Identify specific risk factors."""
        risk_factors = []
        
        # Check for high number of conflicts
        conflicts_count = len(self.dependency_map['potential_conflicts'])
        if conflicts_count > 100:
            risk_factors.append(f"High number of potential conflicts ({conflicts_count})")
        
        # Check for cross-platform dependencies
        cross_deps = len(self.dependency_map['cross_platform_dependencies'])
        if cross_deps > 20:
            risk_factors.append(f"Many cross-platform dependencies ({cross_deps})")
        
        # Check consolidation safety
        safety = self.dependency_map['consolidation_safety_analysis']
        
        ncp_safety = safety.get('ncp_consolidation', {})
        if not ncp_safety.get('consolidation_safe', True):
            overlapping = len(ncp_safety.get('overlapping_functions', []))
            risk_factors.append(f"NCP modules have overlapping functions ({overlapping})")
        
        ncpgov_safety = safety.get('ncpgov_consolidation', {})
        if not ncpgov_safety.get('consolidation_safe', True):
            overlapping = len(ncpgov_safety.get('overlapping_functions', []))
            risk_factors.append(f"NCPGOV modules have overlapping functions ({overlapping})")
        
        return risk_factors
    
    def _generate_consolidation_recommendations(self) -> Dict[str, Any]:
        """Generate specific consolidation recommendations."""
        cli_recs = self.cli_analysis['consolidation_recommendations']
        
        return {
            'ncp_consolidation': {
                'current_structure': {
                    'ncp_modules': cli_recs['ncp_consolidation']['ncp_modules'],
                    'ncp_module_modules': cli_recs['ncp_consolidation']['ncp_module_modules']
                },
                'target_structure': cli_recs['ncp_consolidation']['consolidation_target'],
                'services_to_merge': cli_recs['ncp_consolidation']['services_to_merge'],
                'recommended_approach': [
                    "Create src/ic/platforms/ncp/ directory structure",
                    "Merge ncp.ec2, ncp.s3, ncp.vpc, ncp.sg with ncp_module.rds",
                    "Preserve client.py functionality from ncp_module",
                    "Update CLI imports to new unified paths",
                    "Test each service individually after consolidation"
                ]
            },
            'ncpgov_consolidation': {
                'current_structure': {
                    'ncpgov_modules': cli_recs['ncpgov_consolidation']['ncpgov_modules'],
                    'ncpgov_module_modules': cli_recs['ncpgov_consolidation']['ncpgov_module_modules']
                },
                'target_structure': cli_recs['ncpgov_consolidation']['consolidation_target'],
                'services_to_merge': cli_recs['ncpgov_consolidation']['services_to_merge'],
                'recommended_approach': [
                    "Create src/ic/platforms/ncpgov/ directory structure",
                    "Merge ncpgov.ec2, ncpgov.s3, ncpgov.vpc, ncpgov.sg with ncpgov_module.rds",
                    "Preserve client.py functionality from ncpgov_module",
                    "Maintain security features for government cloud",
                    "Update CLI imports to new unified paths",
                    "Test each service individually after consolidation"
                ]
            },
            'import_mappings': cli_recs['migration_plan']['phase_3_import_updates']['import_mappings']
        }
    
    def _generate_next_steps(self) -> List[Dict[str, Any]]:
        """Generate prioritized next steps."""
        risk_assessment = self._assess_overall_risk()
        
        steps = []
        
        # Step 1: Address high-risk items first
        if not risk_assessment['safe_to_proceed']:
            steps.append({
                'priority': 'HIGH',
                'title': 'Address High-Risk Items',
                'description': 'Resolve high-severity conflicts and overlapping functions before proceeding',
                'actions': [
                    'Review potential conflicts in dependency map',
                    'Resolve function name conflicts between ncp and ncp_module',
                    'Resolve function name conflicts between ncpgov and ncpgov_module',
                    'Test conflict resolution with isolated test cases'
                ]
            })
        
        # Step 2: Prepare for consolidation
        steps.append({
            'priority': 'HIGH',
            'title': 'Prepare Consolidation Environment',
            'description': 'Set up safe environment for module consolidation',
            'actions': [
                'Verify backup integrity and completeness',
                'Create rollback procedures and test them',
                'Set up isolated testing environment',
                'Document current CLI command outputs for comparison'
            ]
        })
        
        # Step 3: Execute NCP consolidation
        steps.append({
            'priority': 'MEDIUM',
            'title': 'Execute NCP Module Consolidation',
            'description': 'Consolidate NCP modules following the recommended approach',
            'actions': [
                'Create src/ic/platforms/ncp/ directory structure',
                'Merge ncp.ec2 into unified structure',
                'Merge ncp.s3 into unified structure', 
                'Merge ncp.vpc into unified structure',
                'Merge ncp.sg into unified structure',
                'Integrate ncp_module.rds and client.py',
                'Update CLI import statements',
                'Test all NCP CLI commands'
            ]
        })
        
        # Step 4: Execute NCPGOV consolidation
        steps.append({
            'priority': 'MEDIUM',
            'title': 'Execute NCPGOV Module Consolidation',
            'description': 'Consolidate NCPGOV modules following the recommended approach',
            'actions': [
                'Create src/ic/platforms/ncpgov/ directory structure',
                'Merge ncpgov.ec2 into unified structure',
                'Merge ncpgov.s3 into unified structure',
                'Merge ncpgov.vpc into unified structure', 
                'Merge ncpgov.sg into unified structure',
                'Integrate ncpgov_module.rds and client.py',
                'Preserve government cloud security features',
                'Update CLI import statements',
                'Test all NCPGOV CLI commands'
            ]
        })
        
        # Step 5: Validation and cleanup
        steps.append({
            'priority': 'LOW',
            'title': 'Validation and Cleanup',
            'description': 'Validate consolidation success and clean up old modules',
            'actions': [
                'Run comprehensive CLI command validation',
                'Compare outputs with pre-consolidation baseline',
                'Execute full test suite',
                'Remove old ncp/ and ncpgov/ directories',
                'Remove old ncp_module/ and ncpgov_module/ directories',
                'Update documentation to reflect new structure'
            ]
        })
        
        return steps
    
    def print_executive_summary(self, summary: Dict[str, Any]) -> None:
        """Print a formatted executive summary."""
        print("\n" + "="*80)
        print("📊 EXECUTIVE SUMMARY - CLI REFACTORING ANALYSIS")
        print("="*80)
        print(f"📅 Analysis Date: {summary['analysis_timestamp']}")
        
        # CLI Analysis Summary
        cli_sum = summary['cli_analysis_summary']
        print(f"\n🔍 CLI ANALYSIS OVERVIEW:")
        print(f"  • Total Imports Analyzed: {cli_sum['total_imports']}")
        print(f"  • NCP Imports: {cli_sum['ncp_imports_count']}")
        print(f"  • NCPGOV Imports: {cli_sum['ncpgov_imports_count']}")
        
        print(f"\n📦 PLATFORM BREAKDOWN:")
        for platform, count in cli_sum['platforms_analyzed'].items():
            print(f"  • {platform.upper()}: {count} imports")
        
        # Dependency Analysis Summary
        dep_sum = summary['dependency_analysis_summary']
        print(f"\n🗺️  DEPENDENCY ANALYSIS:")
        print(f"  • Total Modules Analyzed: {dep_sum['total_modules_analyzed']}")
        print(f"  • Cross-Platform Dependencies: {dep_sum['cross_platform_dependencies']}")
        print(f"  • Potential Conflicts: {dep_sum['potential_conflicts']}")
        
        # Risk Assessment
        risk = summary['risk_assessment']
        print(f"\n⚠️  RISK ASSESSMENT:")
        print(f"  • Overall Risk Level: {risk['overall_risk_level'].upper()}")
        print(f"  • NCP Consolidation Risk: {risk['ncp_consolidation_risk'].upper()}")
        print(f"  • NCPGOV Consolidation Risk: {risk['ncpgov_consolidation_risk'].upper()}")
        print(f"  • Safe to Proceed: {'✅ YES' if risk['safe_to_proceed'] else '❌ NO'}")
        
        if risk['risk_factors']:
            print(f"\n🚨 RISK FACTORS:")
            for factor in risk['risk_factors']:
                print(f"  • {factor}")
        
        # Consolidation Recommendations
        print(f"\n💡 CONSOLIDATION RECOMMENDATIONS:")
        ncp_rec = summary['consolidation_recommendations']['ncp_consolidation']
        print(f"  • NCP Target: {ncp_rec['target_structure']}")
        print(f"    - Services to merge: {ncp_rec['services_to_merge']}")
        
        ncpgov_rec = summary['consolidation_recommendations']['ncpgov_consolidation']
        print(f"  • NCPGOV Target: {ncpgov_rec['target_structure']}")
        print(f"    - Services to merge: {ncpgov_rec['services_to_merge']}")
        
        # Next Steps
        print(f"\n📋 PRIORITIZED NEXT STEPS:")
        for i, step in enumerate(summary['next_steps'], 1):
            priority_color = {
                'HIGH': '🔴',
                'MEDIUM': '🟡', 
                'LOW': '🟢'
            }.get(step['priority'], '⚪')
            
            print(f"\n  {i}. {priority_color} {step['title']} ({step['priority']} PRIORITY)")
            print(f"     {step['description']}")
            print(f"     Actions:")
            for action in step['actions'][:3]:  # Show first 3 actions
                print(f"       • {action}")
            if len(step['actions']) > 3:
                print(f"       • ... and {len(step['actions']) - 3} more actions")
        
        print("\n" + "="*80)
        
        # Final recommendation
        if risk['safe_to_proceed']:
            print("✅ RECOMMENDATION: Proceed with consolidation following the prioritized steps above.")
        else:
            print("⚠️  RECOMMENDATION: Address high-risk items before proceeding with consolidation.")
        
        print("📖 For detailed analysis, review the individual JSON reports in the analysis_output directory.")
        print("="*80)
    
    def save_executive_summary(self, summary: Dict[str, Any], output_file: Path) -> None:
        """Save the executive summary to a file."""
        print(f"💾 Saving executive summary to: {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print("✅ Executive summary saved successfully")


def main():
    """Main function to generate analysis summary."""
    parser = argparse.ArgumentParser(
        description="Analysis Summary Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--analysis-dir',
        type=Path,
        default=Path.cwd() / 'analysis_output',
        help='Directory containing analysis files'
    )
    
    parser.add_argument(
        '--output-file',
        type=Path,
        help='Output file for executive summary (default: analysis_dir/executive_summary_TIMESTAMP.json)'
    )
    
    args = parser.parse_args()
    
    # Set default output file if not provided
    if not args.output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        args.output_file = args.analysis_dir / f'executive_summary_{timestamp}.json'
    
    # Ensure analysis directory exists
    if not args.analysis_dir.exists():
        print(f"❌ Analysis directory does not exist: {args.analysis_dir}")
        sys.exit(1)
    
    try:
        print("🚀 Starting Analysis Summary Generation")
        print(f"📂 Analysis Directory: {args.analysis_dir}")
        print(f"📄 Output File: {args.output_file}")
        
        summarizer = AnalysisSummarizer(args.analysis_dir)
        
        # Load analysis files
        if not summarizer.load_analysis_files():
            print("❌ Failed to load analysis files")
            sys.exit(1)
        
        # Generate executive summary
        summary = summarizer.generate_executive_summary()
        
        # Print summary to console
        summarizer.print_executive_summary(summary)
        
        # Save summary to file
        summarizer.save_executive_summary(summary, args.output_file)
        
        print(f"\n🎉 Analysis summary completed successfully!")
        print(f"📄 Executive Summary: {args.output_file}")
        
    except Exception as e:
        print(f"❌ Error during analysis summary: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()