# app/routes/admin_data.py
import aiosqlite
from fastapi import APIRouter, Depends
from typing import List, Dict, Any

from app.database import db
from app.routes.auth import get_current_admin
from core.config import settings

router = APIRouter()
DB_PATH = settings.DATABASE_PATH

@router.get("/admin/stats")
async def get_admin_stats(admin_id: int = Depends(get_current_admin)):
    """Get global statistics for the admin dashboard."""
    async with db._connect() as conn:
        conn.row_factory = aiosqlite.Row
        
        users_count = await (await conn.execute("SELECT COUNT(id) FROM users")).fetchone()
        posts_count = await (await conn.execute("SELECT COUNT(id) FROM posts")).fetchone()
        websites_count = await (await conn.execute("SELECT COUNT(id) FROM websites")).fetchone()
        
        return {
            "success": True,
            "total_users": users_count[0],
            "total_posts": posts_count[0],
            "total_websites": websites_count[0]
        }

@router.get("/admin/users")
async def get_all_users(admin_id: int = Depends(get_current_admin)):
    """List all users along with their post counts."""
    async with db._connect() as conn:
        conn.row_factory = aiosqlite.Row
        
        query = """
            SELECT u.id, u.first_name, u.last_name, u.email, u.credits, u.is_admin, u.created_at,
                   COUNT(p.id) as posts_count,
                   COUNT(DISTINCT w.id) as websites_count
            FROM users u
            LEFT JOIN posts p ON u.id = p.user_id
            LEFT JOIN websites w ON u.id = w.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """
        cursor = await conn.execute(query)
        users = [dict(row) for row in await cursor.fetchall()]
        
        return {"success": True, "users": users}

@router.get("/admin/posts")
async def get_all_posts(admin_id: int = Depends(get_current_admin)):
    """List all posts across the system."""
    async with db._connect() as conn:
        conn.row_factory = aiosqlite.Row
        
        query = """
            SELECT p.id, p.title, p.category, p.seo_score, p.published, p.created_at, 
                   u.email as user_email, w.name as website_name
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.id
            LEFT JOIN websites w ON p.website_id = w.id
            ORDER BY p.created_at DESC
            LIMIT 100
        """
        cursor = await conn.execute(query)
        posts = [dict(row) for row in await cursor.fetchall()]
        
        return {"success": True, "posts": posts}
