"""Optional email notification for daily reports."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List


def send_email_report(report_text: str, trade_date: str, email_cfg: Dict[str, Any]) -> None:
    """Send the daily report via SMTP email.

    Args:
        report_text: The formatted report string.
        trade_date: Date string for the subject line.
        email_cfg: Dict with keys: smtp_server, smtp_port, username,
                   password, from_addr, to_addrs.
    """
    if not email_cfg.get("smtp_server"):
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Stock Recommendations — {trade_date}"
    msg["From"] = email_cfg["from_addr"]
    msg["To"] = ", ".join(email_cfg["to_addrs"])

    # Plain text body
    msg.attach(MIMEText(report_text, "plain"))

    with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
        server.starttls()
        server.login(email_cfg["username"], email_cfg["password"])
        server.sendmail(
            email_cfg["from_addr"],
            email_cfg["to_addrs"],
            msg.as_string(),
        )
