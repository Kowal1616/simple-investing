"""
notifications.py
================
Generic notification service for Simple Investing.

Sends error alert emails via a transactional email API.
Provider-agnostic interface — configure via environment variables.
"""

import os
import logging

import requests


class SystemNotifier:
    """
    Generic alert service that sends error notifications by email.

    Required environment variables:
        NOTIFIER_API_KEY      – API key for the transactional email provider.
        NOTIFIER_SENDER_EMAIL – Verified sender email address.
        ADMIN_EMAIL           – Destination address for error alerts.
    """

    _API_ENDPOINT = "https://api.brevo.com/v3/smtp/email"

    def __init__(self):
        self._api_key = os.getenv("NOTIFIER_API_KEY", "")
        self._sender_email = os.getenv("NOTIFIER_SENDER_EMAIL", "")
        self._admin_email = os.getenv("ADMIN_EMAIL", "")

    def _is_configured(self) -> bool:
        """Return True only when all required credentials are present."""
        return bool(self._api_key and self._sender_email and self._admin_email)

    def send_error_alert(self, message: str) -> bool:
        """
        Send an error alert email to the administrator.

        Args:
            message: Plain-text or HTML description of the error.

        Returns:
            True if the request was accepted (HTTP 2xx), False otherwise.
            Never raises an exception — all failures are logged instead.
        """
        if not self._is_configured():
            logging.warning(
                "Notification service not configured — alert skipped. "
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
                logging.info("Error alert sent successfully (status %s).", response.status_code)
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
            logging.error("Failed to send error alert — network error: %s", exc)
            return False
