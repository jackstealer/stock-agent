import os

import requests
from dotenv import load_dotenv


def send_alert(text: str) -> bool:
    """Print the message, and send it to Telegram if credentials are configured."""
    print(text)
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat or token.startswith("your_"):
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": text[:4000]}, timeout=10)
        return r.ok
    except requests.RequestException:
        return False