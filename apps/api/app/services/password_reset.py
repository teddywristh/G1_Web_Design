"""Email OTP with expiry, limited attempts and session revocation."""

import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

import bcrypt
from firebase_admin import auth

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.firebase import initialize_firebase
from app.repositories.backend import utcnow


def send_email(email, otp):
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = "Legal AI - Mã khôi phục mật khẩu"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = email
    message.set_content(
        f"Mã OTP của bạn: {otp}\nCó hiệu lực 10 phút và chỉ dùng một lần.\n"
        "Nếu không yêu cầu đổi mật khẩu, hãy bỏ qua email này."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise APIError(503, "mail_unavailable", "Email delivery is unavailable") from None


def request_otp(repo, email, request_id):
    settings = get_settings()
    if not (
        settings.smtp_host and settings.smtp_username and settings.smtp_password.get_secret_value()
    ):
        raise APIError(503, "mail_not_configured", "Email delivery is not configured")
    initialize_firebase()
    now, otp = utcnow(), f"{secrets.randbelow(1000000):06d}"
    key = hashlib.sha256(email.encode()).hexdigest()
    salt = secrets.token_hex(32)
    try:
        identity = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        identity = None

    def reserve(current):
        if current and current["sentAt"] > now - timedelta(seconds=60):
            raise APIError(429, "otp_cooldown", "Wait before requesting another code")
        return {
            "sentAt": now,
            "expiresAt": now + timedelta(minutes=10),
            "salt": salt,
            "digest": hashlib.sha256((salt + otp).encode()).hexdigest(),
            "attempts": 0,
            "consumed": False,
            "userId": identity.uid if identity and not identity.disabled else None,
        }

    repo.mutate(
        "password_resets",
        key,
        reserve,
        actor="anonymous",
        event="auth.reset_requested",
        request_id=request_id,
    )
    if identity and not identity.disabled:
        send_email(email, otp)


def reset_password(repo, body, request_id):
    initialize_firebase()
    key = hashlib.sha256(body.email.encode()).hexdigest()
    now = utcnow()
    verified_uid = None

    def consume(current):
        nonlocal verified_uid
        if (
            not current
            or current["consumed"]
            or current["expiresAt"] <= now
            or current["attempts"] >= 5
        ):
            raise APIError(400, "invalid_otp", "Code is invalid or expired")
        valid = hmac.compare_digest(
            current["digest"], hashlib.sha256((current["salt"] + body.otp).encode()).hexdigest()
        )
        verified_uid = current.get("userId") if valid else None
        return {"attempts": current["attempts"] + 1, "consumed": valid}

    repo.mutate(
        "password_resets",
        key,
        consume,
        actor="anonymous",
        event="auth.reset_verified",
        request_id=request_id,
    )
    if not verified_uid:
        raise APIError(400, "invalid_otp", "Code is invalid or expired")
    try:
        identity = auth.get_user(verified_uid)
    except auth.UserNotFoundError:
        raise APIError(400, "invalid_otp", "Code is invalid or expired") from None
    profile = repo.get("users", verified_uid)
    if (
        identity.email.lower() != body.email
        or identity.disabled
        or not profile
        or not profile.get("isActive")
    ):
        raise APIError(400, "invalid_otp", "Code is invalid or expired")
    # Đồng bộ cả tài khoản Firebase cũ và mật khẩu ứng dụng.
    auth.update_user(verified_uid, password=body.password.get_secret_value())
    encoded = bcrypt.hashpw(
        body.password.get_secret_value().encode(), bcrypt.gensalt(rounds=12)
    ).decode()

    def update(current):
        if not current or not current.get("isActive") or identity.disabled:
            raise APIError(400, "invalid_otp", "Code is invalid or expired")
        return {
            "passwordHash": encoded,
            "authSessionVersion": current.get("authSessionVersion", 0) + 1,
        }

    repo.mutate(
        "users",
        identity.uid,
        update,
        actor=identity.uid,
        event="auth.password_reset",
        request_id=request_id,
    )
    auth.revoke_refresh_tokens(identity.uid)
