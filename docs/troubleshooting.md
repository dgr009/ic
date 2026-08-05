# IC CLI Troubleshooting Guide

Solutions and troubleshooting steps for common issues encountered when using IC CLI.

## ❓ Common Issues & Solutions

### 1. AWS Health API Error (`SubscriptionRequiredException`)
- **Symptom**: `ic aws healthdashboard reboot` execution fails with `AWS Business 또는 Enterprise Support 플랜이 필요합니다.`
- **Cause**: AWS Health API requires an active Business, Enterprise On-Ramp, or Enterprise Support plan.
- **Solution**: Run on accounts with Business/Enterprise support or check standard EC2 commands (`ic aws ec2 info`).

### 2. Missing AWS / Tencent Profiles
- **Symptom**: `❌ 조회를 진행할 AWS 계정을 찾을 수 없습니다.`
- **Cause**: No profiles found in `~/.aws/config`, `~/.aws/credentials`, or `~/.tencent/credentials`.
- **Solution**: Configure your credentials via `aws configure` / `ic config init` or specify account `-a profile_name`.

### 3. Permission Denied / Access Denied (`AccessDeniedException`)
- **Symptom**: API calls return permission errors.
- **Cause**: IAM user/role lacks required describe permissions (e.g., `ec2:DescribeInstances`, `health:DescribeEvents`).
- **Solution**: Grant appropriate read-only policy (`ReadOnlyAccess` or specific service describe actions) to the IAM entity.

### 4. Encoding Error (`UnicodeDecodeError` / `CP949`)
- **Symptom**: Character decoding errors on Windows.
- **Solution**: Set environment variable `PYTHONUTF8=1` in Windows PowerShell / CMD:
  ```powershell
  $env:PYTHONUTF8=1
  ```

---

## 🔍 Debugging Mode

Enable verbose output to inspect full tracebacks and debug details:

```bash
ic <platform> <service> <command> --verbose
```
