"""Authentication + per-deal authorization.

POC-grade but honest: salted PBKDF2-SHA256 (600k iterations, OWASP-level),
random 256-bit session tokens in an httpOnly SameSite=Lax cookie, per-deal
role checks on every route. NOT yet included (needed before a real pilot):
email verification, rate limiting, TLS enforcement (set the cookie 'secure'
flag behind HTTPS), 2FA/SSO.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Deal, DealMember, SessionToken, User

COOKIE_NAME = "dd_session"
SESSION_DAYS = 7
PBKDF2_ITERATIONS = 600_000

ROLE_ORDER = {"viewer": 0, "reviewer": 1, "editor": 2, "owner": 3}


# ---- passwords -------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    )
    return secrets.compare_digest(dk.hex(), dk_hex)


# ---- sessions ---------------------------------------------------------------
def start_session(db: Session, user: User, response: Response) -> None:
    token = secrets.token_hex(32)
    db.add(SessionToken(
        token=token,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
    ))
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite="lax", max_age=SESSION_DAYS * 86400, path="/",
    )


def end_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.query(SessionToken).filter(SessionToken.token == token).delete()
    response.delete_cookie(COOKIE_NAME, path="/")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "not signed in")
    row = db.get(SessionToken, token)
    if row is None:
        raise HTTPException(401, "session expired — sign in again")
    expires = row.expires_at
    if expires.tzinfo is None:  # SQLite returns naive datetimes
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        raise HTTPException(401, "session expired — sign in again")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(401, "unknown user")
    return user


# ---- per-deal authorization --------------------------------------------------
def role_for(db: Session, user: User, deal_id: str) -> str | None:
    m = db.execute(
        select(DealMember).where(
            DealMember.deal_id == deal_id, DealMember.user_id == user.id
        )
    ).scalar_one_or_none()
    return m.role if m else None


def claim_if_orphan(db: Session, user: User, deal: Deal) -> str | None:
    """Deals created before auth existed have no members; the first
    authenticated user to open one becomes its owner (audited)."""
    any_member = db.execute(
        select(DealMember).where(DealMember.deal_id == deal.id).limit(1)
    ).scalar_one_or_none()
    if any_member is not None:
        return None
    from app.audit import record_event

    db.add(DealMember(deal_id=deal.id, user_id=user.id, role="owner"))
    record_event(
        db, event_type="access_granted", actor=user.email, deal_id=deal.id,
        output_ref={"user": user.email, "role": "owner", "reason": "legacy deal claimed"},
    )
    db.flush()
    return "owner"


def ensure_access(db: Session, user: User, deal_id: str, min_role: str) -> str:
    """Return the user's role or raise. 404 (not 403) when the user has no
    membership at all, so deal existence is not leaked."""
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404, "deal not found")
    role = role_for(db, user, deal_id) or claim_if_orphan(db, user, deal)
    if role is None:
        raise HTTPException(404, "deal not found")
    if ROLE_ORDER[role] < ROLE_ORDER[min_role]:
        raise HTTPException(403, f"requires {min_role} access (you are {role})")
    return role
