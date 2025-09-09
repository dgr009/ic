#!/usr/bin/env python3

import os
import json
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from ic.config.manager import ConfigManager

console = Console()

class GCPConfigValidator:
    """GCP 환경 변수 설정 검증 및 도움말 제공"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.suggestions = []
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.gcp_config = self.config.get('gcp', {})
    
    def validate_config(self) -> Tuple[bool, List[str], List[str]]:
        """GCP 설정을 검증하고 오류/경고/제안사항을 반환"""
        self.errors.clear()
        self.warnings.clear()
        self.suggestions.clear()
        
        # MCP 설정 검증
        self._validate_mcp_config()
        
        # 인증 설정 검증
        self._validate_authentication()
        
        # 프로젝트 설정 검증
        self._validate_project_config()
        
        # 지역 설정 검증
        self._validate_regional_config()
        
        # 성능 설정 검증
        self._validate_performance_config()
        
        # 서비스 API 설정 검증
        self._validate_service_config()
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_mcp_config(self):
        """MCP 서버 설정 검증"""
        mcp_config = self.config.get('mcp', {})
        mcp_enabled = str(mcp_config.get('gcp_enabled', os.getenv('MCP_GCP_ENABLED', 'false'))).lower() == 'true'
        prefer_mcp = str(self.gcp_config.get('prefer_mcp', os.getenv('GCP_PREFER_MCP', 'true'))).lower() == 'true'
        
        if prefer_mcp and not mcp_enabled:
            self.warnings.append(
                "GCP_PREFER_MCP is true but MCP_GCP_ENABLED is false. "
                "Will fallback to direct API access."
            )
        
        if mcp_enabled:
            endpoint = mcp_config.get('gcp_endpoint', os.getenv('MCP_GCP_ENDPOINT'))
            if not endpoint:
                self.errors.append(
                    "MCP_GCP_ENDPOINT is required when MCP_GCP_ENABLED=true"
                )
            
            auth_method = mcp_config.get('gcp_auth_method', os.getenv('MCP_GCP_AUTH_METHOD'))
            if auth_method and auth_method not in ['service_account', 'adc', 'gcloud']:
                self.errors.append(
                    f"Invalid MCP_GCP_AUTH_METHOD: {auth_method}. "
                    "Valid options: service_account, adc, gcloud"
                )
    
    def _validate_authentication(self):
        """인증 설정 검증"""
        service_account_path = self.gcp_config.get('service_account_key_path', os.getenv('GCP_SERVICE_ACCOUNT_KEY_PATH'))
        service_account_key = self.gcp_config.get('service_account_key', os.getenv('GCP_SERVICE_ACCOUNT_KEY'))
        google_credentials = self.gcp_config.get('google_application_credentials', os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
        
        auth_methods = [service_account_path, service_account_key, google_credentials]
        available_methods = [method for method in auth_methods if method]
        
        if not available_methods:
            self.warnings.append(
                "No GCP authentication method configured. "
                "Will attempt to use gcloud CLI credentials as fallback."
            )
            self.suggestions.append(
                "Configure at least one authentication method:\n"
                "  • GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json\n"
                "  • GCP_SERVICE_ACCOUNT_KEY='{\"type\": \"service_account\", ...}'\n"
                "  • GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json"
            )
        
        # 서비스 계정 키 파일 경로 검증
        if service_account_path:
            expanded_path = os.path.expanduser(service_account_path)
            if not os.path.exists(expanded_path):
                self.errors.append(
                    f"GCP service account key file not found: {expanded_path}"
                )
            elif not os.access(expanded_path, os.R_OK):
                self.errors.append(
                    f"GCP service account key file not readable: {expanded_path}"
                )
        
        # 서비스 계정 키 JSON 검증
        if service_account_key:
            try:
                key_data = json.loads(service_account_key)
                required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
                missing_fields = [field for field in required_fields if field not in key_data]
                if missing_fields:
                    self.errors.append(
                        f"GCP service account key missing required fields: {', '.join(missing_fields)}"
                    )
            except json.JSONDecodeError:
                self.errors.append("GCP_SERVICE_ACCOUNT_KEY is not valid JSON")
    
    def _validate_project_config(self):
        """프로젝트 설정 검증"""
        projects = self.gcp_config.get('projects', os.getenv('GCP_PROJECTS'))
        default_project = self.gcp_config.get('default_project', os.getenv('GCP_DEFAULT_PROJECT'))
        
        if projects:
            project_list = [p.strip() for p in projects.split(',')]
            # 프로젝트 ID 형식 검증 (간단한 검증)
            for project in project_list:
                if not project or not project.replace('-', '').replace('_', '').isalnum():
                    self.warnings.append(
                        f"Project ID '{project}' may not be valid. "
                        "GCP project IDs should contain only lowercase letters, numbers, and hyphens."
                    )
        
        if default_project and projects:
            project_list = [p.strip() for p in projects.split(',')]
            if default_project not in project_list:
                self.warnings.append(
                    f"GCP_DEFAULT_PROJECT '{default_project}' is not in GCP_PROJECTS list"
                )
    
    def _validate_regional_config(self):
        """지역 설정 검증"""
        regions = self.gcp_config.get('regions', os.getenv('GCP_REGIONS'))
        zones = self.gcp_config.get('zones', os.getenv('GCP_ZONES'))
        
        if regions:
            region_list = [r.strip() for r in regions.split(',')]
            # 간단한 지역 형식 검증
            for region in region_list:
                if not region or len(region.split('-')) < 2:
                    self.warnings.append(
                        f"Region '{region}' may not be valid. "
                        "GCP regions should be in format like 'us-central1'"
                    )
        
        if zones:
            zone_list = [z.strip() for z in zones.split(',')]
            # 간단한 존 형식 검증
            for zone in zone_list:
                if not zone or len(zone.split('-')) < 3:
                    self.warnings.append(
                        f"Zone '{zone}' may not be valid. "
                        "GCP zones should be in format like 'us-central1-a'"
                    )
    
    def _validate_performance_config(self):
        """성능 설정 검증"""
        max_workers = str(self.gcp_config.get('max_workers', os.getenv('GCP_MAX_WORKERS', '10')))
        request_timeout = str(self.gcp_config.get('request_timeout', os.getenv('GCP_REQUEST_TIMEOUT', '30')))
        retry_attempts = str(self.gcp_config.get('retry_attempts', os.getenv('GCP_RETRY_ATTEMPTS', '3')))
        
        try:
            workers = int(max_workers)
            if workers < 1 or workers > 50:
                self.warnings.append(
                    f"GCP_MAX_WORKERS={workers} may be inefficient. "
                    "Recommended range: 1-50"
                )
        except ValueError:
            self.errors.append(f"GCP_MAX_WORKERS must be a number, got: {max_workers}")
        
        try:
            timeout = int(request_timeout)
            if timeout < 5 or timeout > 300:
                self.warnings.append(
                    f"GCP_REQUEST_TIMEOUT={timeout} may cause issues. "
                    "Recommended range: 5-300 seconds"
                )
        except ValueError:
            self.errors.append(f"GCP_REQUEST_TIMEOUT must be a number, got: {request_timeout}")
        
        try:
            retries = int(retry_attempts)
            if retries < 0 or retries > 10:
                self.warnings.append(
                    f"GCP_RETRY_ATTEMPTS={retries} may be inefficient. "
                    "Recommended range: 0-10"
                )
        except ValueError:
            self.errors.append(f"GCP_RETRY_ATTEMPTS must be a number, got: {retry_attempts}")
    
    def _validate_service_config(self):
        """서비스 API 설정 검증"""
        service_configs = {
            'GCP_ENABLE_BILLING_API': 'Billing API',
            'GCP_ENABLE_COMPUTE_API': 'Compute Engine API',
            'GCP_ENABLE_CONTAINER_API': 'Kubernetes Engine API',
            'GCP_ENABLE_STORAGE_API': 'Cloud Storage API',
            'GCP_ENABLE_SQLADMIN_API': 'Cloud SQL Admin API',
            'GCP_ENABLE_CLOUDFUNCTIONS_API': 'Cloud Functions API',
            'GCP_ENABLE_RUN_API': 'Cloud Run API'
        }
        
        disabled_services = []
        for env_var, service_name in service_configs.items():
            # 환경변수 이름을 설정 키로 변환 (GCP_ENABLE_COMPUTE_API -> enable_compute_api)
            config_key = env_var.lower().replace('gcp_', '').replace('_api', '_api')
            enabled = str(self.gcp_config.get(config_key, os.getenv(env_var, 'true'))).lower() == 'true'
            if not enabled:
                disabled_services.append(service_name)
        
        if disabled_services:
            self.warnings.append(
                f"Disabled GCP services: {', '.join(disabled_services)}. "
                "These services will be skipped during queries."
            )
    
    def display_validation_results(self, is_valid: bool, errors: List[str], warnings: List[str]):
        """검증 결과를 Rich 형식으로 출력"""
        if is_valid and not warnings:
            console.print(Panel(
                "[bold green]✓ GCP configuration is valid![/bold green]",
                title="GCP Configuration Status",
                border_style="green"
            ))
            return
        
        # 오류 출력
        if errors:
            error_text = Text()
            error_text.append("Configuration Errors:\n", style="bold red")
            for i, error in enumerate(errors, 1):
                error_text.append(f"{i}. {error}\n", style="red")
            
            console.print(Panel(
                error_text,
                title="❌ GCP Configuration Errors",
                border_style="red"
            ))
        
        # 경고 출력
        if warnings:
            warning_text = Text()
            warning_text.append("Configuration Warnings:\n", style="bold yellow")
            for i, warning in enumerate(warnings, 1):
                warning_text.append(f"{i}. {warning}\n", style="yellow")
            
            console.print(Panel(
                warning_text,
                title="⚠️ GCP Configuration Warnings",
                border_style="yellow"
            ))
        
        # 제안사항 출력
        if self.suggestions:
            suggestion_text = Text()
            suggestion_text.append("Configuration Suggestions:\n", style="bold blue")
            for i, suggestion in enumerate(self.suggestions, 1):
                suggestion_text.append(f"{i}. {suggestion}\n", style="blue")
            
            console.print(Panel(
                suggestion_text,
                title="💡 GCP Configuration Suggestions",
                border_style="blue"
            ))
    
    def get_setup_instructions(self) -> str:
        """GCP 설정 가이드 반환"""
        return """
GCP Configuration Setup Guide:

1. Authentication Setup:
   Choose one of the following methods:
   
   a) Service Account Key (Recommended for production):
      - Create a service account in GCP Console
      - Download the JSON key file
      - Set: GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json
   
   b) Application Default Credentials:
      - Run: gcloud auth application-default login
      - Set: GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
   
   c) gcloud CLI (Development only):
      - Run: gcloud auth login
      - Run: gcloud config set project YOUR_PROJECT_ID

2. Project Configuration:
   - Set: GCP_PROJECTS=project-1,project-2,project-3
   - Set: GCP_DEFAULT_PROJECT=your-main-project

3. Regional Configuration (Optional):
   - Set: GCP_REGIONS=us-central1,us-east1
   - Set: GCP_ZONES=us-central1-a,us-central1-b

4. MCP Server Configuration (Recommended):
   - Set: MCP_GCP_ENABLED=true
   - Set: MCP_GCP_ENDPOINT=http://localhost:8080/gcp
   - Set: MCP_GCP_AUTH_METHOD=service_account

5. Required GCP APIs:
   Enable the following APIs in your GCP projects:
   - Compute Engine API (compute.googleapis.com)
   - Kubernetes Engine API (container.googleapis.com)
   - Cloud Storage API (storage.googleapis.com)
   - Cloud SQL Admin API (sqladmin.googleapis.com)
   - Cloud Functions API (cloudfunctions.googleapis.com)
   - Cloud Run API (run.googleapis.com)
   - Cloud Billing API (cloudbilling.googleapis.com)

For more details, see: https://cloud.google.com/docs/authentication
"""

def validate_gcp_config() -> bool:
    """GCP 설정을 검증하고 결과를 출력"""
    validator = GCPConfigValidator()
    is_valid, errors, warnings = validator.validate_config()
    validator.display_validation_results(is_valid, errors, warnings)
    
    if not is_valid:
        console.print("\n" + validator.get_setup_instructions())
    
    return is_valid

if __name__ == "__main__":
    validate_gcp_config()