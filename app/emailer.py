"""Sends email. Without SMTP settings the message is printed in the terminal instead,
so the whole flow can be tested on a laptop with no mail server."""
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("neuroscan.email")


def email_configured() -> bool:
    return bool(settings.SMTP_HOST)


last_error = ""   # why the most recent send failed (shown to the admin by the test button)


def send_email(to: str, subject: str, body: str) -> bool:
    """Returns True if it was handed to a mail server. Never raises: email must not break a request."""
    global last_error
    last_error = ""
    if not email_configured():
        last_error = "SMTP_HOST is empty in .env, so email is switched off."
        log.warning("EMAIL NOT SENT (SMTP_HOST is empty). Printing it here instead.\n"
                    "To: %s\nSubject: %s\n\n%s", to, subject, body)
        return False
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            if settings.SMTP_TLS:
                server.starttls()
        with server:
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception as exc:  # noqa: BLE001
        last_error = f"{type(exc).__name__}: {exc}"
        log.exception("Could not send email to %s", to)
        return False


SIGNATURE = "\n\nNeuroScan AI\nThis is an automated message."


def approved_email(name: str) -> tuple:
    return ("Your NeuroScan AI account has been approved",
            f"Hello {name},\n\nThe administrator has approved your registration. "
            f"You can now log in and upload MRI images:\n{settings.APP_BASE_URL}/login{SIGNATURE}")


def rejected_email(name: str, reason: str, revoked: bool) -> tuple:
    what = "Your access to NeuroScan AI has been removed." if revoked else "Your NeuroScan AI registration was not approved."
    why = f"\n\nReason: {reason}" if reason else ""
    return (what.rstrip("."), f"Hello {name},\n\n{what}{why}\n\nIf you think this is a mistake, please contact the administrator.{SIGNATURE}")


def reset_email(name: str, link: str) -> tuple:
    return ("Reset your NeuroScan AI password",
            f"Hello {name},\n\nUse this link to choose a new password. It works once and expires in "
            f"{settings.RESET_TOKEN_MINUTES} minutes:\n{link}\n\nIf you did not ask for this, ignore this email; "
            f"your password stays the same.{SIGNATURE}")


def new_registration_email(doctor) -> tuple:
    return (f"New doctor registration: {doctor.full_name}",
            f"A doctor is waiting for your review.\n\nName: {doctor.full_name}\nEmail: {doctor.email}\n"
            f"Institution: {doctor.institution}\nDesignation: {doctor.designation}\n"
            f"License number: {doctor.license_number}\n\nReview it here:\n{settings.APP_BASE_URL}/admin#pending{SIGNATURE}")
