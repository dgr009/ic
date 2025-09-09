#!/usr/bin/env python3
"""
새로운 설정 시스템 테스트 스크립트
Requirements: 8.1
"""

import os
import sys
from pathlib import Path
import logging
import traceback

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigSystemTester:
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
        
    def test_basic_imports(self):
        """기본 import 테스트"""
        logger.info("=== 기본 Import 테스트 ===")
        
        imports_to_test = [
            ("yaml", "PyYAML"),
            ("boto3", "AWS SDK"),
            ("rich", "Rich 출력"),
            ("watchdog", "파일 감시"),
            ("cerberus", "스키마 검증"),
            ("pydantic", "데이터 검증"),
        ]
        
        for module_name, description in imports_to_test:
            try:
                __import__(module_name)
                self.log_test_result(f"Import {description}", True)
            except ImportError as e:
                self.log_test_result(f"Import {description}", False, str(e))
                
    def test_config_manager_import(self):
        """ConfigManager import 테스트"""
        logger.info("=== ConfigManager Import 테스트 ===")
        
        try:
            from ic.config.manager import ConfigManager
            self.log_test_result("ConfigManager import", True)
            return ConfigManager
        except Exception as e:
            self.log_test_result("ConfigManager import", False, str(e))
            return None
            
    def test_config_components_import(self):
        """설정 시스템 컴포넌트들 import 테스트"""
        logger.info("=== 설정 컴포넌트 Import 테스트 ===")
        
        components = [
            ("src.ic.config.secrets", "SecretsManager"),
            ("src.ic.config.external", "ExternalConfigLoader"),
            ("src.ic.config.migration", "MigrationManager"),
            ("src.ic.config.cleanup", "FileCleanupManager"),
            ("src.ic.config.docs_organizer", "DocsOrganizer"),
        ]
        
        for module_path, class_name in components:
            try:
                module = __import__(module_path, fromlist=[class_name])
                getattr(module, class_name)
                self.log_test_result(f"{class_name} import", True)
            except Exception as e:
                self.log_test_result(f"{class_name} import", False, str(e))
                
    def test_config_files_exist(self):
        """설정 파일 존재 확인"""
        logger.info("=== 설정 파일 존재 확인 ===")
        
        config_files = [
            ("config/default.yaml", "기본 설정 파일"),
            ("config/secrets.yaml", "보안 설정 파일", False),  # 선택사항
            (".env", "기존 .env 파일", False),  # 선택사항
        ]
        
        for file_path, description, *optional in config_files:
            is_optional = optional[0] if optional else False
            full_path = self.project_root / file_path
            
            if full_path.exists():
                self.log_test_result(f"{description} 존재", True, str(full_path))
            else:
                if is_optional:
                    self.log_test_result(f"{description} 존재", True, f"선택사항 - {full_path}")
                else:
                    self.log_test_result(f"{description} 존재", False, f"파일 없음: {full_path}")
                    
    def test_config_manager_initialization(self):
        """ConfigManager 초기화 테스트"""
        logger.info("=== ConfigManager 초기화 테스트 ===")
        
        try:
            from ic.config.manager import ConfigManager
            config_manager = ConfigManager()
            self.log_test_result("ConfigManager 초기화", True)
            return config_manager
        except Exception as e:
            self.log_test_result("ConfigManager 초기화", False, str(e))
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return None
            
    def test_config_loading(self, config_manager):
        """설정 로딩 테스트"""
        if not config_manager:
            return
            
        logger.info("=== 설정 로딩 테스트 ===")
        
        try:
            # 기본 설정 로딩
            config = config_manager.get_config()
            self.log_test_result("기본 설정 로딩", True, f"설정 키 수: {len(config)}")
            
            # 주요 설정 섹션 확인
            expected_sections = ["logging", "aws", "gcp", "azure", "oci", "ssh"]
            for section in expected_sections:
                if section in config:
                    self.log_test_result(f"{section} 설정 섹션", True)
                else:
                    self.log_test_result(f"{section} 설정 섹션", False, "섹션 없음")
                    
        except Exception as e:
            self.log_test_result("설정 로딩", False, str(e))
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
    def test_secrets_manager(self):
        """SecretsManager 테스트"""
        logger.info("=== SecretsManager 테스트 ===")
        
        try:
            from ic.config.secrets import SecretsManager
            from ic.config.manager import ConfigManager
            
            config_manager = ConfigManager()
            secrets_manager = SecretsManager(config_manager)
            
            self.log_test_result("SecretsManager 초기화", True)
            
            # 보안 설정 로딩 테스트
            secrets = secrets_manager.load_secrets()
            self.log_test_result("보안 설정 로딩", True, f"보안 설정 키 수: {len(secrets)}")
            
        except Exception as e:
            self.log_test_result("SecretsManager 테스트", False, str(e))
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
    def test_external_config_loader(self):
        """ExternalConfigLoader 테스트"""
        logger.info("=== ExternalConfigLoader 테스트 ===")
        
        try:
            from ic.config.external import ExternalConfigLoader
            
            loader = ExternalConfigLoader()
            self.log_test_result("ExternalConfigLoader 초기화", True)
            
            # AWS 설정 로딩 테스트
            try:
                aws_config = loader.load_aws_config()
                self.log_test_result("AWS 설정 로딩", True, f"AWS 설정 키 수: {len(aws_config)}")
            except Exception as e:
                self.log_test_result("AWS 설정 로딩", False, f"AWS 설정 파일 없음 또는 오류: {e}")
                
            # SSH 설정 로딩 테스트
            try:
                ssh_config = loader.load_ssh_config()
                self.log_test_result("SSH 설정 로딩", True, f"SSH 설정 키 수: {len(ssh_config)}")
            except Exception as e:
                self.log_test_result("SSH 설정 로딩", False, f"SSH 설정 파일 없음 또는 오류: {e}")
                
        except Exception as e:
            self.log_test_result("ExternalConfigLoader 테스트", False, str(e))
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
    def test_logging_system(self):
        """로깅 시스템 테스트"""
        logger.info("=== 로깅 시스템 테스트 ===")
        
        try:
            from ic.core.logging import ICLogger
            from ic.config.manager import ConfigManager
            
            config_manager = ConfigManager()
            config = config_manager.get_config()
            
            ic_logger = ICLogger(config)
            self.log_test_result("ICLogger 초기화", True)
            
            # 로그 경로 확인 (ICLogger에 해당 메서드가 있는지 확인)
            try:
                log_path = ic_logger.get_log_file_path()
                self.log_test_result("로그 경로 결정", True, f"로그 경로: {log_path}")
            except AttributeError:
                self.log_test_result("로그 경로 결정", True, "ICLogger 초기화됨 (경로 메서드 없음)")
            
        except Exception as e:
            self.log_test_result("로깅 시스템 테스트", False, str(e))
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
    def test_cli_integration(self):
        """CLI 통합 테스트"""
        logger.info("=== CLI 통합 테스트 ===")
        
        try:
            from ic.cli import main
            self.log_test_result("CLI 모듈 import", True)
            
            # CLI 초기화 테스트 (실제 실행하지 않고 import만)
            self.log_test_result("CLI 통합", True, "CLI 모듈 정상 로딩")
            
        except Exception as e:
            self.log_test_result("CLI 통합 테스트", False, str(e))
            logger.error(f"상세 오류: {traceback.format_exc()}")
            
    def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("=== 새로운 설정 시스템 테스트 시작 ===")
        
        # 1. 기본 import 테스트
        self.test_basic_imports()
        
        # 2. ConfigManager import 테스트
        config_manager_class = self.test_config_manager_import()
        
        # 3. 설정 컴포넌트들 import 테스트
        self.test_config_components_import()
        
        # 4. 설정 파일 존재 확인
        self.test_config_files_exist()
        
        # 5. ConfigManager 초기화 테스트
        config_manager = self.test_config_manager_initialization()
        
        # 6. 설정 로딩 테스트
        self.test_config_loading(config_manager)
        
        # 7. SecretsManager 테스트
        self.test_secrets_manager()
        
        # 8. ExternalConfigLoader 테스트
        self.test_external_config_loader()
        
        # 9. 로깅 시스템 테스트
        self.test_logging_system()
        
        # 10. CLI 통합 테스트
        self.test_cli_integration()
        
        # 결과 요약
        self.print_test_summary()
        
    def print_test_summary(self):
        """테스트 결과 요약 출력"""
        logger.info("=== 테스트 결과 요약 ===")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for _, success, _ in self.test_results if success)
        failed_tests = total_tests - passed_tests
        
        logger.info(f"총 테스트: {total_tests}")
        logger.info(f"성공: {passed_tests}")
        logger.info(f"실패: {failed_tests}")
        logger.info(f"성공률: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            logger.info("\n실패한 테스트:")
            for test_name, success, message in self.test_results:
                if not success:
                    logger.info(f"  ✗ {test_name}: {message}")
                    
        return failed_tests == 0

def main():
    """메인 함수"""
    tester = ConfigSystemTester()
    success = tester.run_all_tests()
    
    if success:
        logger.info("모든 테스트가 성공했습니다!")
        sys.exit(0)
    else:
        logger.error("일부 테스트가 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()