# AWS Platform Documentation

This directory contains documentation for the AWS (Amazon Web Services) integration in IC CLI.

## Available Guides

- [Installation Guide](../installation.md) - How to install and set up AWS integration
- [User & Usage Guide](../user_guide.md) - Complete command reference for AWS commands
- [Troubleshooting Guide](../troubleshooting.md) - Common issues and solutions

## Services Supported

- EC2 (Elastic Compute Cloud)
- AWS Health Dashboard (Scheduled EC2 reboot maintenance checks: `ic aws healthdashboard reboot`)
- S3 (Simple Storage Service)
- VPC & Security Groups (VPC, Subnets, Gateways, Security Group Tree view)
- RDS (Relational Database Service)
- EKS (Elastic Kubernetes Service)
- ECS (Elastic Container Service)
- Fargate Profiles
- Load Balancers (ALB/NLB with Listener Rules and Target Health)
- CloudFront Distributions
- MSK (Managed Streaming for Kafka)
- CodePipeline Status

---

## AWS CLI 주요 기능 사용법 (Korean Documentation)

### 1. AWS Health Dashboard EC2 재부팅 일정 조회 (`ic aws healthdashboard reboot`)

AWS Health API를 사용하여 EC2 인스턴스의 예정된 재부팅 유지보수 일정("EC2 instance reboot maintenance scheduled")을 다중 계정 전체에서 동시 조회합니다.

```bash
# 로컬에 설정된 전 계정/프로파일 원터치 자동 조회
ic aws healthdashboard reboot

# 명시적 전체 프로파일 조회
ic aws healthdashboard reboot -A

# 특정 계정 지정 조회
ic aws healthdashboard reboot -a com2usplatform-live,event-live

# 이미 마감(closed/RESOLVED)된 과거 일정까지 포함하여 조회
ic aws healthdashboard reboot --all-status
```

### 2. EKS 클러스터 정보 조회 (`ic aws eks info`)

```bash
ic aws eks info
ic aws eks info -a 123456789012 -r ap-northeast-2
```

### 3. Security Group 분석 및 시각화 트리 (`ic aws sg info`)

```bash
ic aws sg info
ic aws sg info -o tree
```

자세한 사용법은 [User Guide](../user_guide.md)를 참조하세요.