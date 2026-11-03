"""Checks your Telegram setup. Run from the backend folder:  python -m app.test_alert"""
import httpx
from . import config

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        return print("TELEGRAM_BOT_TOKEN is empty in .env")
    if not config.TELEGRAM_CHAT_ID:
        return print("TELEGRAM_CHAT_ID is empty in .env")
    r = httpx.post(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": config.TELEGRAM_CHAT_ID, "text": "IPO platform test alert: it works!"},
        timeout=15)
    print("Status:", r.status_code)
    print(r.json())
    if r.status_code == 200:
        print("\nSuccess. Check your Telegram.")
    elif r.status_code == 401:
        print("\nToken is wrong. Copy it again from BotFather.")
    elif r.status_code == 400:
        print("\nChat ID is wrong, or you haven't sent your bot a message yet.")

if __name__ == "__main__":
    main()
