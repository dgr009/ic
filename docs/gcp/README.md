# GCP Platform Documentation

This directory contains documentation for the GCP (Google Cloud Platform) integration in IC CLI (v1.5.2).

---

## Available Guides

- [Installation Guide](../installation.md) - How to install and set up GCP integration
- [User & Usage Guide](../user_guide.md) - Complete command reference for GCP commands
- [Troubleshooting Guide](../troubleshooting.md) - Common issues and solutions

---

## Services Supported (v1.5.2)

| Service | Commands | Key Features |
|---|---|---|
| **Compute Engine** | `ic gcp compute info`, `ic gcp compute desc` | VM list with zone, machine type, vCPU, memory, disks, IPs, tags. Verbose 15-column view (`-v`). Full schema & dot-notation key filtering (`desc -k`, `desc -l`). |
| **Load Balancing** | `ic gcp lb info`, `ic gcp lb desc` | Global & Regional Forwarding Rules, Target Proxies, URL Maps, Backend Services, Health Checks, SSL Certs. Detailed hierarchical inspection (`desc`). |
| **Google Kubernetes Engine (GKE)** | `ic gcp gke info` | GKE clusters, versions, node pools, machine types, autoscaling, and private cluster status. |
| **Cloud Run** | `ic gcp run info` | Serverless container services, ready status, CPU/Mem allocations, min/max instances, and URLs. |
| **Cloud Functions** | `ic gcp functions info` | 1st & 2nd Gen Cloud Functions, triggers, runtimes, memory, and status. |
| **Cloud SQL** | `ic gcp sql info` | MySQL, PostgreSQL, SQL Server instances, versions, tiers, HA, and backup status. |
| **Cloud Storage (GCS)** | `ic gcp storage info` | Storage buckets, locations, storage classes, object counts, sizes, and versioning. |
| **VPC & Networking** | `ic gcp vpc info` | VPC networks, auto/custom subnets, CIDR ranges, and gateway configurations. |
| **Firewall** | `ic gcp firewall info` | Ingress and Egress firewall rules, priorities, allowed/denied protocols/ports, and target tags. |
| **Cloud DNS** | `ic gcp dns info` | Managed public and private DNS zones, nameservers, and record sets. |
| **Resource Manager (Projects)** | `ic gcp project info` | Multi-level folder resource hierarchy tree, active project indicators, and project states. |
| **Cloud Billing** | `ic gcp billing info` | Current month spend by service, budgets, and alert thresholds. |
| **Profile** | `ic gcp profile info` | Active gcloud configurations, authenticated accounts, and default project settings. |

---

## Quick Start Commands

```bash
# 1. Compute Engine VM instances
ic gcp compute info
ic gcp compute info -v                                           # 15-column verbose output
ic gcp compute desc -l                                            # Schema discovery (47+ keys)
ic gcp compute desc -k status,machine_type,internal_ip,labels.env  # Dot-notation attribute extraction

# 2. Load Balancing (ALB / NLB)
ic gcp lb info
ic gcp lb desc -l                                                 # Discover queryable LB keys (56+ keys)
ic gcp lb desc -k type,ip_address,backend_services.0.name         # Deep attribute inspection

# 3. Containers & Serverless
ic gcp gke info                                                   # GKE clusters & node pools
ic gcp run info                                                   # Cloud Run services
ic gcp functions info                                             # Cloud Functions

# 4. Storage & Databases
ic gcp storage info                                               # Cloud Storage buckets
ic gcp sql info                                                   # Cloud SQL instances

# 5. Networking & Security
ic gcp vpc info                                                   # VPC networks & subnets
ic gcp firewall info                                              # Firewall rules
ic gcp dns info                                                   # Cloud DNS managed zones

# 6. Projects & Billing
ic gcp project info                                               # Folder hierarchy tree & project states
ic gcp billing info                                               # Cost breakdown by service
ic gcp profile info                                               # gcloud CLI active configurations
```

---

## Common Options

All GCP commands support standard IC CLI options:
- `-a, --account, --project <PROJECT_ID>`: Filter by one or more GCP project IDs (comma-separated).
- `--all-projects`: Concurrently inspect all accessible GCP projects.
- `-r, --region, --regions <REGION>`: Filter by region (e.g. `asia-northeast3`).
- `-z, --zone, --zones <ZONE>`: Filter by zone (e.g. `asia-northeast3-a`).
- `-n, --name <NAME>`: Filter by resource name (partial match).
- `-o, --output {table,tree,json,yaml}`: Choose output format (Default: `table`).
- `--mock`: Run offline using built-in mock datasets for testing and verification.