import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuthSession, User, utcnow

hasher = PasswordHasher()
SESSION_COOKIE = "taskflow_session"
CSRF_COOKIE = "taskflow_csrf"


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def validate_timezone(name: str) -> None:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Unknown IANA time zone") from exc


def create_session(db: Session, user: User, response: Response) -> None:
    settings = get_settings()
    raw_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            id=sha256(raw_id.encode()).hexdigest(),
            user_id=user.id,
            csrf_token=csrf_token,
            expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
        )
    )
    response.set_cookie(
        SESSION_COOKIE,
        raw_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )


def current_user(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> User:
    if not session_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    session_id = sha256(session_cookie.encode()).hexdigest()
    auth_session = db.scalar(select(AuthSession).where(AuthSession.id == session_id))
    if auth_session is None or _as_utc(auth_session.expires_at) <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    user = db.get(User, auth_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return user


def require_csrf(
    db: Session = Depends(get_db),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    if not session_cookie or not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    session_id = sha256(session_cookie.encode()).hexdigest()
    auth_session = db.get(AuthSession, session_id)
    if (
        auth_session is None
        or _as_utc(auth_session.expires_at) <= utcnow()
        or not secrets.compare_digest(auth_session.csrf_token, csrf_header)
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
