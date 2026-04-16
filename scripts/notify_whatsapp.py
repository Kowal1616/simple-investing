#!/usr/bin/env python3
"""
ZenETFs - WhatsApp deployment notification via CallMeBot API.
Reads CALLMEBOT_API_KEY and MY_PHONE_NUMBER from environment variables.
"""

import os
import sys
import requests
from urllib.parse import quote


def send_whatsapp_notification() -> None:
    api_key = os.environ.get("CALLMEBOT_API_KEY")
    phone = os.environ.get("MY_PHONE_NUMBER")

    if not api_key or not phone:
        print(
            "[notify_whatsapp] ERROR: Missing CALLMEBOT_API_KEY or MY_PHONE_NUMBER "
            "environment variables. Skipping notification.",
            file=sys.stderr,
        )
        return

    message = (
        "🛠 ZenETFs: Nowy kod został przesłany do rejestru (GHCR). Serwer wkrótce pobierze aktualizację."
    )
    encoded_message = quote(message)

    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={phone}&text={encoded_message}&apikey={api_key}"
    )

    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            print("[notify_whatsapp] ✅ WhatsApp notification sent successfully.")
        else:
            print(
                f"[notify_whatsapp] ⚠️  Unexpected response: "
                f"HTTP {response.status_code} — {response.text[:200]}",
                file=sys.stderr,
            )
    except requests.exceptions.ConnectionError as exc:
        print(
            f"[notify_whatsapp] ⚠️  Connection error – skipping notification: {exc}",
            file=sys.stderr,
        )
    except requests.exceptions.Timeout:
        print(
            "[notify_whatsapp] ⚠️  Request timed out – skipping notification.",
            file=sys.stderr,
        )
    except requests.exceptions.RequestException as exc:
        print(
            f"[notify_whatsapp] ⚠️  Request failed – skipping notification: {exc}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    send_whatsapp_notification()
