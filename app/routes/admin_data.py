# app/routes/admin_data.py
"""Admin dashboard data endpoints – PostgreSQL via SQLAlchemy async."""

from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from sqlalchemy.future import select
from sqlalchemy import func, desc

from app.models import AsyncSessionLocal, User, Post, Website
from app.routes.auth import get_current_admin
from core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/admin/stats")
async def get_admin_stats(admin_id: int = Depends(get_current_admin)):
    """Get global statistics for the admin dashboard."""
    async with AsyncSessionLocal() as session:
        users_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
        posts_count = (await session.execute(select(func.count(Post.id)))).scalar() or 0
        websites_count = (await session.execute(select(func.count(Website.id)))).scalar() or 0

    return {
        "success": True,
        "total_users": users_count,
        "total_posts": posts_count,
        "total_websites": websites_count
    }


@router.get("/admin/users")
async def get_all_users(admin_id: int = Depends(get_current_admin)):
    """List all users along with their post counts."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.email,
                User.credits,
                User.is_admin,
                User.created_at,
                func.count(Post.id).label("posts_count"),
                func.count(func.distinct(Website.id)).label("websites_count"),
            )
            .outerjoin(Post, User.id == Post.user_id)
            .outerjoin(Website, User.id == Website.user_id)
            .group_by(User.id)
            .order_by(desc(User.created_at))
        )
        rows = result.all()
        users = [
            {
                "id": r.id,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "email": r.email,
                "credits": r.credits,
                "is_admin": r.is_admin,
                "created_at": str(r.created_at) if r.created_at else None,
                "posts_count": r.posts_count,
                "websites_count": r.websites_count,
            }
            for r in rows
        ]

    return {"success": True, "users": users}


@router.get("/admin/posts")
async def get_all_posts(admin_id: int = Depends(get_current_admin)):
    """List all posts across the system."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                Post.id,
                Post.title,
                Post.category,
                Post.seo_score,
                Post.published,
                Post.created_at,
                User.email.label("user_email"),
                Website.name.label("website_name"),
            )
            .outerjoin(User, Post.user_id == User.id)
            .outerjoin(Website, Post.website_id == Website.id)
            .order_by(desc(Post.created_at))
            .limit(100)
        )
        rows = result.all()
        posts = [
            {
                "id": r.id,
                "title": r.title,
                "category": r.category,
                "seo_score": r.seo_score,
                "published": r.published,
                "created_at": str(r.created_at) if r.created_at else None,
                "user_email": r.user_email,
                "website_name": r.website_name,
            }
            for r in rows
        ]

    return {"success": True, "posts": posts}
