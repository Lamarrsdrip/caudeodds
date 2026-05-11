"""SMTP / Email service for ClaudeOdds.

Uses standard library `smtplib` + `ssl` so we don't need extra deps. Reads
config from db.admin_config (smtp_host, smtp_port, smtp_user, smtp_password,
smtp_from_email). Provides:

  • test_smtp_connection(cfg)      — verify SMTP credentials without sending
  • send_email(cfg, to, subj, html, text)  — send a single email
  • send_welcome(cfg, to_email, name)      — convenience: welcome on register
  • send_password_changed(cfg, to_email, name)  — convenience: pw change conf

All operations classify failures into actionable user-facing error messages
(wrong password / invalid app password / SMTP blocked / TLS issue / etc.)
and log every send into db.email_logs for delivery-status tracking.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import socket
import ssl
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional, Tuple

logger = logging.getLogger("claudeodd.email")

CONNECT_TIMEOUT = 10  # seconds — keep short so admin UI doesn't hang


# ─────────────────────────────────────────────────────────────────────────────
# Error classification — convert raw SMTP exceptions into clear UI messages
# ─────────────────────────────────────────────────────────────────────────────

def _classify_error(exc: Exception) -> Tuple[str, str]:
    """Returns (error_class, user_message) for any SMTP exception."""
    msg = str(exc)
    low = msg.lower()
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        # Gmail returns very specific messages we can map to clearer help
        if "application-specific password" in low or "app password" in low:
            return ("INVALID_APP_PASSWORD",
                    "Gmail requires an App Password (not your regular password). "
                    "Generate one at https://myaccount.google.com/apppasswords and "
                    "paste it as the SMTP password.")
        if "username and password not accepted" in low or "535" in low:
            return ("WRONG_PASSWORD",
                    "Username or password was rejected by Gmail. Double-check the SMTP "
                    "username (your Gmail address) and password (the 16-char App Password, "
                    "not your account password).")
        return ("AUTH_FAILED", f"Gmail authentication failed: {msg[:200]}")
    if isinstance(exc, smtplib.SMTPConnectError):
        return ("SMTP_BLOCKED",
                "Could not connect to the SMTP server. Your network or hosting "
                f"provider may be blocking outbound port 587/465. Detail: {msg[:200]}")
    if isinstance(exc, ssl.SSLError) or "tls" in low or "ssl" in low:
        return ("TLS_ERROR",
                f"TLS/SSL handshake failed with the SMTP server. Detail: {msg[:200]}")
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return ("TIMEOUT",
                f"Connection to SMTP server timed out after {CONNECT_TIMEOUT}s.")
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return ("BAD_RECIPIENT",
                f"Recipient address was rejected by the SMTP server: {msg[:200]}")
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return ("BAD_SENDER",
                f"Sender address was rejected. Make sure smtp_from_email matches a verified address. Detail: {msg[:200]}")
    if "name or service not known" in low or "getaddrinfo" in low:
        return ("HOST_NOT_FOUND",
                "Could not resolve the SMTP host. Check `smtp_host` (e.g. smtp.gmail.com).")
    return ("UNKNOWN", f"SMTP error: {msg[:300]}")


# ─────────────────────────────────────────────────────────────────────────────
# Core blocking SMTP routine — wrapped in asyncio.to_thread by callers
# ─────────────────────────────────────────────────────────────────────────────

def _smtp_send_sync(cfg: Dict, to: str, subject: str, html: str, text: str) -> Tuple[bool, str, str]:
    """Returns (ok, error_class, message)."""
    host = (cfg.get("smtp_host") or "").strip()
    port = int(cfg.get("smtp_port") or 587)
    user = (cfg.get("smtp_user") or "").strip()
    password = cfg.get("smtp_password") or ""
    from_email = (cfg.get("smtp_from_email") or user).strip()
    if not (host and user and password and from_email):
        return False, "MISSING_CONFIG", "SMTP host / user / password / from_email must all be set in Admin → Configuration."

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=CONNECT_TIMEOUT, context=ctx) as server:
                server.login(user, password)
                server.sendmail(from_email, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=CONNECT_TIMEOUT) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(user, password)
                server.sendmail(from_email, [to], msg.as_string())
        return True, "OK", "Sent successfully."
    except Exception as e:
        ec, em = _classify_error(e)
        logger.warning("SMTP send to %s failed: %s — %s", to, ec, em)
        return False, ec, em


def _smtp_test_sync(cfg: Dict) -> Tuple[bool, str, str]:
    """Verify SMTP credentials without sending a message."""
    host = (cfg.get("smtp_host") or "").strip()
    port = int(cfg.get("smtp_port") or 587)
    user = (cfg.get("smtp_user") or "").strip()
    password = cfg.get("smtp_password") or ""
    if not (host and user and password):
        return False, "MISSING_CONFIG", "SMTP host / user / password must all be set."
    try:
        if port == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=CONNECT_TIMEOUT, context=ctx) as server:
                server.login(user, password)
                server.noop()
        else:
            with smtplib.SMTP(host, port, timeout=CONNECT_TIMEOUT) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(user, password)
                server.noop()
        return True, "OK", f"Connected to {host}:{port} as {user}. SMTP is working."
    except Exception as e:
        ec, em = _classify_error(e)
        return False, ec, em


# ─────────────────────────────────────────────────────────────────────────────
# Async wrappers + DB logging
# ─────────────────────────────────────────────────────────────────────────────

async def test_smtp_connection(cfg: Dict) -> Dict:
    ok, ec, em = await asyncio.to_thread(_smtp_test_sync, cfg)
    return {"ok": ok, "error_class": ec, "message": em,
            "host": cfg.get("smtp_host"), "port": cfg.get("smtp_port"),
            "user": cfg.get("smtp_user")}


async def send_email(db, cfg: Dict, to: str, subject: str, html: str,
                     text: Optional[str] = None, kind: str = "manual",
                     meta: Optional[Dict] = None) -> Dict:
    """Send + log. Returns the email_logs document."""
    text = text or _html_to_text(html)
    ok, ec, em = await asyncio.to_thread(_smtp_send_sync, cfg, to, subject, html, text)
    log = {
        "id": str(uuid.uuid4()),
        "to": to,
        "subject": subject,
        "kind": kind,
        "status": "sent" if ok else "failed",
        "error_class": ec if not ok else None,
        "error": em if not ok else None,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta or {},
    }
    try:
        await db.email_logs.insert_one(log.copy())
    except Exception as e:
        logger.warning("Could not persist email_log: %s", e)
    return log


# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    """Very small HTML→text fallback."""
    import re
    return re.sub(r"<[^>]+>", "", html).strip()


_BRAND = "ClaudeOdds"
_FOOTER_HTML = (
    "<p style='color:#888;font-size:12px;margin-top:32px'>"
    "You're receiving this because you registered at ClaudeOdds. "
    "18+ only. Bet responsibly."
    "</p>"
)


def template_welcome(name: str) -> Tuple[str, str]:
    subject = f"Welcome to {_BRAND} — your 3-day free trial is active"
    html = (
        f"<div style='font-family:Inter,Arial,sans-serif;background:#0a0a0a;color:#f5f5f5;padding:24px;max-width:560px'>"
        f"<h1 style='color:#00ff66;font-size:24px;margin:0 0 16px'>Welcome, {name}.</h1>"
        f"<p>Your 3-day free trial is now active. Every day at 09:00 Lagos we publish one combined slip "
        f"with total odds between 2.0 and 5.0 — copy the SportyBet code straight from your dashboard.</p>"
        f"<p><a href='https://claudeodds.com/dashboard' style='display:inline-block;background:#00ff66;color:#050505;padding:12px 20px;text-decoration:none;font-weight:bold'>Open today's slip →</a></p>"
        f"<p style='color:#aaa;font-size:14px'>Trial expires after 3 days. Subscribe for ₦5,000/month to keep the picks coming.</p>"
        f"{_FOOTER_HTML}"
        f"</div>"
    )
    return subject, html


def template_password_changed(name: str, when_iso: str, ip: str = "") -> Tuple[str, str]:
    subject = f"{_BRAND} — your password was changed"
    ip_line = f"<br/>From IP: <code>{ip}</code>" if ip else ""
    html = (
        f"<div style='font-family:Inter,Arial,sans-serif;background:#0a0a0a;color:#f5f5f5;padding:24px;max-width:560px'>"
        f"<h1 style='color:#00ff66;font-size:22px;margin:0 0 16px'>Password changed</h1>"
        f"<p>Hi {name}, your ClaudeOdds password was changed on {when_iso}.{ip_line}</p>"
        f"<p>If you didn't do this, reset your password immediately and email support.</p>"
        f"{_FOOTER_HTML}"
        f"</div>"
    )
    return subject, html


def template_test() -> Tuple[str, str]:
    subject = f"{_BRAND} — SMTP test message"
    html = (
        "<div style='font-family:Inter,Arial,sans-serif;background:#0a0a0a;color:#f5f5f5;padding:24px;max-width:560px'>"
        "<h1 style='color:#00ff66;font-size:22px;margin:0 0 16px'>SMTP test ✓</h1>"
        "<p>If you can read this, your Gmail / SMTP setup is working end-to-end.</p>"
        f"{_FOOTER_HTML}"
        "</div>"
    )
    return subject, html
