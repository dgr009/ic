import os
import json
import re
import requests
import time
from rich.console import Console
from rich.table import Table
from common.log import log_error, log_info

# Slack Webhook URL을 .env 파일에서 가져옴
# SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Rich 콘솔 객체 초기화
console = Console()

def table_to_clean_text(table):
    """Rich 테이블을 ANSI 코드 없이 텍스트로 변환."""
    with console.capture() as capture:
        console.print(table)
    raw_text = capture.get()
    clean_text = re.sub(r'\x1b\[[0-9;]*m', '', raw_text)  # ANSI 코드 제거
    return clean_text

def send_slack_blocks_table_with_color(title, headers, rows, max_attachments=30):
    """
    Slack Blocks Kit과 attachments을 사용해 테이블 형식으로 메시지를 전송.
    너무 많은 rows가 들어오면 'too_many_attachments' 오류가 날 수 있으므로,
    임계값 max_attachments를 넘어가면 요약 메시지만 전송한다.
    """
    import os
    from aws.common.log import log_error, log_info

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        log_error("Slack Webhook URL이 설정되지 않았습니다.")
        return

    # 1) 만약 rows가 임계값을 초과한다면, 전체 데이터 대신 요약만 보냄
    if len(rows) > max_attachments:
        summary_attachments = [
            {
                "color": "#ff0000",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"📊 {title} (요약)", "emoji": True}
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*검사 결과가 너무 많아 Slack 제한을 초과했습니다.*\n\n"
                                f"• 총 {len(rows)}건의 이슈가 발견되었습니다.\n"
                                f"• Slack 메시지가 너무 커져 전송할 수 없습니다.\n"
                                f"• 상세 내용은 콘솔 로그 또는 다른 경로로 확인해주세요."
                            )
                        },
                    },
                ]
            }
        ]

        payload = {"attachments": summary_attachments}
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code != 200:
            log_error(
                f"Request to Slack returned an error {response.status_code}, "
                f"the response is:\n{response.text}"
            )
        else:
            log_info(f"Slack 요약 메시지를 전송했습니다 (총 {len(rows)}건).")
        return

    # 2) rows가 임계값 이하라면, 기존 로직대로 상세히 전송
    attachments = [
        {
            "color": "#000000",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"📊 {title}", "emoji": True}
                },
                {"type": "divider"},
            ]
        }
    ]

    for row in rows:
        # 유효성 검사 결과에 따라 색상 지정
        color_fields_1 = "#dddddd" if "누락" in row[3] else "#36a64f"
        color_fields_2 = "#ff0000" if "누락" in row[3] else "#36a64f"
        vaildation_emoji = ":x:" if "누락" in row[3] else ":o:"

        fields_1 = [
            {"type": "mrkdwn", "text": f":id: *{headers[0]}*: {row[0]}"},
            {"type": "mrkdwn", "text": f":globe_with_meridians: *{headers[1]}*: {row[1]}"},
            {"type": "mrkdwn", "text": f":computer: *{headers[2]}*: {row[2]}"},
        ]
        fields_2 = [
            {
                "type": "mrkdwn",
                "text": f"{vaildation_emoji} *{headers[3]}*\n• " + "\n• ".join(row[3].split(" / "))
            }
        ]

        attachments.append({
            "color": color_fields_1,
            "blocks": [
                {"type": "context", "elements": fields_1},
            ]
        })
        attachments.append({
            "color": color_fields_2,
            "blocks": [
                {"type": "context", "elements": fields_2},
                {"type": "divider"}
            ]
        })

    payload = {"attachments": attachments}
    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    if response.status_code != 200:
        log_error(
            f"Request to Slack returned an error {response.status_code}, "
            f"the response is:\n{response.text}"
        )

def send_slack_blocks_table(title, headers, rows):
    """Slack Blocks Kit을 사용해 테이블 형식으로 메시지를 전송."""
    if not os.getenv("SLACK_WEBHOOK_URL"):
        log_error("Slack Webhook URL이 설정되지 않았습니다.")
        return

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 {title}", "emoji": True},
        },
        {"type": "divider"},
    ]

    # 각 행 데이터를 블록 필드로 구성
    for row in rows:
        # 첫 번째 행 (3열로 배치)
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"🆔 *{headers[0]}:* {row[0]}"},
                {"type": "mrkdwn", "text": f"🌍 *{headers[1]}:* {row[1]}"},
                {"type": "mrkdwn", "text": f"🔸 *{headers[2]}:* {row[2]}"}
            ]
       })
        
        # 두 번째 행 (Validation Results, 전체 폭 사용)
        validation_results = "\n".join(
            [f"{idx + 1}. {error.strip()}" for idx, error in enumerate(row[3].split(" / "))]
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ *{headers[3]}:*\n{validation_results}"
            },
        })
        blocks.append({"type": "divider"})  # 각 인스턴스 사이에 구분선 추가

    payload = {"blocks": blocks}

    try:
        response = requests.post(
            os.getenv("SLACK_WEBHOOK_URL"),
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code != 200:
            log_error(f"Request to Slack returned an error {response.status_code}, the response is:\n{response.text}")
        else:
            log_info("Slack 메시지가 성공적으로 전송되었습니다.")
    except Exception as e:
        log_error(f"Slack 메시지 전송 중 오류 발생: {e}")

def send_slack_message(message):
    """Slack으로 간단한 텍스트 메시지를 전송합니다."""
    if not os.getenv("SLACK_WEBHOOK_URL"):
        log_error("Slack Webhook URL이 설정되지 않았습니다.")
        return

    payload = {"text": message}
    try:
        response = requests.post(os.getenv("SLACK_WEBHOOK_URL"), data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        if response.status_code != 200:
            log_error(f"Slack 메시지 전송 실패: {response.status_code}, {response.text}")
        else:
            log_info("Slack 메시지가 성공적으로 전송되었습니다.")
    except Exception as e:
        log_error(f"Slack 메시지 전송 중 오류 발생: {e}")

def send_slack_table(title, headers, data):
    """테이블 형태의 데이터를 Slack으로 전송합니다."""
    if not os.getenv("SLACK_WEBHOOK_URL"):
        log_error("Slack Webhook URL이 설정되지 않았습니다.")
        return

    # Rich 테이블 생성 및 데이터 추가
    table = Table(title=title, show_header=True, header_style="bold cyan")
    for header in headers:
        table.add_column(header)

    for row in data:
        table.add_row(*[str(item) for item in row])

    # 테이블을 문자열로 변환
    table_string = console.export_text(table)

    # Slack 메시지 준비
    payload = {
        "text": f"```{table_string}```"  # Slack에서 코드 블록으로 테이블 표시
    }

    try:
        response = requests.post(os.getenv("SLACK_WEBHOOK_URL"), data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        if response.status_code != 200:
            log_error(f"Slack 테이블 전송 실패: {response.status_code}, {response.text}")
        else:
            log_info("Slack 테이블이 성공적으로 전송되었습니다.")
    except Exception as e:
        log_error(f"Slack 테이블 전송 중 오류 발생: {e}")

def table_to_text(table):
    """Rich 테이블 객체를 텍스트 형식으로 변환."""
    with console.capture() as capture:
        console.print(table)
    return capture.get()