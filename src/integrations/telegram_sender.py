import os

import requests

from logger import get_logger


logger = get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


def send_message(text, token=None, chat_id=None, timeout=10):
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning(
            "Telegram send skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing"
        )
        return {
            "success": False,
            "reason": "missing_telegram_env",
            "message": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.",
        }

    try:
        response = requests.post(
            f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.error("Telegram send failed: %s", error)
        return {
            "success": False,
            "reason": "telegram_request_failed",
            "message": str(error),
        }

    logger.info("Telegram message sent")
    return {"success": True, "reason": "", "message": "sent"}
