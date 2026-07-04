from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_service import (
    end_session,
    get_current_user,
    hash_password,
    start_session,
    verify_password,
)
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_view(u: User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name}


class RegisterBody(BaseModel):
    email: str
    name: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("enter a valid email address")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name is required")
        return v.strip()

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterBody, response: Response, db: Session = Depends(get_db)) -> dict:
    existing = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "an account with this email already exists")
    user = User(email=body.email, name=body.name, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    start_session(db, user, response)
    db.commit()
    return _user_view(user)


@router.post("/login")
def login(body: LoginBody, response: Response, db: Session = Depends(get_db)) -> dict:
    user = db.execute(
        select(User).where(User.email == body.email.strip().lower())
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "wrong email or password")
    start_session(db, user, response)
    db.commit()
    return _user_view(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    end_session(db, request, response)
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return _user_view(user)
