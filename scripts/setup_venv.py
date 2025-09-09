#!/usr/bin/env python3
"""
새로운 가상환경 생성 및 의존성 설치 스크립트
Requirements: 8.1
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VirtualEnvironmentSetup:
    def __init__(self, venv_name="ic-new-env"):
        self.venv_name = venv_name
        self.project_root = Path(__file__).parent.parent
        self.venv_path = self.project_root / self.venv_name
        self.requirements_file = self.project_root / "requirements.txt"
        
    def check_python_version(self):
        """Python 버전 확인"""
        logger.info(f"Python 버전 확인: {sys.version}")
        if sys.version_info < (3, 8):
            raise RuntimeError("Python 3.8 이상이 필요합니다.")
        return True
        
    def create_virtual_environment(self):
        """가상환경 생성"""
        logger.info(f"가상환경 생성 중: {self.venv_path}")
        
        # 기존 가상환경이 있으면 삭제
        if self.venv_path.exists():
            logger.info("기존 가상환경 삭제 중...")
            shutil.rmtree(self.venv_path)
            
        # 새 가상환경 생성
        try:
            subprocess.run([
                sys.executable, "-m", "venv", str(self.venv_path)
            ], check=True, capture_output=True, text=True)
            logger.info("가상환경 생성 완료")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"가상환경 생성 실패: {e}")
            logger.error(f"stderr: {e.stderr}")
            return False
            
    def get_pip_executable(self):
        """pip 실행 파일 경로 반환"""
        if sys.platform == "win32":
            return self.venv_path / "Scripts" / "pip.exe"
        else:
            return self.venv_path / "bin" / "pip"
            
    def get_python_executable(self):
        """Python 실행 파일 경로 반환"""
        if sys.platform == "win32":
            return self.venv_path / "Scripts" / "python.exe"
        else:
            return self.venv_path / "bin" / "python"
            
    def upgrade_pip(self):
        """pip 업그레이드"""
        logger.info("pip 업그레이드 중...")
        pip_path = self.get_pip_executable()
        
        try:
            subprocess.run([
                str(pip_path), "install", "--upgrade", "pip"
            ], check=True, capture_output=True, text=True)
            logger.info("pip 업그레이드 완료")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"pip 업그레이드 실패: {e}")
            logger.error(f"stderr: {e.stderr}")
            return False
            
    def install_dependencies(self):
        """의존성 설치"""
        logger.info("의존성 설치 중...")
        pip_path = self.get_pip_executable()
        
        if not self.requirements_file.exists():
            logger.error(f"requirements.txt 파일을 찾을 수 없습니다: {self.requirements_file}")
            return False
            
        try:
            # requirements-updated.txt 설치 (더 유연한 버전)
            updated_requirements = self.project_root / "requirements-updated.txt"
            if updated_requirements.exists():
                subprocess.run([
                    str(pip_path), "install", "-r", str(updated_requirements)
                ], check=True, capture_output=True, text=True)
                logger.info("requirements-updated.txt 의존성 설치 완료")
            else:
                # 기존 requirements.txt 사용
                subprocess.run([
                    str(pip_path), "install", "-r", str(self.requirements_file)
                ], check=True, capture_output=True, text=True)
                logger.info("requirements.txt 의존성 설치 완료")
            
            # 추가 의존성 설치 (새로운 설정 시스템용)
            additional_deps = [
                "watchdog>=3.0.0",  # 파일 변경 감지용
                "cerberus>=1.3.4",   # 스키마 검증용
                "pydantic>=2.0.0",   # 데이터 검증용
                "netifaces>=0.11.0", # 네트워크 인터페이스 정보
            ]
            
            for dep in additional_deps:
                logger.info(f"추가 의존성 설치: {dep}")
                subprocess.run([
                    str(pip_path), "install", dep
                ], check=True, capture_output=True, text=True)
                
            logger.info("모든 의존성 설치 완료")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"의존성 설치 실패: {e}")
            logger.error(f"stderr: {e.stderr}")
            return False
            
    def install_project_in_development_mode(self):
        """프로젝트를 개발 모드로 설치"""
        logger.info("프로젝트를 개발 모드로 설치 중...")
        pip_path = self.get_pip_executable()
        
        try:
            subprocess.run([
                str(pip_path), "install", "-e", "."
            ], cwd=str(self.project_root), check=True, capture_output=True, text=True)
            logger.info("프로젝트 개발 모드 설치 완료")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"프로젝트 설치 실패: {e}")
            logger.error(f"stderr: {e.stderr}")
            return False
            
    def verify_installation(self):
        """설치 검증"""
        logger.info("설치 검증 중...")
        python_path = self.get_python_executable()
        
        # 기본 import 테스트
        test_imports = [
            "import sys; print('Python:', sys.version)",
            "import yaml; print('PyYAML 설치됨')",
            "import boto3; print('boto3 설치됨')",
            "import rich; print('rich 설치됨')",
            "import watchdog; print('watchdog 설치됨')",
            "import cerberus; print('cerberus 설치됨')",
            "import pydantic; print('pydantic 설치됨')",
        ]
        
        for test_import in test_imports:
            try:
                result = subprocess.run([
                    str(python_path), "-c", test_import
                ], check=True, capture_output=True, text=True)
                logger.info(f"✓ {result.stdout.strip()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"✗ Import 실패: {test_import}")
                logger.error(f"Error: {e.stderr}")
                return False
                
        # 프로젝트 모듈 import 테스트
        try:
            result = subprocess.run([
                str(python_path), "-c", 
                "from ic.config.manager import ConfigManager; print('ConfigManager import 성공')"
            ], cwd=str(self.project_root), check=True, capture_output=True, text=True)
            logger.info(f"✓ {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            logger.error("✗ ConfigManager import 실패")
            logger.error(f"Error: {e.stderr}")
            return False
            
        logger.info("모든 검증 완료!")
        return True
        
    def create_activation_script(self):
        """가상환경 활성화 스크립트 생성"""
        logger.info("활성화 스크립트 생성 중...")
        
        if sys.platform == "win32":
            script_content = f"""@echo off
echo 새로운 IC 가상환경 활성화 중...
call "{self.venv_path}\\Scripts\\activate.bat"
echo 가상환경이 활성화되었습니다: {self.venv_name}
echo Python 경로: {self.get_python_executable()}
echo.
echo 설정 시스템 테스트를 위해 다음 명령어를 실행하세요:
echo   python -c "from ic.config.manager import ConfigManager; cm = ConfigManager(); print('설정 시스템 정상 작동')"
echo.
cmd /k
"""
            script_path = self.project_root / "activate_new_env.bat"
        else:
            script_content = f"""#!/bin/bash
echo "새로운 IC 가상환경 활성화 중..."
source "{self.venv_path}/bin/activate"
echo "가상환경이 활성화되었습니다: {self.venv_name}"
echo "Python 경로: {self.get_python_executable()}"
echo ""
echo "설정 시스템 테스트를 위해 다음 명령어를 실행하세요:"
echo '  python -c "from ic.config.manager import ConfigManager; cm = ConfigManager(); print('"'"'설정 시스템 정상 작동'"'"')"'
echo ""
exec "$SHELL"
"""
            script_path = self.project_root / "activate_new_env.sh"
            
        script_path.write_text(script_content, encoding='utf-8')
        
        if not sys.platform == "win32":
            os.chmod(script_path, 0o755)
            
        logger.info(f"활성화 스크립트 생성 완료: {script_path}")
        return script_path
        
    def run_setup(self):
        """전체 설정 프로세스 실행"""
        logger.info("=== 새로운 가상환경 설정 시작 ===")
        
        try:
            # 1. Python 버전 확인
            if not self.check_python_version():
                return False
                
            # 2. 가상환경 생성
            if not self.create_virtual_environment():
                return False
                
            # 3. pip 업그레이드
            if not self.upgrade_pip():
                return False
                
            # 4. 의존성 설치
            if not self.install_dependencies():
                return False
                
            # 5. 프로젝트 개발 모드 설치
            if not self.install_project_in_development_mode():
                return False
                
            # 6. 설치 검증
            if not self.verify_installation():
                return False
                
            # 7. 활성화 스크립트 생성
            script_path = self.create_activation_script()
            
            logger.info("=== 가상환경 설정 완료 ===")
            logger.info(f"가상환경 경로: {self.venv_path}")
            logger.info(f"활성화 스크립트: {script_path}")
            logger.info("다음 단계:")
            logger.info(f"  1. 활성화 스크립트 실행: {script_path}")
            logger.info("  2. 설정 시스템 테스트 실행")
            logger.info("  3. 각 서비스 모듈 테스트")
            
            return True
            
        except Exception as e:
            logger.error(f"설정 중 오류 발생: {e}")
            return False

def main():
    """메인 함수"""
    setup = VirtualEnvironmentSetup()
    success = setup.run_setup()
    
    if success:
        logger.info("가상환경 설정이 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        logger.error("가상환경 설정에 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    main()