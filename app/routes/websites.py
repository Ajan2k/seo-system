from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.database import db  # <--- Import the global async db instance
from app.routes.auth import get_user_id, get_user_dict
from fastapi import Depends

router = APIRouter()

class WebsiteCreate(BaseModel):
    name: str
    domain: str
    cms_type: str  # wordpress, ghost, custom
    api_url: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None

@router.post("/websites")
async def create_website(website: WebsiteCreate, user: dict = Depends(get_user_dict)):
    """Add a new website"""
    try:
        user_id = user["id"]
        plan = user.get("plan", "free").lower()

        # Enforce CMS limits
        if plan in ['free', 'starter']:
            if website.cms_type != 'wordpress':
                raise HTTPException(status_code=403, detail="Starter plan only supports WordPress.")
        elif plan == 'professional':
            if website.cms_type not in ['wordpress', 'ghost']:
                raise HTTPException(status_code=403, detail="Professional plan only supports WordPress and Ghost.")

        # Enforce Connection Limits
        current_websites = await db.get_websites(user_id=user_id)
        if plan in ['free', 'starter'] and len(current_websites) >= 1:
            raise HTTPException(status_code=403, detail="Starter plan is limited to 1 website. Please upgrade your plan.")
        elif plan == 'professional' and len(current_websites) >= 5:
            raise HTTPException(status_code=403, detail="Professional plan is limited to 5 websites. Please upgrade your plan.")

        # <--- FIXED: Added await
        website_id = await db.add_website(
            name=website.name,
            domain=website.domain,
            cms_type=website.cms_type,
            api_url=website.api_url,
            api_key=website.api_key,
            api_secret=website.api_secret,
            user_id=user_id
        )
        
        return {
            'success': True,
            'website_id': website_id,
            'message': f'Website "{website.name}" added successfully'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/websites")
async def get_websites(user_id: int = Depends(get_user_id)):
    """Get all websites"""
    try:
        # <--- FIXED: Added await
        websites = await db.get_websites(user_id=user_id)
        return {'websites': websites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/websites/{website_id}")
async def delete_website(website_id: int, user_id: int = Depends(get_user_id)):
    """Delete a website"""
    try:
        # <--- FIXED: Added await
        await db.delete_website(website_id, user_id=user_id)
        return {'success': True, 'message': 'Website deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts")
async def get_posts(limit: int = 50, user_id: int = Depends(get_user_id)):
    """Get all posts"""
    try:
        # <--- FIXED: Added await
        posts = await db.get_posts(limit, user_id=user_id)
        return {'posts': posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/posts/{post_id}")
async def get_post(post_id: int, user_id: int = Depends(get_user_id)):
    """Get single post"""
    try:
        # <--- FIXED: Added await
        post = await db.get_post(post_id, user_id=user_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return post
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/posts/{post_id}")
async def delete_post(post_id: int, user_id: int = Depends(get_user_id)):
    """Delete a post"""
    try:
        # <--- FIXED: Added await
        await db.delete_post(post_id, user_id=user_id)
        return {'success': True, 'message': 'Post deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))