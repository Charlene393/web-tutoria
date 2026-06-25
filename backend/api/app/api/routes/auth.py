from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...schemas.requests import AuthLoginRequest, AuthRegisterRequest
from ...schemas.responses import AuthTokenResponse, AuthUserResponse
from ...services.auth_service import get_current_user, login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer token format.",
        )

    return token.strip()


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: AuthRegisterRequest,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    return register_user(request, db)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    request: AuthLoginRequest,
    db: Session = Depends(get_db),
) -> AuthTokenResponse:
    return login_user(request, db)


@router.get("/me", response_model=AuthUserResponse)
def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    token = _extract_bearer_token(authorization)
    user = get_current_user(token, db)
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
    )
