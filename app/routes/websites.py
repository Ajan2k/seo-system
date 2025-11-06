from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional,List
from app.database import Database

router = APIRouter()
db = Database()

class WebsiteCreate(BaseModel):
    name: str
    domain: str
    cms_type: str  # wordpress, ghost, custom
    api_url: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None

@router.post("/websites")
async def create_website(website: WebsiteCreate):
    """Add a new website"""
    try:
        website_id = db.add_website(
            name=website.name,
            domain=website.domain,
            cms_type=website.cms_type,
            api_url=website.api_url,
            api_key=website.api_key,
            api_secret=website.api_secret
        )
        
        return {
            'success': True,
            'website_id': website_id,
            'message': f'Website "{website.name}" added successfully'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/websites")
async def get_websites():
    """Get all websites"""
    try:
        websites = db.get_websites()
        return {'websites': websites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/websites/{website_id}")
async def delete_website(website_id: int):
    """Delete a website"""
    try:
        db.delete_website(website_id)
        return {'success': True, 'message': 'Website deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts")
async def get_posts(limit: int = 50):
    """Get all posts"""
    try:
        posts = db.get_posts(limit)
        return {'posts': posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts/{post_id}")
async def get_post(post_id: int):
    """Get single post"""
    try:
        post = db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return post
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/posts/{post_id}")
async def delete_post(post_id: int):
    """Delete a post"""
    try:
        db.delete_post(post_id)
        return {'success': True, 'message': 'Post deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))