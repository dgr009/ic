#!/usr/bin/env python3
"""
Configuration validation script for IC build process.
Requirements: 8.2
"""

import sys
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigValidator:
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        self.validation_errors: List[str] = []
        
    def validate_yaml_syntax(self, file_path: Path) -> bool:
        """YAML 파일 구문 검증"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            logger.info(f"✓ YAML 구문 검증 통과: {file_path}")
            return True
        except yaml.YAMLError as e:
            error_msg = f"✗ YAML 구문 오류 in {file_path}: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"✗ 파일 읽기 오류 in {file_path}: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return False
            
    def validate_json_syntax(self, file_path: Path) -> bool:
        """JSON 파일 구문 검증"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            logger.info(f"✓ JSON 구문 검증 통과: {file_path}")
            return True
        except json.JSONDecodeError as e:
            error_msg = f"✗ JSON 구문 오류 in {file_path}: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return False
        except Exception as e:
            error_msg = f"✗ 파일 읽기 오류 in {file_path}: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return False
            
    def validate_required_config_files(self) -> bool:
        """필수 설정 파일 존재 확인"""
        # Check both new and legacy configuration paths
        config_paths = [
            (".ic/config/default.yaml", "config/default.yaml"),
            (".ic/config/secrets.yaml", "config/secrets.yaml"),
        ]
        
        required_files = []
        for new_path, legacy_path in config_paths:
            if os.path.exists(new_path):
                required_files.append(new_path)
            elif os.path.exists(legacy_path):
                required_files.append(legacy_path)
            else:
                required_files.append(new_path)  # Use new path as default
        
        all_exist = True
        for file_path in required_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                logger.info(f"✓ 필수 파일 존재: {file_path}")
            else:
                error_msg = f"✗ 필수 파일 없음: {file_path}"
                logger.error(error_msg)
                self.validation_errors.append(error_msg)
                all_exist = False
                
        return all_exist
        
    def validate_config_structure(self, config_file: Path) -> bool:
        """설정 파일 구조 검증"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            if not isinstance(config, dict):
                error_msg = f"✗ 설정 파일이 딕셔너리 형태가 아님: {config_file}"
                logger.error(error_msg)
                self.validation_errors.append(error_msg)
                return False
                
            # default.yaml의 경우 주요 섹션 확인
            if config_file.name == "default.yaml":
                expected_sections = ["version", "logging"]
                for section in expected_sections:
                    if section not in config:
                        logger.warning(f"⚠ 권장 섹션 없음 in {config_file}: {section}")
                        
            logger.info(f"✓ 설정 구조 검증 통과: {config_file}")
            return True
            
        except Exception as e:
            error_msg = f"✗ 설정 구조 검증 실패 in {config_file}: {e}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            return False
            
    def validate_security_settings(self) -> bool:
        """보안 설정 검증"""
        secrets_file = self.config_dir / "secrets.yaml"
        
        if not secrets_file.exists():
            logger.warning("⚠ secrets.yaml 파일이 없습니다. 환경변수를 사용하는지 확인하세요.")
            return True
            
        # 파일 권한 확인 (Unix 시스템에서만)
        if hasattr(secrets_file.stat(), 'st_mode'):
            import stat
            file_mode = secrets_file.stat().st_mode
            if file_mode & stat.S_IRGRP or file_mode & stat.S_IROTH:
                logger.warning(f"⚠ {secrets_file}의 권한이 안전하지 않습니다. 600으로 설정하는 것을 권장합니다.")
                
        logger.info("✓ 보안 설정 검증 완료")
        return True
        
    def validate_all_configs(self) -> bool:
        """모든 설정 파일 검증"""
        logger.info("=== 설정 파일 검증 시작 ===")
        
        success = True
        
        # 1. 필수 파일 존재 확인
        if not self.validate_required_config_files():
            success = False
            
        # 2. 설정 디렉토리의 모든 YAML/JSON 파일 검증
        if self.config_dir.exists():
            for file_path in self.config_dir.rglob("*.yaml"):
                if not self.validate_yaml_syntax(file_path):
                    success = False
                else:
                    if not self.validate_config_structure(file_path):
                        success = False
                        
            for file_path in self.config_dir.rglob("*.yml"):
                if not self.validate_yaml_syntax(file_path):
                    success = False
                else:
                    if not self.validate_config_structure(file_path):
                        success = False
                        
            for file_path in self.config_dir.rglob("*.json"):
                if not self.validate_json_syntax(file_path):
                    success = False
        else:
            error_msg = f"✗ 설정 디렉토리가 존재하지 않습니다: {self.config_dir}"
            logger.error(error_msg)
            self.validation_errors.append(error_msg)
            success = False
            
        # 3. 보안 설정 검증
        if not self.validate_security_settings():
            success = False
            
        # 결과 요약
        if success:
            logger.info("=== 모든 설정 파일 검증 통과 ===")
        else:
            logger.error("=== 설정 파일 검증 실패 ===")
            logger.error("오류 목록:")
            for error in self.validation_errors:
                logger.error(f"  - {error}")
                
        return success

def main():
    """메인 함수"""
    validator = ConfigValidator()
    success = validator.validate_all_configs()
    
    if success:
        logger.info("설정 파일 검증이 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        logger.error("설정 파일 검증에 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()