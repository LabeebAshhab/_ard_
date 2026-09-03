"""For building and sending the delivery e-mail with the CSV file."""

import mimetypes
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from .config import config


def _address(recipient: dict) -> str:
    return formataddr((recipient.get("display_name") or "", recipient["email_address"]))


def build_message(email_cfg: dict, recipients: list[dict],
                  attachments: list[Path]) -> tuple[EmailMessage, list[str]]:
    """Return the message and the full envelope list (To + Cc + Bcc)."""
    msg = EmailMessage()
    msg["From"] = config.smtp_from
    msg["Subject"] = email_cfg["subject"]

    envelope = []
    for header in ("TO", "CC"):
        picked = [_address(r) for r in recipients if r["recipient_type"] == header]
        if picked:
            msg[header.capitalize()] = ", ".join(picked)
    
    for r in recipients:
        envelope.append(r["email_address"])

    body = email_cfg.get("body") or ""
    signature = email_cfg.get("signature") or ""
    msg.set_content(f"{body}\n\n{signature}".strip())

    for path in attachments:
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, _, subtype = (ctype or "text/csv").partition("/")
        msg.add_attachment(
            path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name
        )
    return msg, envelope


def send(email_cfg: dict, recipients: list[dict], attachments: list[Path]) -> datetime:
    """Send the mail and return the moment it was accepted."""
    msg, envelope = build_message(email_cfg, recipients, attachments)
    if not envelope:
        raise ValueError("no active recipients for this task")
    """Writting log in .eml file."""
    if config.smtp_dry_run:
        path = config.log_dir / f"dryrun_{datetime.now():%Y%m%d_%H%M%S}_cfg{email_cfg['config_id']}.eml"
        path.write_bytes(bytes(msg))
        return datetime.now()

    with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=60) as server:
        if config.smtp_use_tls:
            server.starttls()
        if config.smtp_user:
            server.login(config.smtp_user, config.smtp_password)
        server.send_message(msg, from_addr=config.smtp_from, to_addrs=envelope)
    return datetime.now()
