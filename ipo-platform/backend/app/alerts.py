import smtplib, httpx
from email.message import EmailMessage
from . import config

def send_telegram(text: str):
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    httpx.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
        timeout=15,
    )

def send_email(subject: str, body: str):
    if not (config.SMTP_HOST and config.ALERT_EMAIL_TO):
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_USER, config.ALERT_EMAIL_TO, subject
    msg.set_content(body)
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
        s.starttls()
        s.login(config.SMTP_USER, config.SMTP_PASS)
        s.send_message(msg)

def notify(channel: str, subject: str, body: str):
    if channel in ("telegram", "both"):
        send_telegram(f"{subject}\n{body}")
    if channel in ("email", "both"):
        send_email(subject, body)
