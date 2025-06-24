# 프로젝트 설정 및 실행 가이드

이 문서는 `find.py` 스크립트를 실행하기 전에 필요한 설정 파일과 환경을 준비하는 방법을 설명합니다.

### 1. Python 버전 설정

- **파일**: `.python-version`
- **설명**: 이 파일은 프로젝트에서 사용할 Python 버전을 지정합니다. `oci_policy`라는 가상 환경을 사용하도록 설정되어 있습니다. 이 가상 환경을 활성화해야 합니다.
- **가상 환경 버전**: `3.13.2/envs/oci_policy`

- **설치 방법**:
  1. `pyenv`를 설치합니다. macOS에서는 Homebrew를 사용하여 설치할 수 있습니다:
     ```bash
     brew update
     brew install pyenv
     ```
  2. `pyenv`를 사용하여 Python 3.13.2 버전을 설치합니다:
     ```bash
     pyenv install 3.13.2
     ```
  3. 다음 명령어를 사용하여 가상 환경을 생성합니다:
     ```bash
     pyenv virtualenv 3.13.2 oci_policy
     ```
  4. `pyenv`를 사용하여 해당 버전을 활성화합니다:
     ```bash
     pyenv local oci_policy
     ```

### 2. OCI 설정 파일

- **파일**: `config`
- **설명**: Oracle Cloud Infrastructure(OCI) API와의 통신을 위한 설정 파일입니다. 다음과 같은 정보가 포함되어야 합니다:
  - 사용자 OCID
  - 지문 (fingerprint)
  - 테넌시 OCID
  - 리전
  - 개인 키 파일 경로

- **설정 방법**:
  1. `config` 파일을 열고 각 항목에 맞는 정보를 입력합니다.
  2. `key_file` 경로에 개인 키 파일이 존재하는지 확인합니다.

### 3. 컴파트먼트 설정

- **파일**: `compartment.txt`
- **설명**: 각 컴파트먼트의 OCID를 정의하는 파일입니다. `find.py`가 특정 컴파트먼트에 대한 작업을 수행할 때 사용됩니다.

- **설정 방법**:
  1. `compartment.txt` 파일을 열고 각 컴파트먼트의 이름과 OCID를 정확히 입력합니다.

### 4. 종속성 설치

- **파일**: `requirements.txt`
- **설명**: `find.py`가 의존하는 Python 패키지 목록입니다. 이 파일을 사용하여 필요한 모든 패키지를 설치할 수 있습니다.

- **설치 방법**:
  1. 가상 환경을 활성화합니다.
  2. 다음 명령어를 실행하여 종속성을 설치합니다:
     ```bash
     pip install -r requirements.txt
     ```

### 5. 환경 변수 설정

- **설명**: `.env` 파일을 사용하여 필요한 환경 변수를 설정합니다. 이 파일은 `python-dotenv` 패키지를 통해 로드됩니다.

- **설정 방법**:
  1. `.env` 파일을 생성하고 필요한 환경 변수를 정의합니다.
  2. 예를 들어, `OCI_CONFIG_FILE` 변수를 설정하여 `config` 파일의 경로를 지정할 수 있습니다.

### 6. `find.py` 실행

모든 설정이 완료되면, `find.py`를 실행하여 원하는 작업을 수행할 수 있습니다. 다음 명령어를 사용하여 스크립트를 실행합니다:

```bash
python3 find.py
```

이 가이드를 따라 설정을 완료한 후 `find.py`를 실행하면 정상적으로 작동할 것입니다. 추가적인 질문이 있으면 언제든지 문의해 주세요!
