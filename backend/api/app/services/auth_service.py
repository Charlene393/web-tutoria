from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.models import User
from ..db.session import initialize_database
from ..schemas.requests import AuthLoginRequest, AuthRegisterRequest
from ..schemas.responses import AuthTokenResponse, AuthUserResponse

try:
    from pwdlib import PasswordHash

    password_hash = PasswordHash.recommended()
except Exception:
    password_hash = None

PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _build_user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
    )


def _hash_password(password: str) -> str:
    if password_hash is not None:
        return password_hash.hash(password)

    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"{PBKDF2_SCHEME}${PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def _verify_password(password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(f"{PBKDF2_SCHEME}$"):
        try:
            _, iterations_raw, salt_b64, digest_b64 = hashed_password.split("$", 3)
            iterations = int(iterations_raw)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected_digest = base64.b64decode(digest_b64.encode("ascii"))
        except Exception:
            return False

        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(actual_digest, expected_digest)

    if password_hash is None:
        return False

    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False


def _create_access_token(user: User) -> str:
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.auth_access_token_expire_minutes
    )
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )


def register_user(request: AuthRegisterRequest, db: Session) -> AuthTokenResponse:
    initialize_database()

    password = request.password.strip()
    if len(password) < settings.auth_password_min_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Password must be at least "
                f"{settings.auth_password_min_length} characters long."
            ),
        )

    normalized_email = _normalize_email(request.email)
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        email=normalized_email,
        full_name=request.full_name.strip() if request.full_name else None,
        password_hash=_hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthTokenResponse(
        access_token=_create_access_token(user),
        user=_build_user_response(user),
        status="ok",
    )


def login_user(request: AuthLoginRequest, db: Session) -> AuthTokenResponse:
    initialize_database()

    normalized_email = _normalize_email(request.email)
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not _verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    return AuthTokenResponse(
        access_token=_create_access_token(user),
        user=_build_user_response(user),
        status="ok",
    )


def get_current_user(access_token: str, db: Session) -> User:
    initialize_database()

    try:
        payload = jwt.decode(
            access_token,
            settings.auth_jwt_secret,
            algorithms=[settings.auth_jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        ) from exc

    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token payload.",
        )

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token subject.",
        ) from exc

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
        )

    return user
