#!/usr/bin/env python3
"""
마이그레이션 실행 및 검증 스크립트
Requirements: 6.1, 6.2, 6.3
"""

import sys
import os
from pathlib import Path
import logging
import shutil
import yaml
import json
import time
from typing import Dict, Any, List, Optional
import hashlib

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationExecutor:
    def __init__(self):
        self.project_root = project_root
        self.migration_log = []
        self.validation_results = []
        self.backup_dir = self.project_root / 'backup'
        self.migration_history_file = self.project_root / 'docs' / 'migration_history.md'
        
    def log_migration_step(self, step_type, description, status="success", details=None):
        """마이그레이션 단계 로깅"""
        step = {
            'timestamp': time.time(),
            'type': step_type,
            'description': description,
            'status': status,
            'details': details or {}
        }
        self.migration_log.append(step)
        
        status_icon = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        logger.info(f"{status_icon} {step_type}: {description}")
        
    def log_validation_result(self, test_name, result, details=None):
        """검증 결과 로깅"""
        validation = {
            'test_name': test_name,
            'result': result,
            'details': details or {},
            'timestamp': time.time()
        }
        self.validation_results.append(validation)
        
        status_icon = "✅" if result else "❌"
        logger.info(f"{status_icon} 검증: {test_name}")
        
    def backup_current_env(self):
        """현재 .env 파일 백업"""
        logger.info("=== 현재 .env 파일 백업 ===")
        
        env_file = self.project_root / '.env'
        if not env_file.exists():
            self.log_migration_step("Backup", ".env 파일이 존재하지 않음", "warning")
            return False
            
        # 백업 디렉토리 생성
        backup_env_dir = self.backup_dir / 'env_files'
        backup_env_dir.mkdir(parents=True, exist_ok=True)
        
        # 타임스탬프가 포함된 백업 파일명
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_file = backup_env_dir / f'.env.backup.{timestamp}'
        
        try:
            # 파일 복사
            shutil.copy2(env_file, backup_file)
            
            # 체크섬 계산
            original_checksum = self.calculate_file_checksum(env_file)
            backup_checksum = self.calculate_file_checksum(backup_file)
            
            if original_checksum == backup_checksum:
                self.log_migration_step(
                    "Backup", 
                    f".env 파일 백업 완료: {backup_file}",
                    "success",
                    {"original_checksum": original_checksum, "backup_file": str(backup_file)}
                )
                return True
            else:
                self.log_migration_step("Backup", "백업 파일 체크섬 불일치", "error")
                return False
                
        except Exception as e:
            self.log_migration_step("Backup", f".env 파일 백업 실패: {e}", "error")
            return False
            
    def calculate_file_checksum(self, file_path: Path) -> str:
        """파일 체크섬 계산"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
            
    def execute_migration(self):
        """마이그레이션 실행"""
        logger.info("=== 마이그레이션 실행 ===")
        
        try:
            from ic.config.migration import MigrationManager
            
            migration_manager = MigrationManager()
            
            # 마이그레이션 실행 (force=True로 기존 파일 덮어쓰기)
            result = migration_manager.migrate_env_to_yaml(force=True)
            
            if result:
                self.log_migration_step(
                    "Migration", 
                    "마이그레이션 성공적으로 완료",
                    "success",
                    {"config_files_created": ["config/default.yaml", "config/secrets.yaml"]}
                )
                return True
            else:
                self.log_migration_step("Migration", "마이그레이션 실패", "error")
                return False
                
        except Exception as e:
            self.log_migration_step("Migration", f"마이그레이션 실행 중 오류: {e}", "error")
            return False
            
    def validate_migrated_config(self):
        """마이그레이션된 설정 검증"""
        logger.info("=== 마이그레이션된 설정 검증 ===")
        
        # 1. 설정 파일 존재 확인
        config_files = [
            self.project_root / 'config' / 'default.yaml',
            self.project_root / 'config' / 'secrets.yaml'
        ]
        
        for config_file in config_files:
            exists = config_file.exists()
            self.log_validation_result(
                f"{config_file.name} 파일 존재",
                exists,
                {"file_path": str(config_file)}
            )
            
        # 2. YAML 파일 구문 검증
        for config_file in config_files:
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        yaml.safe_load(f)
                    self.log_validation_result(f"{config_file.name} YAML 구문", True)
                except Exception as e:
                    self.log_validation_result(
                        f"{config_file.name} YAML 구문", 
                        False, 
                        {"error": str(e)}
                    )
                    
        # 3. ConfigManager로 설정 로딩 테스트
        try:
            from ic.config.manager import ConfigManager
            config_manager = ConfigManager()
            config = config_manager.get_config()
            
            self.log_validation_result(
                "ConfigManager 설정 로딩",
                True,
                {"config_sections": list(config.keys())}
            )
            
            # 필수 섹션 확인
            required_sections = ['aws', 'gcp', 'azure', 'oci', 'cloudflare', 'ssh']
            missing_sections = []
            
            for section in required_sections:
                if section not in config:
                    missing_sections.append(section)
                    
            if missing_sections:
                self.log_validation_result(
                    "필수 설정 섹션",
                    False,
                    {"missing_sections": missing_sections}
                )
            else:
                self.log_validation_result("필수 설정 섹션", True)
                
        except Exception as e:
            self.log_validation_result(
                "ConfigManager 설정 로딩",
                False,
                {"error": str(e)}
            )
            
    def test_service_modules(self):
        """서비스 모듈 동작 테스트"""
        logger.info("=== 서비스 모듈 동작 테스트 ===")
        
        # 테스트할 모듈들
        test_modules = [
            ('common.gcp_utils', 'GCP 유틸리티'),
            ('common.azure_utils', 'Azure 유틸리티'),
            ('src.ic.config.external', '외부 설정 로더'),
            ('src.ic.config.secrets', '시크릿 매니저')
        ]
        
        for module_name, description in test_modules:
            try:
                __import__(module_name)
                self.log_validation_result(f"{description} 모듈 import", True)
                
                # 모듈별 기본 기능 테스트
                if module_name == 'common.gcp_utils':
                    self.test_gcp_utils()
                elif module_name == 'common.azure_utils':
                    self.test_azure_utils()
                elif module_name == 'src.ic.config.external':
                    self.test_external_config()
                elif module_name == 'src.ic.config.secrets':
                    self.test_secrets_manager()
                    
            except Exception as e:
                self.log_validation_result(
                    f"{description} 모듈 import",
                    False,
                    {"error": str(e)}
                )
                
    def test_gcp_utils(self):
        """GCP 유틸리티 테스트"""
        try:
            from common.gcp_utils import get_gcp_config
            config = get_gcp_config()
            self.log_validation_result("GCP 설정 로딩", True, {"config_keys": list(config.keys())})
        except Exception as e:
            self.log_validation_result("GCP 설정 로딩", False, {"error": str(e)})
            
    def test_azure_utils(self):
        """Azure 유틸리티 테스트"""
        try:
            from common.azure_utils import get_azure_config
            config = get_azure_config()
            self.log_validation_result("Azure 설정 로딩", True, {"config_keys": list(config.keys())})
        except Exception as e:
            self.log_validation_result("Azure 설정 로딩", False, {"error": str(e)})
            
    def test_external_config(self):
        """외부 설정 로더 테스트"""
        try:
            from ic.config.external import ExternalConfigLoader
            loader = ExternalConfigLoader()
            
            # AWS 설정 테스트
            try:
                aws_config = loader.load_aws_config()
                self.log_validation_result("AWS 외부 설정 로딩", True)
            except Exception:
                self.log_validation_result("AWS 외부 설정 로딩", False, {"note": "AWS 설정 파일 없음 (정상)"})
                
        except Exception as e:
            self.log_validation_result("외부 설정 로더", False, {"error": str(e)})
            
    def test_secrets_manager(self):
        """시크릿 매니저 테스트"""
        try:
            from ic.config.secrets import SecretsManager
            secrets_manager = SecretsManager()
            
            # 시크릿 로딩 테스트
            secrets = secrets_manager.load_secrets()
            self.log_validation_result("시크릿 로딩", True, {"sections": list(secrets.keys())})
            
        except Exception as e:
            self.log_validation_result("시크릿 로딩", False, {"error": str(e)})
            
    def validate_backup_integrity(self):
        """백업 파일 무결성 검증"""
        logger.info("=== 백업 파일 무결성 검증 ===")
        
        backup_env_dir = self.backup_dir / 'env_files'
        if not backup_env_dir.exists():
            self.log_validation_result("백업 디렉토리 존재", False)
            return
            
        backup_files = list(backup_env_dir.glob('.env.backup.*'))
        if not backup_files:
            self.log_validation_result("백업 파일 존재", False)
            return
            
        # 가장 최근 백업 파일 검증
        latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
        
        try:
            # 백업 파일 읽기 테스트
            content = latest_backup.read_text(encoding='utf-8')
            lines = content.strip().split('\n')
            
            self.log_validation_result(
                "백업 파일 무결성",
                True,
                {
                    "backup_file": str(latest_backup),
                    "lines_count": len(lines),
                    "file_size": latest_backup.stat().st_size
                }
            )
            
        except Exception as e:
            self.log_validation_result(
                "백업 파일 무결성",
                False,
                {"error": str(e)}
            )
            
    def test_dynamic_config_loading(self):
        """동적 설정 로딩 테스트"""
        logger.info("=== 동적 설정 로딩 테스트 ===")
        
        try:
            from ic.config.manager import ConfigManager
            
            # 첫 번째 로딩
            config_manager = ConfigManager()
            config1 = config_manager.get_config()
            
            # 캐시 무효화
            try:
                config_manager.invalidate_cache()
                
                # 두 번째 로딩
                config2 = config_manager.get_config()
                
                # 설정이 동일한지 확인
                configs_match = config1 == config2
            except AttributeError:
                # invalidate_cache 메서드가 없는 경우 새로운 인스턴스 생성
                config_manager2 = ConfigManager()
                config2 = config_manager2.get_config()
                configs_match = config1 == config2
            self.log_validation_result(
                "동적 설정 로딩",
                configs_match,
                {"cache_invalidation": True}
            )
            
        except Exception as e:
            self.log_validation_result(
                "동적 설정 로딩",
                False,
                {"error": str(e)}
            )
            
    def generate_migration_history(self):
        """마이그레이션 히스토리 문서 생성"""
        logger.info("=== 마이그레이션 히스토리 문서 생성 ===")
        
        # docs 디렉토리 생성
        docs_dir = self.project_root / 'docs'
        docs_dir.mkdir(exist_ok=True)
        
        # 마이그레이션 히스토리 문서 내용 생성
        history_content = self.create_migration_history_content()
        
        try:
            self.migration_history_file.write_text(history_content, encoding='utf-8')
            self.log_migration_step(
                "Documentation",
                f"마이그레이션 히스토리 문서 생성: {self.migration_history_file}",
                "success"
            )
        except Exception as e:
            self.log_migration_step(
                "Documentation",
                f"마이그레이션 히스토리 문서 생성 실패: {e}",
                "error"
            )
            
    def create_migration_history_content(self) -> str:
        """마이그레이션 히스토리 문서 내용 생성"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        content = f"""# 설정 시스템 마이그레이션 히스토리

## 마이그레이션 개요

- **실행 일시**: {timestamp}
- **마이그레이션 유형**: .env 파일에서 YAML 설정으로 마이그레이션
- **대상 시스템**: IC (Infrastructure Commander) v2.0

## 마이그레이션 단계

"""
        
        # 마이그레이션 로그 추가
        for i, step in enumerate(self.migration_log, 1):
            step_time = time.strftime("%H:%M:%S", time.localtime(step['timestamp']))
            status_icon = "✅" if step['status'] == "success" else "❌" if step['status'] == "error" else "⚠️"
            
            content += f"### {i}. {step['type']} - {step_time}\n\n"
            content += f"{status_icon} **상태**: {step['status']}\n\n"
            content += f"**설명**: {step['description']}\n\n"
            
            if step['details']:
                content += "**세부사항**:\n"
                for key, value in step['details'].items():
                    content += f"- {key}: {value}\n"
                content += "\n"
                
        # 검증 결과 추가
        content += "## 검증 결과\n\n"
        
        success_count = sum(1 for v in self.validation_results if v['result'])
        total_count = len(self.validation_results)
        
        content += f"**전체 검증**: {success_count}/{total_count} 성공\n\n"
        
        for i, validation in enumerate(self.validation_results, 1):
            result_icon = "✅" if validation['result'] else "❌"
            content += f"### {i}. {validation['test_name']}\n\n"
            content += f"{result_icon} **결과**: {'성공' if validation['result'] else '실패'}\n\n"
            
            if validation['details']:
                content += "**세부사항**:\n"
                for key, value in validation['details'].items():
                    content += f"- {key}: {value}\n"
                content += "\n"
                
        # 요약 및 권장사항
        content += "## 마이그레이션 요약\n\n"
        
        if success_count == total_count:
            content += "🎉 **마이그레이션이 성공적으로 완료되었습니다!**\n\n"
            content += "모든 검증 테스트가 통과했으며, 새로운 YAML 기반 설정 시스템이 정상적으로 작동합니다.\n\n"
        else:
            content += "⚠️ **마이그레이션이 부분적으로 완료되었습니다.**\n\n"
            content += f"{total_count - success_count}개의 검증 테스트가 실패했습니다. 위의 검증 결과를 확인하여 문제를 해결해주세요.\n\n"
            
        content += "### 다음 단계\n\n"
        content += "1. **설정 확인**: `ic config show` 명령어로 현재 설정을 확인하세요.\n"
        content += "2. **서비스 테스트**: 각 클라우드 서비스 명령어를 실행하여 정상 작동을 확인하세요.\n"
        content += "3. **백업 관리**: 백업된 .env 파일은 `backup/env_files/` 디렉토리에 보관됩니다.\n"
        content += "4. **문서 참조**: 새로운 설정 시스템 사용법은 `docs/configuration.md`를 참조하세요.\n\n"
        
        content += "### 백업 파일 위치\n\n"
        backup_env_dir = self.backup_dir / 'env_files'
        if backup_env_dir.exists():
            backup_files = list(backup_env_dir.glob('.env.backup.*'))
            if backup_files:
                content += "다음 위치에 원본 .env 파일이 백업되었습니다:\n\n"
                for backup_file in backup_files:
                    content += f"- `{backup_file}`\n"
                content += "\n"
                
        content += "### 롤백 방법\n\n"
        content += "만약 문제가 발생하여 이전 설정으로 돌아가야 한다면:\n\n"
        content += "1. 백업된 .env 파일을 프로젝트 루트로 복사\n"
        content += "2. config/ 디렉토리의 YAML 파일들 제거\n"
        content += "3. 애플리케이션 재시작\n\n"
        
        return content
        
    def run_full_migration_and_validation(self):
        """전체 마이그레이션 및 검증 실행"""
        logger.info("=== 마이그레이션 실행 및 검증 시작 ===")
        
        success = True
        
        # 1. 현재 .env 파일 백업
        if not self.backup_current_env():
            success = False
            
        # 2. 마이그레이션 실행
        if not self.execute_migration():
            success = False
            
        # 3. 마이그레이션된 설정 검증
        self.validate_migrated_config()
        
        # 4. 서비스 모듈 동작 테스트
        self.test_service_modules()
        
        # 5. 백업 파일 무결성 검증
        self.validate_backup_integrity()
        
        # 6. 동적 설정 로딩 테스트
        self.test_dynamic_config_loading()
        
        # 7. 마이그레이션 히스토리 문서 생성
        self.generate_migration_history()
        
        # 결과 요약
        self.print_summary()
        
        return success and all(v['result'] for v in self.validation_results)
        
    def print_summary(self):
        """결과 요약 출력"""
        logger.info("=== 마이그레이션 및 검증 결과 요약 ===")
        
        migration_success = all(step['status'] == 'success' for step in self.migration_log if step['status'] != 'warning')
        validation_success = all(v['result'] for v in self.validation_results)
        
        total_validations = len(self.validation_results)
        successful_validations = sum(1 for v in self.validation_results if v['result'])
        
        logger.info(f"마이그레이션 단계: {'✅ 성공' if migration_success else '❌ 실패'}")
        logger.info(f"검증 테스트: {successful_validations}/{total_validations} 성공")
        
        if migration_success and validation_success:
            logger.info("🎉 마이그레이션이 성공적으로 완료되었습니다!")
            logger.info(f"📄 마이그레이션 히스토리: {self.migration_history_file}")
        else:
            logger.warning("⚠️ 일부 단계에서 문제가 발생했습니다. 로그를 확인해주세요.")
            
        return migration_success and validation_success

def main():
    """메인 함수"""
    executor = MigrationExecutor()
    success = executor.run_full_migration_and_validation()
    
    if success:
        logger.info("🎉 마이그레이션 실행 및 검증이 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        logger.error("⚠️ 마이그레이션 또는 검증 중 문제가 발생했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()