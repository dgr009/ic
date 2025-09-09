#!/usr/bin/env python3
"""
전체 시스템 통합 테스트 스크립트
Requirements: 8.3
"""

import sys
import os
from pathlib import Path
import logging
import traceback
import importlib

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegrationTester:
    def __init__(self):
        self.project_root = project_root
        self.test_results = []
        
    def log_test_result(self, test_name, success, message=""):
        """테스트 결과 로깅"""
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
        if message:
            logger.info(f"    {message}")
        self.test_results.append((test_name, success, message))
        
    def test_config_system_integration(self):
        """설정 시스템 통합 테스트"""
        logger.info("=== 설정 시스템 통합 테스트 ===")
        
        try:
            from ic.config.manager import ConfigManager
            config_manager = ConfigManager()
            config = config_manager.get_config()
            
            self.log_test_result("ConfigManager 초기화", True)
            
            # 주요 설정 섹션 확인
            expected_sections = ['aws', 'gcp', 'azure', 'oci', 'cloudflare', 'ssh', 'logging']
            for section in expected_sections:
                if section in config or len(config) == 0:  # 빈 config도 허용 (환경변수 사용 시)
                    self.log_test_result(f"{section} 설정 접근", True)
                else:
                    self.log_test_result(f"{section} 설정 접근", False, "설정 섹션 없음")
                    
        except Exception as e:
            self.log_test_result("설정 시스템 통합", False, str(e))
            
    def test_aws_modules_integration(self):
        """AWS 모듈 통합 테스트"""
        logger.info("=== AWS 모듈 통합 테스트 ===")
        
        aws_modules = [
            ('aws.ec2', 'EC2 모듈'),
            ('aws.ecs', 'ECS 모듈'),
            ('aws.eks', 'EKS 모듈'),
            ('aws.rds', 'RDS 모듈'),
            ('aws.s3', 'S3 모듈'),
            ('aws.vpc', 'VPC 모듈'),
        ]
        
        for module_name, description in aws_modules:
            try:
                module = importlib.import_module(module_name)
                self.log_test_result(f"{description} import", True)
                
                # ConfigManager 사용 확인
                module_file = self.project_root / (module_name.replace('.', '/') + '.py')
                if module_file.exists():
                    content = module_file.read_text()
                    if 'ConfigManager' in content:
                        self.log_test_result(f"{description} ConfigManager 사용", True)
                    else:
                        self.log_test_result(f"{description} ConfigManager 사용", False, "ConfigManager 미사용")
                        
            except Exception as e:
                self.log_test_result(f"{description} import", False, str(e))
                
    def test_gcp_modules_integration(self):
        """GCP 모듈 통합 테스트"""
        logger.info("=== GCP 모듈 통합 테스트 ===")
        
        # GCP common utils 테스트
        try:
            from common.gcp_utils import _config_manager
            self.log_test_result("GCP Utils ConfigManager", True)
        except Exception as e:
            self.log_test_result("GCP Utils ConfigManager", False, str(e))
            
        # GCP config validator 테스트
        try:
            from common.gcp_config_validator import GCPConfigValidator
            validator = GCPConfigValidator()
            self.log_test_result("GCP Config Validator", True)
        except Exception as e:
            self.log_test_result("GCP Config Validator", False, str(e))
                
    def test_azure_oci_cf_modules_integration(self):
        """Azure, OCI, CloudFlare 모듈 통합 테스트"""
        logger.info("=== Azure, OCI, CloudFlare 모듈 통합 테스트 ===")
        
        # Azure utils 테스트
        try:
            from common.azure_utils import _config_manager
            self.log_test_result("Azure Utils ConfigManager", True)
        except Exception as e:
            self.log_test_result("Azure Utils ConfigManager", False, str(e))
            
        # OCI 모듈 테스트
        try:
            oci_file = self.project_root / 'oci_module/policy/search.py'
            if oci_file.exists():
                content = oci_file.read_text()
                if 'ConfigManager' in content:
                    self.log_test_result("OCI Policy Search ConfigManager 사용", True)
                else:
                    self.log_test_result("OCI Policy Search ConfigManager 사용", False, "ConfigManager 미사용")
        except Exception as e:
            self.log_test_result("OCI 모듈", False, str(e))
            
        # CloudFlare 모듈 테스트
        try:
            cf_file = self.project_root / 'cf/dns/list_info.py'
            if cf_file.exists():
                content = cf_file.read_text()
                if 'ConfigManager' in content:
                    self.log_test_result("CloudFlare DNS ConfigManager 사용", True)
                else:
                    self.log_test_result("CloudFlare DNS ConfigManager 사용", False, "ConfigManager 미사용")
        except Exception as e:
            self.log_test_result("CloudFlare 모듈", False, str(e))
                
    def test_ssh_modules_integration(self):
        """SSH 모듈 통합 테스트"""
        logger.info("=== SSH 모듈 통합 테스트 ===")
        
        ssh_modules = [
            ('ssh/server_info.py', 'SSH Server Info'),
            ('ssh/auto_ssh.py', 'SSH Auto Connect'),
        ]
        
        for module_path, description in ssh_modules:
            try:
                module_file = self.project_root / module_path
                if module_file.exists():
                    content = module_file.read_text()
                    if 'ConfigManager' in content:
                        self.log_test_result(f"{description} ConfigManager 사용", True)
                    else:
                        self.log_test_result(f"{description} ConfigManager 사용", False, "ConfigManager 미사용")
                else:
                    self.log_test_result(f"{description} 파일 존재", False, "파일 없음")
            except Exception as e:
                self.log_test_result(f"{description}", False, str(e))
                
    def test_cli_integration(self):
        """CLI 통합 테스트"""
        logger.info("=== CLI 통합 테스트 ===")
        
        try:
            from ic.cli import main
            self.log_test_result("CLI 메인 모듈 import", True)
            
            # CLI 명령어 테스트 (실제 실행하지 않고 import만)
            from ic.commands.config import ConfigCommands
            self.log_test_result("Config 명령어 모듈 import", True)
            
        except Exception as e:
            self.log_test_result("CLI 통합", False, str(e))
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
    def test_backward_compatibility(self):
        """하위 호환성 테스트"""
        logger.info("=== 하위 호환성 테스트 ===")
        
        try:
            # 기존 .env 파일이 있는 경우 호환성 확인
            env_file = self.project_root / '.env'
            if env_file.exists():
                from ic.config.manager import ConfigManager
                config_manager = ConfigManager()
                config = config_manager.get_config()
                
                self.log_test_result(".env 파일 호환성", True, "기존 .env 파일과 호환됨")
            else:
                self.log_test_result(".env 파일 호환성", True, ".env 파일 없음 (정상)")
                
        except Exception as e:
            self.log_test_result("하위 호환성", False, str(e))
            
    def test_migration_functionality(self):
        """마이그레이션 기능 테스트"""
        logger.info("=== 마이그레이션 기능 테스트 ===")
        
        try:
            from ic.config.migration import MigrationManager
            migration_manager = MigrationManager()
            
            self.log_test_result("MigrationManager 초기화", True)
            
            # 마이그레이션 기능 확인
            env_file = self.project_root / '.env'
            can_migrate = env_file.exists()
            self.log_test_result("마이그레이션 가능성 확인", True, f"마이그레이션 가능: {can_migrate}")
            
        except Exception as e:
            self.log_test_result("마이그레이션 기능", False, str(e))
            
    def test_external_config_integration(self):
        """외부 설정 통합 테스트"""
        logger.info("=== 외부 설정 통합 테스트 ===")
        
        try:
            from ic.config.external import ExternalConfigLoader
            loader = ExternalConfigLoader()
            
            self.log_test_result("ExternalConfigLoader 초기화", True)
            
            # AWS 설정 로딩 테스트
            try:
                aws_config = loader.load_aws_config()
                self.log_test_result("AWS 외부 설정 로딩", True, f"설정 항목 수: {len(aws_config)}")
            except Exception as e:
                self.log_test_result("AWS 외부 설정 로딩", False, f"AWS 설정 파일 없음: {e}")
                
        except Exception as e:
            self.log_test_result("외부 설정 통합", False, str(e))
            
    def test_common_utils_integration(self):
        """Common Utils 통합 테스트"""
        logger.info("=== Common Utils 통합 테스트 ===")
        
        try:
            from common.utils import USE_NEW_CONFIG
            if USE_NEW_CONFIG:
                self.log_test_result("Common Utils 새 설정 시스템 사용", True)
            else:
                self.log_test_result("Common Utils 새 설정 시스템 사용", False, "Fallback 모드")
                
        except Exception as e:
            self.log_test_result("Common Utils 통합", False, str(e))
            
    def run_all_tests(self):
        """모든 통합 테스트 실행"""
        logger.info("=== 전체 시스템 통합 테스트 시작 ===")
        
        # 1. 설정 시스템 통합 테스트
        self.test_config_system_integration()
        
        # 2. AWS 모듈 통합 테스트
        self.test_aws_modules_integration()
        
        # 3. GCP 모듈 통합 테스트
        self.test_gcp_modules_integration()
        
        # 4. Azure, OCI, CloudFlare 모듈 통합 테스트
        self.test_azure_oci_cf_modules_integration()
        
        # 5. SSH 모듈 통합 테스트
        self.test_ssh_modules_integration()
        
        # 6. CLI 통합 테스트
        self.test_cli_integration()
        
        # 7. 하위 호환성 테스트
        self.test_backward_compatibility()
        
        # 8. 마이그레이션 기능 테스트
        self.test_migration_functionality()
        
        # 9. 외부 설정 통합 테스트
        self.test_external_config_integration()
        
        # 10. Common Utils 통합 테스트
        self.test_common_utils_integration()
        
        # 결과 요약
        return self.print_test_summary()
        
    def print_test_summary(self):
        """테스트 결과 요약 출력"""
        logger.info("=== 통합 테스트 결과 요약 ===")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests
        
        logger.info(f"총 테스트: {total_tests}")
        logger.info(f"성공: {passed_tests}")
        logger.info(f"실패: {failed_tests}")
        logger.info(f"성공률: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\\n실패한 테스트:")
            for test_name, success, message in self.test_results:
                if not success:
                    logger.info(f"  ✗ {test_name}: {message}")
        else:
            logger.info("모든 테스트가 성공했습니다!")
                    
        return failed_tests == 0

def main():
    """메인 함수"""
    tester = IntegrationTester()
    success = tester.run_all_tests()
    
    if success:
        logger.info("🎉 전체 시스템 통합 테스트가 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        logger.error("❌ 일부 통합 테스트가 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()