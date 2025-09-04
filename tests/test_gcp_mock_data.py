#!/usr/bin/env python3
"""
Mock data generators for GCP services testing.

Provides realistic mock data for all GCP services to support comprehensive testing.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Any
from unittest.mock import Mock


class GCPMockDataGenerator:
    """Generator for realistic GCP mock data."""
    
    @staticmethod
    def generate_compute_instance(
        name: str = "test-instance",
        project_id: str = "test-project",
        zone: str = "us-central1-a",
        status: str = "RUNNING"
    ) -> Dict[str, Any]:
        """Generate mock Compute Engine instance data."""
        return {
            "name": name,
            "project_id": project_id,
            "zone": zone,
            "machine_type": "n1-standard-1",
            "status": status,
            "internal_ip": "10.0.0.2",
            "external_ip": "34.123.45.67" if status == "RUNNING" else "N/A",
            "disks": [
                {
                    "source": f"projects/{project_id}/zones/{zone}/disks/{name}-disk",
                    "boot": True,
                    "auto_delete": True,
                    "device_name": "persistent-disk-0"
                }
            ],
            "network_interfaces": [
                {
                    "network": f"projects/{project_id}/global/networks/default",
                    "subnetwork": f"projects/{project_id}/regions/us-central1/subnetworks/default",
                    "network_ip": "10.0.0.2",
                    "access_configs": [
                        {
                            "type": "ONE_TO_ONE_NAT",
                            "name": "External NAT",
                            "nat_ip": "34.123.45.67"
                        }
                    ] if status == "RUNNING" else []
                }
            ],
            "labels": {
                "env": "test",
                "team": "backend"
            },
            "metadata": {
                "startup-script": "#!/bin/bash\necho 'Hello World'",
                "ssh-keys": "user:ssh-rsa AAAAB3NzaC1yc2E..."
            },
            "creation_timestamp": "2023-01-01T00:00:00Z"
        }
    
    @staticmethod
    def generate_vpc_network(
        name: str = "default",
        project_id: str = "test-project",
        routing_mode: str = "REGIONAL"
    ) -> Dict[str, Any]:
        """Generate mock VPC network data."""
        return {
            "name": name,
            "project_id": project_id,
            "description": f"{name.title()} network",
            "routing_mode": routing_mode,
            "auto_create_subnetworks": name == "default",
            "subnets": [
                {
                    "name": f"{name}-subnet",
                    "ip_cidr_range": "10.0.0.0/24",
                    "region": "us-central1",
                    "gateway_address": "10.0.0.1",
                    "private_ip_google_access": True
                }
            ] if name == "default" else [],
            "firewall_rules": [
                {
                    "name": f"{name}-allow-internal",
                    "direction": "INGRESS",
                    "priority": 65534,
                    "source_ranges": ["10.0.0.0/8"],
                    "allowed": [
                        {
                            "IPProtocol": "tcp",
                            "ports": ["0-65535"]
                        },
                        {
                            "IPProtocol": "udp", 
                            "ports": ["0-65535"]
                        },
                        {
                            "IPProtocol": "icmp"
                        }
                    ]
                }
            ],
            "peerings": [],
            "creation_timestamp": "2023-01-01T00:00:00Z"
        }
    
    @staticmethod
    def generate_gke_cluster(
        name: str = "test-cluster",
        project_id: str = "test-project",
        location: str = "us-central1-a",
        status: str = "RUNNING"
    ) -> Dict[str, Any]:
        """Generate mock GKE cluster data."""
        return {
            "name": name,
            "project_id": project_id,
            "location": location,
            "status": status,
            "current_master_version": "1.27.3-gke.100",
            "initial_cluster_version": "1.27.3-gke.100",
            "network": "default",
            "subnetwork": "default",
            "cluster_ipv4_cidr": "10.0.0.0/14",
            "services_ipv4_cidr": "10.4.0.0/19",
            "endpoint": "34.123.45.67",
            "node_pools": [
                {
                    "name": "default-pool",
                    "initial_node_count": 3,
                    "config": {
                        "machine_type": "e2-medium",
                        "disk_size_gb": 100,
                        "oauth_scopes": [
                            "https://www.googleapis.com/auth/cloud-platform"
                        ],
                        "image_type": "COS_CONTAINERD"
                    },
                    "autoscaling": {
                        "enabled": True,
                        "min_node_count": 1,
                        "max_node_count": 10
                    },
                    "status": "RUNNING"
                }
            ],
            "addons_config": {
                "http_load_balancing": {"disabled": False},
                "horizontal_pod_autoscaling": {"disabled": False},
                "network_policy_config": {"disabled": True}
            },
            "creation_timestamp": "2023-01-01T00:00:00Z"
        }
    
    @staticmethod
    def generate_storage_bucket(
        name: str = "test-bucket",
        project_id: str = "test-project",
        location: str = "US"
    ) -> Dict[str, Any]:
        """Generate mock Cloud Storage bucket data."""
        return {
            "name": name,
            "project_id": project_id,
            "location": location,
            "storage_class": "STANDARD",
            "versioning_enabled": False,
            "lifecycle_rules": [
                {
                    "action": {"type": "Delete"},
                    "condition": {"age": 365}
                }
            ],
            "iam_policy": {
                "bindings": [
                    {
                        "role": "roles/storage.objectViewer",
                        "members": [f"serviceAccount:test@{project_id}.iam.gserviceaccount.com"]
                    }
                ]
            },
            "object_count": 42,
            "total_size": 1024000,
            "labels": {
                "env": "test",
                "purpose": "backup"
            },
            "creation_time": "2023-01-01T00:00:00Z",
            "updated_time": "2023-01-02T00:00:00Z"
        }
    
    @staticmethod
    def generate_sql_instance(
        name: str = "test-instance",
        project_id: str = "test-project",
        region: str = "us-central1"
    ) -> Dict[str, Any]:
        """Generate mock Cloud SQL instance data."""
        return {
            "name": name,
            "project_id": project_id,
            "database_version": "POSTGRES_14",
            "tier": "db-f1-micro",
            "region": region,
            "status": "RUNNABLE",
            "ip_addresses": [
                {
                    "type": "PRIMARY",
                    "ip_address": "34.123.45.67"
                },
                {
                    "type": "PRIVATE",
                    "ip_address": "10.0.0.5"
                }
            ],
            "backup_configuration": {
                "enabled": True,
                "start_time": "03:00",
                "point_in_time_recovery_enabled": True,
                "backup_retention_settings": {
                    "retained_backups": 7
                }
            },
            "maintenance_window": {
                "hour": 4,
                "day": 7,
                "update_track": "stable"
            },
            "high_availability": True,
            "read_replicas": [f"{name}-replica-1"],
            "connection_name": f"{project_id}:{region}:{name}",
            "creation_time": "2023-01-01T00:00:00Z"
        }
    
    @staticmethod
    def generate_cloud_function(
        name: str = "test-function",
        project_id: str = "test-project",
        region: str = "us-central1"
    ) -> Dict[str, Any]:
        """Generate mock Cloud Function data."""
        return {
            "name": name,
            "project_id": project_id,
            "region": region,
            "runtime": "python39",
            "entry_point": "main",
            "trigger": {
                "event_trigger": {
                    "event_type": "providers/cloud.pubsub/eventTypes/topic.publish",
                    "resource": f"projects/{project_id}/topics/test-topic"
                }
            },
            "memory_mb": 256,
            "timeout": "60s",
            "environment_variables": {
                "ENV": "production",
                "DEBUG": "false"
            },
            "source_location": f"gs://{project_id}-functions-source/{name}.zip",
            "last_update_time": "2023-01-01T00:00:00Z",
            "status": "ACTIVE"
        }
    
    @staticmethod
    def generate_cloud_run_service(
        name: str = "test-service",
        project_id: str = "test-project",
        region: str = "us-central1"
    ) -> Dict[str, Any]:
        """Generate mock Cloud Run service data."""
        return {
            "name": name,
            "project_id": project_id,
            "region": region,
            "image": f"gcr.io/{project_id}/{name}:latest",
            "cpu_allocation": "1000m",
            "memory_allocation": "512Mi",
            "min_instances": 0,
            "max_instances": 100,
            "revisions": [
                {
                    "name": f"{name}-00001-abc",
                    "image": f"gcr.io/{project_id}/{name}:latest",
                    "traffic_percent": 100,
                    "status": "READY"
                }
            ],
            "traffic_allocation": {
                f"{name}-00001-abc": 100
            },
            "endpoint_url": f"https://{name}-abc123-uc.a.run.app",
            "last_modifier": "user@example.com",
            "creation_time": "2023-01-01T00:00:00Z"
        }
    
    @staticmethod
    def generate_load_balancer(
        name: str = "test-lb",
        project_id: str = "test-project",
        lb_type: str = "HTTP(S)"
    ) -> Dict[str, Any]:
        """Generate mock Load Balancer data."""
        return {
            "name": name,
            "project_id": project_id,
            "lb_type": lb_type,
            "frontend_config": {
                "ip_address": "34.123.45.67",
                "port": 80,
                "protocol": "HTTP"
            },
            "backend_services": [
                {
                    "name": f"{name}-backend",
                    "protocol": "HTTP",
                    "port": 80,
                    "instance_groups": [
                        f"projects/{project_id}/zones/us-central1-a/instanceGroups/test-ig"
                    ]
                }
            ],
            "health_checks": [
                {
                    "name": f"{name}-health-check",
                    "type": "HTTP",
                    "port": 80,
                    "request_path": "/health"
                }
            ],
            "ssl_certificates": [
                {
                    "name": f"{name}-ssl-cert",
                    "domains": ["example.com", "www.example.com"]
                }
            ] if lb_type == "HTTP(S)" else [],
            "ip_address": "34.123.45.67",
            "creation_timestamp": "2023-01-01T00:00:00Z"
        }
    
    @staticmethod
    def generate_firewall_rule(
        name: str = "test-firewall-rule",
        project_id: str = "test-project",
        direction: str = "INGRESS"
    ) -> Dict[str, Any]:
        """Generate mock Firewall Rule data."""
        return {
            "name": name,
            "project_id": project_id,
            "direction": direction,
            "priority": 1000,
            "network": f"projects/{project_id}/global/networks/default",
            "source_ranges": ["0.0.0.0/0"] if direction == "INGRESS" else [],
            "destination_ranges": ["0.0.0.0/0"] if direction == "EGRESS" else [],
            "target_tags": ["web-server"],
            "allowed_protocols": [
                {
                    "IPProtocol": "tcp",
                    "ports": ["80", "443"]
                }
            ],
            "denied_protocols": [],
            "logging_enabled": True,
            "creation_timestamp": "2023-01-01T00:00:00Z"
        }
    
    @staticmethod
    def generate_billing_info(
        billing_account_id: str = "012345-678901-ABCDEF",
        project_id: str = "test-project"
    ) -> Dict[str, Any]:
        """Generate mock Billing information data."""
        return {
            "billing_account_id": billing_account_id,
            "billing_account_name": "Test Billing Account",
            "projects": [project_id, f"{project_id}-dev", f"{project_id}-staging"],
            "current_month_cost": 123.45,
            "cost_by_service": {
                "Compute Engine": 45.67,
                "Cloud Storage": 12.34,
                "Cloud SQL": 23.45,
                "Kubernetes Engine": 34.56,
                "Cloud Functions": 7.43
            },
            "budgets": [
                {
                    "name": "monthly-budget",
                    "amount": 1000.00,
                    "spent": 123.45,
                    "threshold_percent": 80
                }
            ],
            "alerts": [
                {
                    "name": "budget-alert-80",
                    "threshold_percent": 80,
                    "enabled": True
                }
            ],
            "currency": "USD"
        }


class GCPMockAPIResponses:
    """Mock API responses for GCP services."""
    
    @staticmethod
    def create_mock_compute_instance():
        """Create mock Compute Engine instance object."""
        mock_instance = Mock()
        data = GCPMockDataGenerator.generate_compute_instance()
        
        mock_instance.name = data["name"]
        mock_instance.zone = f"zones/{data['zone']}"
        mock_instance.machine_type = f"machine-types/{data['machine_type']}"
        mock_instance.status = data["status"]
        mock_instance.creation_timestamp = data["creation_timestamp"]
        mock_instance.labels = data["labels"]
        
        # Mock metadata
        mock_instance.metadata = Mock()
        mock_instance.metadata.items = [
            Mock(key=k, value=v) for k, v in data["metadata"].items()
        ]
        
        # Mock network interfaces
        mock_network_interface = Mock()
        mock_network_interface.network = data["network_interfaces"][0]["network"]
        mock_network_interface.subnetwork = data["network_interfaces"][0]["subnetwork"]
        mock_network_interface.network_i_p = data["network_interfaces"][0]["network_ip"]
        
        if data["network_interfaces"][0]["access_configs"]:
            mock_access_config = Mock()
            mock_access_config.nat_i_p = data["network_interfaces"][0]["access_configs"][0]["nat_ip"]
            mock_network_interface.access_configs = [mock_access_config]
        else:
            mock_network_interface.access_configs = []
        
        mock_instance.network_interfaces = [mock_network_interface]
        
        # Mock disks
        mock_disk = Mock()
        mock_disk.source = data["disks"][0]["source"]
        mock_disk.boot = data["disks"][0]["boot"]
        mock_disk.auto_delete = data["disks"][0]["auto_delete"]
        mock_instance.disks = [mock_disk]
        
        return mock_instance
    
    @staticmethod
    def create_mock_vpc_network():
        """Create mock VPC network object."""
        mock_network = Mock()
        data = GCPMockDataGenerator.generate_vpc_network()
        
        mock_network.name = data["name"]
        mock_network.description = data["description"]
        mock_network.routing_config = Mock()
        mock_network.routing_config.routing_mode = data["routing_mode"]
        mock_network.auto_create_subnetworks = data["auto_create_subnetworks"]
        mock_network.peerings = []
        mock_network.creation_timestamp = data["creation_timestamp"]
        
        return mock_network
    
    @staticmethod
    def create_mock_gke_cluster():
        """Create mock GKE cluster object."""
        mock_cluster = Mock()
        data = GCPMockDataGenerator.generate_gke_cluster()
        
        mock_cluster.name = data["name"]
        mock_cluster.location = data["location"]
        mock_cluster.status = data["status"]
        mock_cluster.current_master_version = data["current_master_version"]
        mock_cluster.network = f"projects/{data['project_id']}/global/networks/{data['network']}"
        mock_cluster.subnetwork = f"projects/{data['project_id']}/regions/us-central1/subnetworks/{data['subnetwork']}"
        mock_cluster.cluster_ipv4_cidr = data["cluster_ipv4_cidr"]
        mock_cluster.services_ipv4_cidr = data["services_ipv4_cidr"]
        mock_cluster.endpoint = data["endpoint"]
        
        # Mock create time
        mock_cluster.create_time = Mock()
        mock_cluster.create_time.seconds = 1672531200  # 2023-01-01
        
        # Mock node pools
        mock_node_pool = Mock()
        node_pool_data = data["node_pools"][0]
        mock_node_pool.name = node_pool_data["name"]
        mock_node_pool.initial_node_count = node_pool_data["initial_node_count"]
        mock_node_pool.config = Mock()
        mock_node_pool.config.machine_type = node_pool_data["config"]["machine_type"]
        mock_node_pool.config.disk_size_gb = node_pool_data["config"]["disk_size_gb"]
        mock_node_pool.config.oauth_scopes = node_pool_data["config"]["oauth_scopes"]
        mock_node_pool.autoscaling = Mock()
        mock_node_pool.autoscaling.enabled = node_pool_data["autoscaling"]["enabled"]
        mock_node_pool.autoscaling.min_node_count = node_pool_data["autoscaling"]["min_node_count"]
        mock_node_pool.autoscaling.max_node_count = node_pool_data["autoscaling"]["max_node_count"]
        mock_node_pool.status = node_pool_data["status"]
        
        mock_cluster.node_pools = [mock_node_pool]
        
        # Mock addons config
        mock_cluster.addons_config = Mock()
        mock_cluster.addons_config.http_load_balancing = Mock()
        mock_cluster.addons_config.http_load_balancing.disabled = False
        mock_cluster.addons_config.horizontal_pod_autoscaling = Mock()
        mock_cluster.addons_config.horizontal_pod_autoscaling.disabled = False
        
        return mock_cluster


if __name__ == '__main__':
    # Example usage
    generator = GCPMockDataGenerator()
    
    # Generate sample data
    instance_data = generator.generate_compute_instance()
    network_data = generator.generate_vpc_network()
    cluster_data = generator.generate_gke_cluster()
    
    print("Sample Compute Instance:")
    print(json.dumps(instance_data, indent=2))
    
    print("\nSample VPC Network:")
    print(json.dumps(network_data, indent=2))
    
    print("\nSample GKE Cluster:")
    print(json.dumps(cluster_data, indent=2))