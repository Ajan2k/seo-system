# app/routes/auth.py
"""
Authentication routes for BlogAI SaaS platform.

Simple token-based auth with SQLite user storage.
Supports signup, login, and user profile endpoints.
"""

import hashlib
import secrets
import time

import aiosqlite
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

DB_PATH = settings.DATABASE_PATH


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


async def _ensure_users_table():
    """Create users table if it doesn't exist."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                token TEXT,
                credits INTEGER DEFAULT 5,
                plan TEXT DEFAULT 'free',
                created_at REAL NOT NULL,
                last_login REAL
            )
        """)
        await conn.commit()


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("/auth/signup")
async def signup(req: SignupRequest):
    """Create a new user account."""
    await _ensure_users_table()

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Check if email already exists
        cursor = await conn.execute(
            "SELECT id FROM users WHERE email = ?", (req.email.lower(),)
        )
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        if len(req.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

        # Hash password & create token
        password_hash, salt = _hash_password(req.password)
        token = _generate_token()

        # Insert user
        cursor = await conn.execute(
            """INSERT INTO users (first_name, last_name, email, password_hash, password_salt, token, credits, plan, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (req.first_name, req.last_name, req.email.lower(), password_hash, salt, token, 5, "free", time.time())
        )
        await conn.commit()
        user_id = cursor.lastrowid

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
        },
        "message": "Account created successfully! You have 5 free credits.",
    }


@router.post("/auth/login")
async def login(req: LoginRequest):
    """Authenticate an existing user."""
    await _ensure_users_table()

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        cursor = await conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (req.email.lower(),)
        )
        user = await cursor.fetchone()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        password_hash, _ = _hash_password(req.password, user["password_salt"])
        if password_hash != user["password_hash"]:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Generate new token
        token = _generate_token()
        await conn.execute(
            "UPDATE users SET token = ?, last_login = ? WHERE id = ?",
            (token, time.time(), user["id"])
        )
        await conn.commit()

    logger.info("User logged in", extra={"user_id": user["id"], "email": user["email"]})

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "name": f"{user['first_name']} {user['last_name']}",
            "email": user["email"],
            "credits": user["credits"],
            "plan": user["plan"],
        },
    }


@router.get("/auth/me")
async def get_current_user(request: Request):
    """Get current user profile from token."""
    await _ensure_users_table()

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()

    # Demo token
    if not token or token == "demo-token":
        return {
            "success": True,
            "user": {
                "id": 0,
                "name": "Demo User",
                "email": "demo@blogai.com",
                "credits": 10,
                "plan": "starter",
            }
        }

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, first_name, last_name, email, credits, plan FROM users WHERE token = ?",
            (token,)
        )
        user = await cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "success": True,
        "user": {
            "id": user["id"],
            "name": f"{user['first_name']} {user['last_name']}",
            "email": user["email"],
            "credits": user["credits"],
            "plan": user["plan"],
        }
    }
