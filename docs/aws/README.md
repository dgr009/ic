# AWS Platform Documentation

This directory contains comprehensive documentation for the AWS (Amazon Web Services) integration.

## Available Guides

- [Installation Guide](installation.md) - How to install and set up AWS integration
- [Configuration Guide](configuration.md) - How to configure AWS credentials and settings
- [Usage Guide](usage.md) - How to use AWS commands and features
- [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions

## Services Supported

- EC2 (Elastic Compute Cloud)
- S3 (Simple Storage Service)
- VPC (Virtual Private Cloud)
- RDS (Relational Database Service)
- EKS (Elastic Kubernetes Service)
- ECS (Elastic Container Service)
- Fargate
- Load Balancers
- CloudFront
- MSK (Managed Streaming for Kafka)
- CodePipeline

## Quick Start

1. Follow the [Installation Guide](installation.md) to set up AWS integration
2. Configure your credentials using the [Configuration Guide](configuration.md)
3. Start using AWS commands as described in the [Usage Guide](usage.md)

For issues, check the [Troubleshooting Guide](troubleshooting.md) or refer to the main project documentation.

## Legacy Documentation

- [AWS Implementation Summary](AWS_IMPLEMENTATION_SUMMARY.md) - Summary of AWS module implementations
- [AWS CLI Production Guidelines](aws_cli_prd.md) - AWS CLI production guidelines

---

## AWS CLI 확장 기능 (Korean Documentation)

이 문서는 ic CLI 도구에 새롭게 추가된 AWS 기능들에 대한 사용법을 설명합니다.

### 새로 추가된 기능

#### 1. EKS 클러스터 정보 조회 (`ic aws eks info`)

Amazon EKS 클러스터의 종합적인 정보를 조회합니다.

**사용법**
```bash
# 기본 사용법
ic aws eks info

# 특정 계정과 리전 지정
ic aws eks info -a 123456789012 -r ap-northeast-2

# 클러스터 이름 필터링
ic aws eks info -n my-cluster

# JSON 형식으로 출력
ic aws eks info --output json
```

#### 2. Fargate 정보 조회 (`ic aws fargate info`)

EKS 또는 ECS Fargate 관련 정보를 조회합니다.

#### 3. ECS 정보 조회 (`ic aws ecs info/service/task`)

Amazon ECS 클러스터, 서비스, 태스크에 대한 종합적인 정보를 조회합니다.

#### 4. CodePipeline 상태 조회 (`ic aws code build/deploy`)

CodePipeline의 빌드 또는 배포 스테이지 상태를 조회합니다.

자세한 사용법은 [Usage Guide](usage.md)를 참조하세요.