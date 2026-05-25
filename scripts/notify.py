"""
SMTP 기반 이메일 알림.

환경변수:
  SMTP_HOST       (예: smtp.gmail.com)
  SMTP_PORT       (기본 465 = SSL, 또는 587 = STARTTLS)
  SMTP_USER       발신 계정 (예: yourname@gmail.com)
  SMTP_PASSWORD   앱 비밀번호 (Gmail은 일반 비번 X, 반드시 '앱 비밀번호')
  MAIL_FROM       From 헤더 (보통 SMTP_USER와 동일)
  MAIL_TO         수신자. ',' 로 여러 명 가능

Gmail 사용 시:
  1) 2단계 인증 활성화
  2) https://myaccount.google.com/apppasswords 에서 '앱 비밀번호' 발급
  3) 발급된 16자리를 SMTP_PASSWORD 로 사용
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def _env(name: str, required: bool = True, default: str | None = None) -> str | None:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"env var {name} is required")
    return val


def send_notification(subject: str, body: str) -> None:
    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", required=False, default="465") or "465")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASSWORD")
    mail_from = _env("MAIL_FROM", required=False) or user
    mail_to_raw = _env("MAIL_TO")
    recipients = [addr.strip() for addr in (mail_to_raw or "").split(",") if addr.strip()]

    if not recipients:
        raise RuntimeError("MAIL_TO has no valid recipients")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    context = ssl.create_default_context()

    if port == 465:
        # SSL
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        # STARTTLS (587 등)
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)


if __name__ == "__main__":
    # 로컬에서 알림 자체만 테스트하고 싶을 때:
    #   $ SMTP_HOST=... SMTP_USER=... SMTP_PASSWORD=... MAIL_TO=... python scripts/notify.py
    send_notification(
        subject="[TEST] Cartier stock watcher",
        body="이 메일이 보이면 SMTP 설정이 정상입니다.",
    )
    print("test mail sent")
