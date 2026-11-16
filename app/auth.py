import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select

from app.database import SessionLocal
from app.models import User

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

SECRET = os.getenv("JWT_SECRET")
if not SECRET:
    raise RuntimeError("JWT_SECRET is missing in your .env file")

ALGORITHM = "HS256"
TOKEN_HOURS = 24

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


class SignupRequest(BaseModel):
    email: str
    password: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2)) -> User:
    try:
        user_id = int(jwt.decode(token, SECRET, algorithms=[ALGORITHM])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    with SessionLocal() as db:
        user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/signup")
def signup(req: SignupRequest):
    email = req.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email")
    if not 8 <= len(req.password.encode()) <= 72:
        raise HTTPException(status_code=400, detail="Password must be 8 to 72 characters")

    with SessionLocal() as db:
        if db.scalars(select(User).where(User.email == email)).first():
            raise HTTPException(status_code=409, detail="Email already registered")
        user = User(email=email, password_hash=hash_password(req.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    email = form.username.strip().lower()
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == email)).first()

    if (
        user is None
        or len(form.password.encode()) > 72
        or not verify_password(form.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return {"access_token": create_token(user.id), "token_type": "bearer"}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}