# SSH Configuration Guide

## SSH Host Key Policy 설정

IC CLI의 SSH 기능은 보안을 위해 다양한 호스트 키 정책을 지원합니다.

### 설정 방법

`~/.ic/config/default.yaml` 파일에서 SSH 설정을 수정할 수 있습니다:

```yaml
ssh:
  config_file: ~/.ssh/config
  key_dir: ~/.ssh
  timeout: 5
  workers: 20
  host_key_policy: auto  # 새로 추가된 설정
  skip_prefixes:
    - git
    - test
```

### Host Key Policy 옵션

1. **auto** (기본값, 권장)
   - 처음 연결하는 호스트의 키를 자동으로 `~/.ssh/known_hosts`에 추가
   - 편의성과 보안의 균형을 제공
   - 대부분의 사용 사례에 적합

2. **warning**
   - 알려지지 않은 호스트에 대해 경고를 출력하지만 연결 허용
   - 개발 환경이나 테스트 환경에 적합
   - 보안 경고를 확인할 수 있음

3. **reject**
   - 알려지지 않은 호스트에 대한 연결을 거부
   - 최고 수준의 보안
   - 프로덕션 환경에 적합하지만 초기 설정이 복잡할 수 있음

### 환경 변수 오버라이드

개발이나 테스트 목적으로 임시로 정책을 변경할 수 있습니다:

```bash
# 테스트 모드 (경고 정책 사용)
IC_TEST_MODE=1 ic ssh info

# 개발 모드 (경고 정책 사용)
IC_DEV_MODE=1 ic ssh info
```

### 보안 고려사항

- **프로덕션 환경**: `reject` 정책 사용 권장
- **개발 환경**: `auto` 또는 `warning` 정책 사용 권장
- **CI/CD 환경**: `IC_TEST_MODE=1` 환경 변수 사용 권장

### 문제 해결

#### 모든 서버가 "Connection Fail"로 표시되는 경우

1. **임시 해결책**:
   ```bash
   IC_DEV_MODE=1 ic ssh info
   ```

2. **영구 해결책**:
   설정 파일에서 `host_key_policy`를 `auto`로 변경:
   ```yaml
   ssh:
     host_key_policy: auto
   ```

3. **known_hosts 파일 확인**:
   ```bash
   ls -la ~/.ssh/known_hosts
   ```

#### 특정 서버만 연결 실패하는 경우

1. SSH 키 권한 확인:
   ```bash
   chmod 600 ~/.ssh/id_rsa
   chmod 644 ~/.ssh/id_rsa.pub
   ```

2. SSH 설정 파일 확인:
   ```bash
   ssh -T [hostname]
   ```

### 예제 설정

완전한 SSH 설정 예제:

```yaml
ssh:
  config_file: ~/.ssh/config
  key_dir: ~/.ssh
  timeout: 10
  workers: 30
  host_key_policy: auto
  skip_prefixes:
    - git
    - github
    - gitlab
    - test-
    - temp-
```