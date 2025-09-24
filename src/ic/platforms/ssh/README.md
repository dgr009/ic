# 📘 auto_ssh.py

자동으로 SSH 가능한 호스트를 스캔하고, SSH 설정 파일(`~/.ssh/config`)에 쉽게 등록할 수 있도록 도와주는 유틸리티 스크립트입니다.

---

## ✨ 주요 기능

- 🔍 CIDR 대역 자동 추정 및 수동 입력 지원
- 🔓 포트(기본 22) 열려 있는 호스트 자동 탐색
- 🙅 이미 등록된 IP는 제외
- 🧑 사용자 계정 직접 선택 또는 입력
- 🔑 키 파일 자동 탐색 또는 직접 입력
- 🧾 `~/.ssh/config` 자동 등록 및 주석 처리 포함
- ✅ 등록된 모든 SSH 호스트 연결 확인 기능 (`--check`)
- 🧠 직관적인 Rich 기반 인터페이스

---

## 🧑‍💻 설치 및 환경 준비

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. 필요 환경변수 설정 (.env 파일 또는 export)
```env
SSH_KEY_DIR=~/aws-key
SSH_CONFIG_FILE=~/.ssh/config
SSH_MAX_WORKER=70
PORT_OPEN_TIMEOUT=0.5
SSH_TIMEOUT=3
```

---

## 🚀 사용 방법

### 1. 일반 실행 (CIDR 자동 추정)
```bash
python auto_ssh.py
```
- CIDR은 자동으로 추정되며, 수동 입력도 가능
- 열린 포트(22) 탐색 후 하나씩 등록 여부를 선택
- 등록된 호스트는 `~/.ssh/config`에 기록됨

### 2. 특정 CIDR 명시하여 실행
```bash
python auto_ssh.py 192.168.1.0/24
```

### 3. 모든 SSH 등록 호스트 접속 가능 여부 확인
```bash
python auto_ssh.py --check
```
- `~/.ssh/config`에 등록된 모든 호스트 대상
- 연결 실패한 호스트는 테이블로 출력

---

## 🗂️ 출력 예시

### 🔍 열린 호스트 탐색 결과
```
Port Open IP LIST :
- 192.168.1.101
- 192.168.1.104
```

### 📄 SSH 설정 등록 예시 (~/.ssh/config)
```ssh
# Added by auto_ssh.py on 2025-03-25
Host host-192-168-1-101
    Hostname 192.168.1.101
    User ubuntu
    Port 22
    IdentityFile ~/aws-key/my-key.pem
```

### 🛠️ 연결 실패 테이블 출력
```
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Host               ┃ IP              ┃ Error     ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ sykim1             │ 20.20.6.8       │ timed out │
└────────────────────┴─────────────────┴───────────┘
```

---

## 🔐 SSH 키 파일 경로 자동 탐색
- `~/aws-key/` 내의 `.pem` 파일 자동 탐색
- 키 파일 없을 시 수동 입력 가능

---

## 📁 파일 구조
```
.
├── auto_ssh.py
├── .env (옵션)
├── logs/
│   └── auto_ssh.log
├── requirements.txt
└── README.md
```

---

## 📝 요구 사항
- Python 3.7+
- 패키지: `paramiko`, `rich`, `netifaces`, `tqdm`, `python-dotenv`

---

## 🙋 자주 묻는 질문

### Q. 키보드 입력이 필요한 2FA 호스트는 어떻게 처리되나요?
A. 현재는 자동 등록 시 제외되며, 수동으로 처리하는 것을 권장합니다.

### Q. 이미 등록된 호스트가 있는데 다시 등록할 수 있나요?
A. IP 기준 중복 체크를 수행하므로 기존 IP는 스킵됩니다. 다른 이름으로 등록하려면 `~/.ssh/config`를 편집하거나 IP를 변경해야 합니다.

---

## 🧑‍🔧 유지보수자 정보
- 작성자: sykim
- 문의: email

