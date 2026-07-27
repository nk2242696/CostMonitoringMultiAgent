"""
Notification Service

Sends alert notifications via Email, Slack, and Microsoft Teams.
Channel configuration is read from the YAML config file.
"""

import json
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import requests

from src.models import CostAlert

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Dispatches alert notifications to configured channels.

    Supported channels:
      - email  (SMTP)
      - slack  (Incoming Webhook)
      - teams  (Incoming Webhook / Workflow)
    """

    def __init__(self, channel_config: Dict[str, Any]):
        """
        Args:
            channel_config: alerting.notification_channels section from YAML config.
        """
        self.config = channel_config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def notify(self, alert: CostAlert, channels: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Send alert to all requested channels.

        Args:
            alert:    The alert instance.
            channels: Channel names to notify.  Falls back to alert.notification_channels.

        Returns:
            Mapping of channel → success boolean.
        """
        channels = channels or alert.notification_channels or []
        results: Dict[str, bool] = {}

        for channel in channels:
            try:
                if channel == "email":
                    self._send_email(alert)
                elif channel == "slack":
                    self._send_slack(alert)
                elif channel == "teams":
                    self._send_teams(alert)
                else:
                    logger.warning("Unknown notification channel: %s", channel)
                    results[channel] = False
                    continue
                results[channel] = True
            except Exception:
                logger.exception("Failed to send %s notification for alert %s", channel, alert.alert_id)
                results[channel] = False

        return results

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    def _send_email(self, alert: CostAlert) -> None:
        email_cfg = self.config.get("email", {})
        if not email_cfg.get("enabled"):
            logger.debug("Email notifications disabled")
            return

        smtp_host = email_cfg["smtp_host"]
        smtp_port = email_cfg.get("smtp_port", 587)
        use_tls = email_cfg.get("use_tls", True)
        username = email_cfg.get("username", "")
        password = email_cfg.get("password", "")
        from_addr = email_cfg.get("from_address", username)
        to_addrs = email_cfg.get("recipients", [from_addr])

        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            alert.severity, "⚪"
        )

        subject = f"{severity_emoji} [{alert.severity.upper()}] {alert.title}"

        body = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2>{severity_emoji} Cost Alert: {alert.title}</h2>
<table style="border-collapse: collapse; width: 100%;">
  <tr><td style="padding: 8px; font-weight: bold;">Alert Type</td><td style="padding: 8px;">{alert.alert_type}</td></tr>
  <tr><td style="padding: 8px; font-weight: bold;">Severity</td><td style="padding: 8px;">{alert.severity}</td></tr>
  <tr><td style="padding: 8px; font-weight: bold;">Subscription</td><td style="padding: 8px;">{alert.subscription_id}</td></tr>
  <tr><td style="padding: 8px; font-weight: bold;">Current Value</td><td style="padding: 8px;">${alert.current_value:,.2f}</td></tr>
  <tr><td style="padding: 8px; font-weight: bold;">Threshold</td><td style="padding: 8px;">${alert.threshold_value:,.2f}</td></tr>
</table>
<p>{alert.description}</p>
<hr/>
<p style="font-size: 12px; color: #999;">Azure Cost Optimization Agent</p>
</body>
</html>
"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.send_message(msg)

        logger.info("Email sent for alert %s", alert.alert_id)

    # ------------------------------------------------------------------
    # Slack
    # ------------------------------------------------------------------

    def _send_slack(self, alert: CostAlert) -> None:
        slack_cfg = self.config.get("slack", {})
        if not slack_cfg.get("enabled"):
            logger.debug("Slack notifications disabled")
            return

        webhook_url = slack_cfg["webhook_url"]
        channel = slack_cfg.get("default_channel", "#azure-costs")

        severity_color = {
            "critical": "#FF0000",
            "high": "#FF8C00",
            "medium": "#FFD700",
            "low": "#32CD32",
        }.get(alert.severity, "#808080")

        payload = {
            "channel": channel,
            "attachments": [
                {
                    "color": severity_color,
                    "title": f"[{alert.severity.upper()}] {alert.title}",
                    "text": alert.description,
                    "fields": [
                        {"title": "Alert Type", "value": alert.alert_type, "short": True},
                        {"title": "Subscription", "value": alert.subscription_id or "N/A", "short": True},
                        {"title": "Current Value", "value": f"${alert.current_value:,.2f}", "short": True},
                        {"title": "Threshold", "value": f"${alert.threshold_value:,.2f}", "short": True},
                    ],
                    "footer": "Azure Cost Optimization Agent",
                    "ts": int(alert.fired_at.timestamp()) if alert.fired_at else None,
                }
            ],
        }

        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Slack notification sent for alert %s", alert.alert_id)

    # ------------------------------------------------------------------
    # Microsoft Teams
    # ------------------------------------------------------------------

    def _send_teams(self, alert: CostAlert) -> None:
        teams_cfg = self.config.get("teams", {})
        if not teams_cfg.get("enabled"):
            logger.debug("Teams notifications disabled")
            return

        webhook_url = teams_cfg["webhook_url"]

        severity_color = {
            "critical": "FF0000",
            "high": "FF8C00",
            "medium": "FFD700",
            "low": "32CD32",
        }.get(alert.severity, "808080")

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": severity_color,
            "summary": alert.title,
            "sections": [
                {
                    "activityTitle": f"**[{alert.severity.upper()}]** {alert.title}",
                    "activitySubtitle": f"Alert Type: {alert.alert_type}",
                    "facts": [
                        {"name": "Subscription", "value": alert.subscription_id or "N/A"},
                        {"name": "Current Value", "value": f"${alert.current_value:,.2f}"},
                        {"name": "Threshold", "value": f"${alert.threshold_value:,.2f}"},
                        {"name": "Fired At", "value": str(alert.fired_at)},
                    ],
                    "text": alert.description,
                    "markdown": True,
                }
            ],
        }

        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Teams notification sent for alert %s", alert.alert_id)
