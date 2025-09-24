# IC Documentation

This directory contains comprehensive documentation for the IC (Infrastructure Resource Management CLI) tool.

## Getting Started

- [Installation Guide](installation.md) - How to install IC CLI
- [User Guide](user_guide.md) - Complete user guide and tutorials
- [General Configuration](general/configuration.md) - General configuration management
- [Security](security.md) - Security best practices

## Platform-Specific Documentation

### AWS (Amazon Web Services)
- [AWS Installation](aws/installation.md) - Install and setup AWS integration
- [AWS Configuration](aws/configuration.md) - Configure AWS credentials and settings
- [AWS Usage](aws/usage.md) - How to use AWS commands
- [AWS Troubleshooting](aws/troubleshooting.md) - AWS-specific troubleshooting

### Azure (Microsoft Azure)
- [Azure Installation](azure/installation.md) - Install and setup Azure integration
- [Azure Configuration](azure/configuration.md) - Configure Azure credentials and settings
- [Azure Usage](azure/usage.md) - How to use Azure commands
- [Azure Troubleshooting](azure/troubleshooting.md) - Azure-specific troubleshooting

### GCP (Google Cloud Platform)
- [GCP Installation](gcp/installation.md) - Install and setup GCP integration
- [GCP Configuration](gcp/configuration.md) - Configure GCP credentials and settings
- [GCP Usage](gcp/usage.md) - How to use GCP commands
- [GCP Troubleshooting](gcp/troubleshooting.md) - GCP-specific troubleshooting

### NCP (Naver Cloud Platform)
- [NCP Installation](ncp/installation.md) - Install and setup NCP integration
- [NCP Configuration](ncp/configuration.md) - Configure NCP credentials and settings
- [NCP Usage](ncp/usage.md) - How to use NCP commands
- [NCP Troubleshooting](ncp/troubleshooting.md) - NCP-specific troubleshooting

### NCPGOV (Naver Cloud Platform Government)
- [NCPGOV Installation](ncpgov/installation.md) - Install and setup NCPGOV integration
- [NCPGOV Configuration](ncpgov/configuration.md) - Configure NCPGOV credentials and settings
- [NCPGOV Usage](ncpgov/usage.md) - How to use NCPGOV commands
- [NCPGOV Troubleshooting](ncpgov/troubleshooting.md) - NCPGOV-specific troubleshooting

### OCI (Oracle Cloud Infrastructure)
- [OCI Installation](oci/installation.md) - Install and setup OCI integration
- [OCI Configuration](oci/configuration.md) - Configure OCI credentials and settings
- [OCI Usage](oci/usage.md) - How to use OCI commands
- [OCI Troubleshooting](oci/troubleshooting.md) - OCI-specific troubleshooting

## Advanced Topics

- [MCP Integration](mcp_integration.md) - Model Context Protocol integration
- [Deployment](deployment.md) - Deployment strategies
- [Troubleshooting](troubleshooting.md) - General troubleshooting guide

## Migration and Updates

- [Migration Guide](migration_guide.md) - Migrating from older versions
- [Config Migration](config_migration.md) - Configuration migration guide

## Development

- [Development Documentation](development/) - For contributors

## Documentation Templates

- [Templates](_templates/) - Documentation templates for consistency

## Quick Reference

### Platform Commands
```bash
# AWS
ic aws ec2 info
ic aws s3 info

# Azure  
ic azure vm info
ic azure storage info

# GCP
ic gcp compute info
ic gcp storage info

# NCP
ic ncp ec2 info
ic ncp s3 info

# NCPGOV
ic ncpgov ec2 info
ic ncpgov s3 info

# OCI
ic oci compute info
ic oci storage info
```

### Configuration Commands
```bash
# Initialize configuration
ic config init

# Validate configuration
ic config validate

# Show configuration
ic config show
```

---

## 한국어 문서 (Korean Documentation)

### 시작하기
- [메인 README](../README.md) - 프로젝트 전체 개요 및 사용법

### AWS 기능
- [AWS 서비스 사용법](aws/README.md) - ECS, EKS, Fargate, CodePipeline 등 AWS 서비스 사용 가이드

### 개발 가이드
- [개발 환경 설정](../.cursor/rules.md) - 프로젝트 엔지니어링 핸드북 및 AI 협업 규칙

---

**Last Updated**: 2024  
**Maintainer**: IC CLI Team