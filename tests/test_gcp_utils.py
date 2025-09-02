#!/usr/bin/env python3
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
from google.auth.credentials import Credentials
from google.oauth2 import service_account
from google.api_core import exceptions as gcp_exceptions

# Import the modules to test
from common.gcp_utils import (
    GCPAuthManager, GCPProjectManager, GCPResourceCollector,
    get_gcp_regions, get_gcp_zones, create_gcp_client,
    format_gcp_output, check_gcp_label_compliance
)


class TestGCPAuthManager(unittest.TestCase):
    """GCPAuthManager 클래스 테스트"""
    
    def setUp(self):
        # Clear environment variables for clean testing
        with patch.dict(os.environ, {}, clear=True):
            self.auth_manager = GCPAuthManager()
        # 캐시된 credentials 초기화
        self.auth_manager._credentials = None
        self.auth_manager._project_id = None
    
    @patch.dict(os.environ, {
        'GCP_SERVICE_ACCOUNT_KEY': '{"type": "service_account", "project_id": "test-project", "private_key_id": "key123"}'
    }, clear=True)
    @patch('common.gcp_utils.service_account.Credentials.from_service_account_info')
    def test_get_credentials_service_account_json(self, mock_from_info):
        """Service Account Key (JSON) 인증 테스트"""
        mock_credentials = MagicMock(spec=Credentials)
        mock_from_info.return_value = mock_credentials
        
        # Create a fresh auth manager with the test environment
        auth_manager = GCPAuthManager()
        credentials = auth_manager.get_credentials()
        
        self.assertEqual(credentials, mock_credentials)
        self.assertEqual(auth_manager._project_id, "test-project")
        mock_from_info.assert_called_once()
    
    @patch.dict(os.environ, {
        'GCP_SERVICE_ACCOUNT_KEY_PATH': '/path/to/service-account.json'
    })
    @patch('os.path.exists')
    @patch('common.gcp_utils.service_account.Credentials.from_service_account_file')
    @patch('builtins.open', new_callable=mock_open, read_data='{"project_id": "test-project"}')
    def test_get_credentials_service_account_file(self, mock_file, mock_from_file, mock_exists):
        """Service Account Key Path 인증 테스트"""
        mock_exists.return_value = True
        mock_credentials = MagicMock(spec=Credentials)
        mock_from_file.return_value = mock_credentials
        
        credentials = self.auth_manager.get_credentials()
        
        self.assertEqual(credentials, mock_credentials)
        self.assertEqual(self.auth_manager._project_id, "test-project")
        mock_from_file.assert_called_once_with('/path/to/service-account.json')
    
    @patch('common.gcp_utils.default')
    def test_get_credentials_application_default(self, mock_default):
        """Application Default Credentials 인증 테스트"""
        mock_credentials = MagicMock(spec=Credentials)
        mock_default.return_value = (mock_credentials, "default-project")
        
        credentials = self.auth_manager.get_credentials()
        
        self.assertEqual(credentials, mock_credentials)
        self.assertEqual(self.auth_manager._project_id, "default-project")
        mock_default.assert_called_once()
    
    @patch('common.gcp_utils.default')
    def test_get_credentials_failure(self, mock_default):
        """인증 실패 테스트"""
        mock_default.side_effect = Exception("Authentication failed")
        
        credentials = self.auth_manager.get_credentials()
        
        self.assertIsNone(credentials)
    
    @patch.dict(os.environ, {'GCP_DEFAULT_PROJECT': 'env-project'}, clear=True)
    def test_get_default_project_id_from_env(self):
        """환경변수에서 기본 프로젝트 ID 가져오기 테스트"""
        # Create a fresh auth manager with the test environment
        auth_manager = GCPAuthManager()
        project_id = auth_manager.get_default_project_id()
        self.assertEqual(project_id, 'env-project')
    
    @patch('common.gcp_utils.ProjectsClient')
    def test_validate_credentials_success(self, mock_client_class):
        """인증 검증 성공 테스트"""
        mock_credentials = MagicMock(spec=Credentials)
        self.auth_manager._credentials = mock_credentials
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search_projects.return_value = []
        
        result = self.auth_manager.validate_credentials()
        
        self.assertTrue(result)
        mock_client.search_projects.assert_called_once()
    
    @patch('common.gcp_utils.ProjectsClient')
    def test_validate_credentials_failure(self, mock_client_class):
        """인증 검증 실패 테스트"""
        mock_credentials = MagicMock(spec=Credentials)
        self.auth_manager._credentials = mock_credentials
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search_projects.side_effect = gcp_exceptions.PermissionDenied("Access denied")
        
        result = self.auth_manager.validate_credentials()
        
        self.assertFalse(result)


class TestGCPProjectManager(unittest.TestCase):
    """GCPProjectManager 클래스 테스트"""
    
    def setUp(self):
        self.auth_manager = MagicMock(spec=GCPAuthManager)
        self.project_manager = GCPProjectManager(self.auth_manager)
    
    @patch('common.gcp_utils.ProjectsClient')
    def test_discover_projects_success(self, mock_client_class):
        """프로젝트 발견 성공 테스트"""
        mock_credentials = MagicMock(spec=Credentials)
        self.auth_manager.get_credentials.return_value = mock_credentials
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock project data
        mock_project = MagicMock()
        mock_project.project_id = "test-project-1"
        mock_project.display_name = "Test Project 1"
        mock_project.name = "projects/123456789"
        mock_project.state.name = "ACTIVE"
        mock_project.labels = {"env": "test"}
        
        mock_client.search_projects.return_value = [mock_project]
        
        projects = self.project_manager.discover_projects()
        
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].project_id, "test-project-1")
        self.assertEqual(projects[0].project_name, "Test Project 1")
        self.assertEqual(projects[0].project_number, "123456789")
        self.assertEqual(projects[0].lifecycle_state, "ACTIVE")
        self.assertEqual(projects[0].labels, {"env": "test"})
    
    @patch.dict(os.environ, {'GCP_PROJECTS': 'project-1,project-2'}, clear=True)
    def test_get_projects_from_env(self):
        """환경변수에서 프로젝트 목록 가져오기 테스트"""
        # Create a fresh project manager with the test environment
        auth_manager = MagicMock(spec=GCPAuthManager)
        project_manager = GCPProjectManager(auth_manager)
        projects = project_manager.get_projects()
        self.assertEqual(projects, ['project-1', 'project-2'])
    
    @patch('common.gcp_utils.ProjectsClient')
    def test_validate_project_access_success(self, mock_client_class):
        """프로젝트 접근 권한 확인 성공 테스트"""
        mock_credentials = MagicMock(spec=Credentials)
        self.auth_manager.get_credentials.return_value = mock_credentials
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_project = MagicMock()
        mock_project.state.name = "ACTIVE"
        mock_client.get_project.return_value = mock_project
        
        result = self.project_manager.validate_project_access("test-project")
        
        self.assertTrue(result)
    
    @patch('common.gcp_utils.ProjectsClient')
    def test_validate_project_access_not_found(self, mock_client_class):
        """프로젝트 접근 권한 확인 - 프로젝트 없음 테스트"""
        mock_credentials = MagicMock(spec=Credentials)
        self.auth_manager.get_credentials.return_value = mock_credentials
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.get_project.side_effect = gcp_exceptions.NotFound("Project not found")
        
        result = self.project_manager.validate_project_access("nonexistent-project")
        
        self.assertFalse(result)


class TestGCPResourceCollector(unittest.TestCase):
    """GCPResourceCollector 클래스 테스트"""
    
    def setUp(self):
        self.auth_manager = MagicMock(spec=GCPAuthManager)
        self.collector = GCPResourceCollector(self.auth_manager)
    
    def test_parallel_collect_success(self):
        """병렬 리소스 수집 성공 테스트"""
        def mock_collect_func(project_id):
            return [{"name": f"resource-{project_id}", "project_id": project_id}]
        
        projects = ["project-1", "project-2"]
        results = self.collector.parallel_collect(projects, mock_collect_func)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["project_id"], "project-1")
        self.assertEqual(results[1]["project_id"], "project-2")
    
    def test_apply_filters_name(self):
        """이름 필터 적용 테스트"""
        resources = [
            {"name": "test-instance-1", "project_id": "project-1"},
            {"name": "prod-instance-1", "project_id": "project-1"},
            {"name": "test-instance-2", "project_id": "project-2"}
        ]
        
        filters = {"name": "test"}
        filtered = self.collector.apply_filters(resources, filters)
        
        self.assertEqual(len(filtered), 2)
        self.assertTrue(all("test" in r["name"] for r in filtered))
    
    def test_apply_filters_project(self):
        """프로젝트 필터 적용 테스트"""
        resources = [
            {"name": "instance-1", "project_id": "project-1"},
            {"name": "instance-2", "project_id": "project-2"},
            {"name": "instance-3", "project_id": "project-1"}
        ]
        
        filters = {"project": "project-1"}
        filtered = self.collector.apply_filters(resources, filters)
        
        self.assertEqual(len(filtered), 2)
        self.assertTrue(all(r["project_id"] == "project-1" for r in filtered))
    
    def test_apply_filters_labels(self):
        """라벨 필터 적용 테스트"""
        resources = [
            {"name": "instance-1", "labels": {"env": "prod", "team": "backend"}},
            {"name": "instance-2", "labels": {"env": "dev", "team": "frontend"}},
            {"name": "instance-3", "labels": {"env": "prod", "team": "frontend"}}
        ]
        
        filters = {"labels": {"env": "prod"}}
        filtered = self.collector.apply_filters(resources, filters)
        
        self.assertEqual(len(filtered), 2)
        self.assertTrue(all(r["labels"]["env"] == "prod" for r in filtered))


class TestUtilityFunctions(unittest.TestCase):
    """유틸리티 함수 테스트"""
    
    @patch.dict(os.environ, {'GCP_REGIONS': 'us-central1,europe-west1'}, clear=True)
    def test_get_gcp_regions(self):
        """GCP 지역 목록 가져오기 테스트"""
        # Need to reload the module to pick up new environment variables
        import importlib
        import common.gcp_utils
        importlib.reload(common.gcp_utils)
        from common.gcp_utils import get_gcp_regions
        
        regions = get_gcp_regions()
        self.assertEqual(regions, ['us-central1', 'europe-west1'])
    
    @patch.dict(os.environ, {'GCP_ZONES': 'us-central1-a,europe-west1-b'}, clear=True)
    def test_get_gcp_zones(self):
        """GCP 존 목록 가져오기 테스트"""
        # Need to reload the module to pick up new environment variables
        import importlib
        import common.gcp_utils
        importlib.reload(common.gcp_utils)
        from common.gcp_utils import get_gcp_zones
        
        zones = get_gcp_zones()
        self.assertEqual(zones, ['us-central1-a', 'europe-west1-b'])
    
    def test_format_gcp_output_json(self):
        """JSON 출력 포맷 테스트"""
        data = {"name": "test", "value": 123}
        result = format_gcp_output(data, 'json')
        self.assertIn('"name": "test"', result)
        self.assertIn('"value": 123', result)
    
    def test_format_gcp_output_yaml(self):
        """YAML 출력 포맷 테스트"""
        data = {"name": "test", "value": 123}
        result = format_gcp_output(data, 'yaml')
        self.assertIn('name: test', result)
        self.assertIn('value: 123', result)
    
    def test_check_gcp_label_compliance_compliant(self):
        """라벨 규정 준수 확인 - 준수 테스트"""
        labels = {"env": "prod", "team": "backend", "owner": "john"}
        required_labels = ["env", "team"]
        optional_labels = ["owner", "project"]
        
        result = check_gcp_label_compliance(labels, required_labels, optional_labels)
        
        self.assertTrue(result['compliant'])
        self.assertEqual(result['missing_required'], [])
        self.assertEqual(result['missing_optional'], ["project"])
        self.assertEqual(result['label_count'], 3)
    
    def test_check_gcp_label_compliance_non_compliant(self):
        """라벨 규정 준수 확인 - 미준수 테스트"""
        labels = {"owner": "john"}
        required_labels = ["env", "team"]
        optional_labels = ["owner", "project"]
        
        result = check_gcp_label_compliance(labels, required_labels, optional_labels)
        
        self.assertFalse(result['compliant'])
        self.assertEqual(set(result['missing_required']), {"env", "team"})
        self.assertEqual(result['missing_optional'], ["project"])
        self.assertEqual(result['label_count'], 1)


if __name__ == '__main__':
    unittest.main()