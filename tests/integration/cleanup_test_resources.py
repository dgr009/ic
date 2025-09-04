#!/usr/bin/env python3
"""
Cleanup utility for GCP integration test resources.

This script helps clean up resources created during integration testing
to avoid unnecessary charges and resource limits.
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.gcp_utils import GCPAuthManager, GCPProjectManager
from tests.integration.integration_config import integration_config


class GCPResourceCleaner:
    """Utility for cleaning up GCP test resources."""
    
    def __init__(self, project_id: str):
        """Initialize resource cleaner."""
        self.project_id = project_id
        self.auth_manager = GCPAuthManager()
        self.credentials = self.auth_manager.get_credentials()
        
        if not self.credentials:
            raise ValueError("No valid GCP credentials found")
        
        self.cleanup_config = integration_config.get_cleanup_config()
        self.dry_run = False
        self.cleaned_resources = []
    
    def set_dry_run(self, dry_run: bool):
        """Set dry run mode."""
        self.dry_run = dry_run
        if dry_run:
            print("🔍 DRY RUN MODE: No resources will be actually deleted")
    
    def is_test_resource(self, resource: Dict[str, Any]) -> bool:
        """Check if a resource is a test resource based on labels."""
        if not self.cleanup_config['enabled']:
            return False
        
        resource_labels = resource.get('labels', {})
        label_filters = self.cleanup_config['label_filters']
        
        # Check if all required labels match
        for key, value in label_filters.items():
            if resource_labels.get(key) != value:
                return False
        
        return True
    
    def is_resource_old_enough(self, creation_time: str) -> bool:
        """Check if resource is old enough to be cleaned up."""
        try:
            # Parse creation time (assuming ISO format)
            created = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
            max_age = timedelta(hours=self.cleanup_config['max_age_hours'])
            
            return datetime.now(created.tzinfo) - created > max_age
        except Exception as e:
            print(f"Warning: Could not parse creation time {creation_time}: {e}")
            return False
    
    def cleanup_compute_instances(self) -> List[str]:
        """Clean up Compute Engine instances."""
        print("🔍 Checking Compute Engine instances...")
        
        try:
            from gcp.compute.info import fetch_compute_instances_direct
            instances = fetch_compute_instances_direct(self.project_id)
            
            cleaned = []
            for instance in instances:
                if (self.is_test_resource(instance) and 
                    (self.cleanup_config['force_cleanup'] or 
                     self.is_resource_old_enough(instance.get('creation_timestamp', '')))):
                    
                    if self.dry_run:
                        print(f"  [DRY RUN] Would delete instance: {instance['name']}")
                    else:
                        success = self._delete_compute_instance(instance)
                        if success:
                            cleaned.append(f"compute/instance/{instance['name']}")
                            print(f"  ✅ Deleted instance: {instance['name']}")
                        else:
                            print(f"  ❌ Failed to delete instance: {instance['name']}")
            
            return cleaned
            
        except Exception as e:
            print(f"Error cleaning up compute instances: {e}")
            return []
    
    def cleanup_vpc_networks(self) -> List[str]:
        """Clean up VPC networks."""
        print("🔍 Checking VPC networks...")
        
        try:
            from gcp.vpc.info import fetch_vpc_networks_direct
            networks = fetch_vpc_networks_direct(self.project_id)
            
            cleaned = []
            for network in networks:
                # Skip default network
                if network['name'] == 'default':
                    continue
                
                if (self.is_test_resource(network) and 
                    (self.cleanup_config['force_cleanup'] or 
                     self.is_resource_old_enough(network.get('creation_timestamp', '')))):
                    
                    if self.dry_run:
                        print(f"  [DRY RUN] Would delete network: {network['name']}")
                    else:
                        success = self._delete_vpc_network(network)
                        if success:
                            cleaned.append(f"vpc/network/{network['name']}")
                            print(f"  ✅ Deleted network: {network['name']}")
                        else:
                            print(f"  ❌ Failed to delete network: {network['name']}")
            
            return cleaned
            
        except Exception as e:
            print(f"Error cleaning up VPC networks: {e}")
            return []
    
    def cleanup_gke_clusters(self) -> List[str]:
        """Clean up GKE clusters."""
        print("🔍 Checking GKE clusters...")
        
        try:
            from gcp.gke.info import fetch_gke_clusters_direct
            clusters = fetch_gke_clusters_direct(self.project_id)
            
            cleaned = []
            for cluster in clusters:
                if (self.is_test_resource(cluster) and 
                    (self.cleanup_config['force_cleanup'] or 
                     self.is_resource_old_enough(cluster.get('creation_timestamp', '')))):
                    
                    if self.dry_run:
                        print(f"  [DRY RUN] Would delete cluster: {cluster['name']}")
                    else:
                        success = self._delete_gke_cluster(cluster)
                        if success:
                            cleaned.append(f"gke/cluster/{cluster['name']}")
                            print(f"  ✅ Deleted cluster: {cluster['name']}")
                        else:
                            print(f"  ❌ Failed to delete cluster: {cluster['name']}")
            
            return cleaned
            
        except Exception as e:
            print(f"Error cleaning up GKE clusters: {e}")
            return []
    
    def cleanup_sql_instances(self) -> List[str]:
        """Clean up Cloud SQL instances."""
        print("🔍 Checking Cloud SQL instances...")
        
        try:
            from gcp.sql.info import fetch_sql_instances_direct
            instances = fetch_sql_instances_direct(self.project_id)
            
            cleaned = []
            for instance in instances:
                if (self.is_test_resource(instance) and 
                    (self.cleanup_config['force_cleanup'] or 
                     self.is_resource_old_enough(instance.get('creation_time', '')))):
                    
                    if self.dry_run:
                        print(f"  [DRY RUN] Would delete SQL instance: {instance['name']}")
                    else:
                        success = self._delete_sql_instance(instance)
                        if success:
                            cleaned.append(f"sql/instance/{instance['name']}")
                            print(f"  ✅ Deleted SQL instance: {instance['name']}")
                        else:
                            print(f"  ❌ Failed to delete SQL instance: {instance['name']}")
            
            return cleaned
            
        except Exception as e:
            print(f"Error cleaning up SQL instances: {e}")
            return []
    
    def cleanup_storage_buckets(self) -> List[str]:
        """Clean up Cloud Storage buckets."""
        print("🔍 Checking Cloud Storage buckets...")
        
        try:
            from gcp.storage.info import fetch_storage_buckets_direct
            buckets = fetch_storage_buckets_direct(self.project_id)
            
            cleaned = []
            for bucket in buckets:
                if (self.is_test_resource(bucket) and 
                    (self.cleanup_config['force_cleanup'] or 
                     self.is_resource_old_enough(bucket.get('creation_time', '')))):
                    
                    if self.dry_run:
                        print(f"  [DRY RUN] Would delete bucket: {bucket['name']}")
                    else:
                        success = self._delete_storage_bucket(bucket)
                        if success:
                            cleaned.append(f"storage/bucket/{bucket['name']}")
                            print(f"  ✅ Deleted bucket: {bucket['name']}")
                        else:
                            print(f"  ❌ Failed to delete bucket: {bucket['name']}")
            
            return cleaned
            
        except Exception as e:
            print(f"Error cleaning up storage buckets: {e}")
            return []
    
    def _delete_compute_instance(self, instance: Dict[str, Any]) -> bool:
        """Delete a compute instance."""
        try:
            from google.cloud.compute_v1 import InstancesClient
            
            client = InstancesClient(credentials=self.credentials)
            
            operation = client.delete(
                project=self.project_id,
                zone=instance['zone'],
                instance=instance['name']
            )
            
            # Wait for operation to complete (simplified)
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"Error deleting compute instance {instance['name']}: {e}")
            return False
    
    def _delete_vpc_network(self, network: Dict[str, Any]) -> bool:
        """Delete a VPC network."""
        try:
            from google.cloud.compute_v1 import NetworksClient
            
            client = NetworksClient(credentials=self.credentials)
            
            # First delete subnets, then firewall rules, then network
            # This is a simplified implementation
            operation = client.delete(
                project=self.project_id,
                network=network['name']
            )
            
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f"Error deleting VPC network {network['name']}: {e}")
            return False
    
    def _delete_gke_cluster(self, cluster: Dict[str, Any]) -> bool:
        """Delete a GKE cluster."""
        try:
            from google.cloud.container_v1 import ClusterManagerClient
            
            client = ClusterManagerClient(credentials=self.credentials)
            
            operation = client.delete_cluster(
                project_id=self.project_id,
                zone=cluster['location'],
                cluster_id=cluster['name']
            )
            
            time.sleep(5)  # Cluster deletion takes longer
            return True
            
        except Exception as e:
            print(f"Error deleting GKE cluster {cluster['name']}: {e}")
            return False
    
    def _delete_sql_instance(self, instance: Dict[str, Any]) -> bool:
        """Delete a Cloud SQL instance."""
        try:
            from google.cloud.sql_v1 import SqlInstancesServiceClient
            
            client = SqlInstancesServiceClient(credentials=self.credentials)
            
            operation = client.delete(
                project=self.project_id,
                instance=instance['name']
            )
            
            time.sleep(5)  # SQL instance deletion takes longer
            return True
            
        except Exception as e:
            print(f"Error deleting SQL instance {instance['name']}: {e}")
            return False
    
    def _delete_storage_bucket(self, bucket: Dict[str, Any]) -> bool:
        """Delete a Cloud Storage bucket."""
        try:
            from google.cloud.storage import Client
            
            client = Client(credentials=self.credentials, project=self.project_id)
            
            bucket_obj = client.bucket(bucket['name'])
            
            # Delete all objects first
            for blob in bucket_obj.list_blobs():
                blob.delete()
            
            # Delete bucket
            bucket_obj.delete()
            
            return True
            
        except Exception as e:
            print(f"Error deleting storage bucket {bucket['name']}: {e}")
            return False
    
    def cleanup_all_resources(self) -> Dict[str, List[str]]:
        """Clean up all test resources."""
        print(f"🧹 Starting cleanup for project: {self.project_id}")
        
        if self.dry_run:
            print("🔍 DRY RUN MODE: No resources will be actually deleted")
        
        results = {}
        
        # Clean up different resource types
        if integration_config.test_compute:
            results['compute'] = self.cleanup_compute_instances()
        
        if integration_config.test_vpc:
            results['vpc'] = self.cleanup_vpc_networks()
        
        if integration_config.test_gke:
            results['gke'] = self.cleanup_gke_clusters()
        
        if integration_config.test_sql:
            results['sql'] = self.cleanup_sql_instances()
        
        if integration_config.test_storage:
            results['storage'] = self.cleanup_storage_buckets()
        
        # Collect all cleaned resources
        all_cleaned = []
        for service_resources in results.values():
            all_cleaned.extend(service_resources)
        
        self.cleaned_resources = all_cleaned
        
        return results
    
    def generate_cleanup_report(self, results: Dict[str, List[str]]):
        """Generate cleanup report."""
        total_cleaned = sum(len(resources) for resources in results.values())
        
        print("\n" + "="*60)
        print("CLEANUP REPORT")
        print("="*60)
        
        print(f"Project: {self.project_id}")
        print(f"Dry Run: {self.dry_run}")
        print(f"Total Resources Cleaned: {total_cleaned}")
        
        for service, resources in results.items():
            if resources:
                print(f"\n{service.upper()} ({len(resources)} resources):")
                for resource in resources:
                    print(f"  - {resource}")
        
        if total_cleaned == 0:
            print("\n✅ No test resources found to clean up")
        elif self.dry_run:
            print(f"\n🔍 DRY RUN: {total_cleaned} resources would be cleaned up")
        else:
            print(f"\n🧹 Successfully cleaned up {total_cleaned} resources")
        
        # Save report to file
        report_file = Path(__file__).parent / f"cleanup_report_{int(time.time())}.json"
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'project_id': self.project_id,
            'dry_run': self.dry_run,
            'total_cleaned': total_cleaned,
            'results': results,
            'config': self.cleanup_config
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n📊 Cleanup report saved to: {report_file}")


def main():
    """Main cleanup script entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Clean up GCP integration test resources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cleanup_test_resources.py --dry-run    # Show what would be deleted
  python cleanup_test_resources.py --force      # Delete all test resources
  python cleanup_test_resources.py --project my-test-project
        """
    )
    
    parser.add_argument('--project', help='GCP project ID (overrides config)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without deleting')
    parser.add_argument('--force', action='store_true', help='Force cleanup regardless of age')
    parser.add_argument('--service', choices=['compute', 'vpc', 'gke', 'sql', 'storage'], 
                       help='Clean up specific service only')
    
    args = parser.parse_args()
    
    # Determine project ID
    project_id = args.project or integration_config.project_id
    
    if not project_id:
        print("❌ No project ID specified. Use --project or set GCP_INTEGRATION_TEST_PROJECT")
        sys.exit(1)
    
    # Validate configuration
    if not integration_config.cleanup_config['enabled'] and not args.force:
        print("❌ Cleanup is disabled in configuration. Use --force to override.")
        sys.exit(1)
    
    try:
        # Initialize cleaner
        cleaner = GCPResourceCleaner(project_id)
        
        if args.dry_run:
            cleaner.set_dry_run(True)
        
        if args.force:
            cleaner.cleanup_config['force_cleanup'] = True
        
        # Perform cleanup
        if args.service:
            # Clean up specific service
            print(f"Cleaning up {args.service} resources only...")
            
            if args.service == 'compute':
                results = {'compute': cleaner.cleanup_compute_instances()}
            elif args.service == 'vpc':
                results = {'vpc': cleaner.cleanup_vpc_networks()}
            elif args.service == 'gke':
                results = {'gke': cleaner.cleanup_gke_clusters()}
            elif args.service == 'sql':
                results = {'sql': cleaner.cleanup_sql_instances()}
            elif args.service == 'storage':
                results = {'storage': cleaner.cleanup_storage_buckets()}
        else:
            # Clean up all resources
            results = cleaner.cleanup_all_resources()
        
        # Generate report
        cleaner.generate_cleanup_report(results)
        
    except KeyboardInterrupt:
        print("\n⚠️  Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()