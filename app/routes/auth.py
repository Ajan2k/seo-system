# app/routes/auth.py
"""
Authentication routes for BlogAI SaaS platform.

PostgreSQL-backed token-based auth via SQLAlchemy async.
Supports signup, login, and user profile endpoints.
"""

import hashlib
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.future import select

from app.models import AsyncSessionLocal, User
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str


# ── Helpers ───────────────────────────────────────────────────────────────

def _hash_password(password: str, salt: str = None) -> tuple:
    """Hash a password with a salt using SHA-256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt


def _generate_token() -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(48)


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("/auth/signup")
async def signup(req: SignupRequest):
    """Create a new user account."""
    async with AsyncSessionLocal() as session:
        # Check if email already exists
        result = await session.execute(
            select(User).where(User.email == req.email.lower())
        )
        existing = result.scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        if len(req.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        # Hash password & create token
        password_hash, salt = _hash_password(req.password)
        token = _generate_token()

        is_admin_flag = 1 if req.email.lower() == "admin@infiniteseo.com" else 0

        # Insert user
        user = User(
            first_name=req.first_name,
            last_name=req.last_name,
            email=req.email.lower(),
            password_hash=password_hash,
            password_salt=salt,
            token=token,
            credits=5,
            plan="free",
            is_admin=is_admin_flag,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    logger.info("User registered", extra={"user_id": user_id, "email": req.email})

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user_id,
            "name": f"{req.first_name} {req.last_name}",
            "email": req.email.lower(),
            "credits": 5,
            "plan": "free",
            "is_admin": is_admin_flag,
        },
        "message": "Account created successfully! You have 5 free credits.",
    }


@router.post("/auth/login")
async def login(req: LoginRequest):
    """Authenticate an existing user."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == req.email.lower())
        )
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        password_hash, _ = _hash_password(req.password, user.password_salt)
        if password_hash != user.password_hash:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Generate new token
        token = _generate_token()
        user.token = token
        user.last_login = time.time()
        await session.commit()

    logger.info("User logged in", extra={"user_id": user.id, "email": user.email})

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "credits": user.credits,
            "plan": user.plan,
            "is_admin": user.is_admin,
        },
    }


@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current user profile from token."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized - missing token")
        
    # Demo token
    if token == "demo-token":
        return {
            "success": True,
            "user": {
                "id": 0,
                "name": "Demo User",
                "email": "demo@blogai.com",
                "credits": 10,
                "plan": "starter",
                "is_admin": 0,
            }
        }

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.token == token)
        )
        user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "success": True,
        "user": {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "email": user.email,
            "credits": user.credits,
            "plan": user.plan,
            "is_admin": user.is_admin,
        }
    }

async def get_user_id(request: Request) -> int:
    """Dependency to extract user_id from token."""
    user_data = await get_current_user(request)
    if not user_data or "user" not in user_data:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_data["user"]["id"]

async def get_current_admin(request: Request) -> int:
    """Dependency to extract admin user_id and verify admin privileges."""
    user_data = await get_current_user(request)
    if not user_data or "user" not in user_data:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not user_data["user"].get("is_admin"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user_data["user"]["id"]
