from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


def _get_serializer():
    secret_key = current_app.config.get("SECRET_KEY")
    return URLSafeTimedSerializer(secret_key=secret_key, salt="trace-token-salt")


def generate_verification_token(email: str) -> str:
    serializer = _get_serializer()
    return serializer.dumps(email, salt="email-verification")


def confirm_verification_token(token: str, expiration: int = 86400) -> str:
    serializer = _get_serializer()
    return serializer.loads(token, max_age=expiration, salt="email-verification")


def generate_password_reset_token(email: str) -> str:
    serializer = _get_serializer()
    return serializer.dumps(email, salt="password-reset")


def confirm_password_reset_token(token: str, expiration: int = 3600) -> str:
    serializer = _get_serializer()
    return serializer.loads(token, max_age=expiration, salt="password-reset")

__all__ = [
    "generate_verification_token",
    "confirm_verification_token",
    "generate_password_reset_token",
    "confirm_password_reset_token",
    "BadSignature",
    "SignatureExpired",
]
