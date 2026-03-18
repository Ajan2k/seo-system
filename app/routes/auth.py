# app/routes/auth.py
"""
Authentication routes – DEMO MODE (no login required).

All dependency functions return a hardcoded demo user so that
downstream routes continue to work without any token.
"""

from fastapi import APIRouter, Request
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# ── Hardcoded demo user ──────────────────────────────────────────────────

DEMO_USER = {
    "id": 0,
    "name": "Demo User",
    "email": "demo@blogai.com",
    "credits": 999,
    "plan": "business",
    "is_admin": 1,
}


# ── Routes (kept for API compatibility) ──────────────────────────────────

@router.get("/auth/me")
async def get_current_user(request: Request):
    """Always returns the demo user profile."""
    return {"success": True, "user": DEMO_USER}


# ── Dependency functions used by other routes ────────────────────────────

async def get_user_id(request: Request) -> int:
    """Always returns demo user id (0)."""
    return DEMO_USER["id"]


async def get_current_admin(request: Request) -> int:
    """Always returns demo admin id (0)."""
    return DEMO_USER["id"]


async def get_user_dict(request: Request) -> dict:
    """Always returns demo user dict."""
    return DEMO_USER
