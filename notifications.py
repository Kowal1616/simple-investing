"""
notifications.py
================
Generic notification service for Simple Investing.

Sends error alert emails via a transactional email API.
Provider-agnostic interface — configure via environment variables.
"""

import os
import logging
from urllib.parse import quote

import requests


class SystemNotifier:
    """
    Generic alert service that sends error notifications by email and WhatsApp.

    Required environment variables:
        NOTIFIER_API_KEY      – API key for the transactional email provider.
        NOTIFIER_SENDER_EMAIL – Verified sender email address.
        ADMIN_EMAIL           – Destination address for error alerts.
        CALLMEBOT_API_KEY     – API key for CallMeBot WhatsApp notifications.
        MY_PHONE_NUMBER       – Destination phone number for WhatsApp alerts.
    """

    _API_ENDPOINT = "https://api.brevo.com/v3/smtp/email"

    def __init__(self):
        self._api_key = os.getenv("NOTIFIER_API_KEY", "")
        self._sender_email = os.getenv("NOTIFIER_SENDER_EMAIL", "")
        self._admin_email = os.getenv("ADMIN_EMAIL", "")
        self._whatsapp_api_key = os.getenv("CALLMEBOT_API_KEY", "")
        self._whatsapp_phone = os.getenv("MY_PHONE_NUMBER", "")

    def _is_email_configured(self) -> bool:
        """Return True only when all required email credentials are present."""
        return bool(self._api_key and self._sender_email and self._admin_email)

    def _is_whatsapp_configured(self) -> bool:
        """Return True only when CallMeBot credentials are present."""
        return bool(self._whatsapp_api_key and self._whatsapp_phone)

    def _send_whatsapp(self, message: str) -> bool:
        """Sends a WhatsApp message via CallMeBot API."""
        if not self._is_whatsapp_configured():
            logging.warning("WhatsApp notification not configured. Skipping.")
            return False

        encoded_message = quote(message)
        url = (
            f"https://api.callmebot.com/whatsapp.php"
            f"?phone={self._whatsapp_phone}&text={encoded_message}&apikey={self._whatsapp_api_key}"
        )

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                logging.info("WhatsApp alert sent successfully.")
                return True
            else:
                logging.error(
                    "WhatsApp API returned non-OK status %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                return False
        except requests.RequestException as exc:
            logging.error("Failed to send WhatsApp alert: %s", exc)
            return False

    def send_error_alert(self, message: str) -> bool:
        """
        Send an error alert email and WhatsApp message to the administrator.

        Args:
            message: Plain-text or HTML description of the error.

        Returns:
            True if the email request was accepted (HTTP 2xx), False otherwise.
            Never raises an exception — all failures are logged instead.
        """
        # 1. Send WhatsApp Error Alert
        whatsapp_msg = "⚠️ ZenETFs: BŁĄD podczas aktualizacji danych! Szczegóły wysłano na e-mail (Brevo)."
        self._send_whatsapp(whatsapp_msg)

        # 2. Send Email Error Alert
        if not self._is_email_configured():
            logging.warning(
                "Email notification service not configured — alert skipped. "
                "Set NOTIFIER_API_KEY, NOTIFIER_SENDER_EMAIL, and ADMIN_EMAIL."
            )
            return False

        payload = {
            "sender": {
                "name": "SimpleInvesting Alert",
                "email": self._sender_email,
            },
            "to": [{"email": self._admin_email}],
            "subject": "SimpleInvesting — Application Error Alert",
            "htmlContent": f"<strong>Error:</strong> {message}",
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": self._api_key,
        }

        try:
            response = requests.post(
                self._API_ENDPOINT,
                json=payload,
                headers=headers,
                timeout=10,
            )
            if response.ok:
                logging.info("Error alert email sent successfully (status %s).", response.status_code)
                return True
            else:
                logging.error(
                    "Alert API returned non-OK status %s: %s",
                    response.status_code,
                    response.text,
                )
                return False
        except requests.RequestException as exc:
            # Network error, timeout, etc. — do NOT crash the application.
            logging.error("Failed to send error alert email — network error: %s", exc)
            return False

    def send_info_alert(self, message: str) -> bool:
        """
        Send an informational alert via WhatsApp only.
        
        Args:
            message: Plain-text description of the info/success event.
            
        Returns:
            True if the WhatsApp request was accepted.
        """
        logging.info("Sending info alert via WhatsApp.")
        return self._send_whatsapp(message)
