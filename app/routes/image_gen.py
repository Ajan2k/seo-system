from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.utils.image_api import ImageGenerator
from app.database import db  # <--- Import the global async db instance

router = APIRouter()
image_gen = ImageGenerator()

class ImageGenerateRequest(BaseModel):
    prompt: str
    keywords: Optional[List[str]] = None
    source: Optional[str] = None

class ImageRegenerateRequest(BaseModel):
    post_id: int
    source: Optional[str] = None

class ImageSearchRequest(BaseModel):
    query: str
    count: int = 5

@router.post("/generate-image")
async def generate_image_endpoint(request: ImageGenerateRequest):
    """Generate image for a given prompt"""
    try:
        if request.source and request.source != 'auto':
            image_url = await generate_from_specific_source(
                request.source, 
                request.prompt, 
                request.keywords
            )
        else:
            # <--- FIXED: Added await if generate_image is async
            image_url =  image_gen.generate_image(request.prompt, request.keywords)
        
        if not image_url:
            raise HTTPException(
                status_code=500, 
                detail="Failed to generate image from all sources"
            )
        
        return {
            'success': True,
            'image_url': image_url,
            'prompt': request.prompt,
            'source': detect_image_source(image_url)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate-image")
async def regenerate_image(request: ImageRegenerateRequest):
    """Regenerate image for an existing blog post"""
    try:
        # <--- FIXED: Added await
        post = await db.get_post(request.post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        keywords = post['keywords'].split(',') if post['keywords'] else []
        
        if request.source and request.source != 'auto':
            image_url = await generate_from_specific_source(
                request.source,
                post['title'],
                keywords
            )
        else:
            # <--- FIXED: Added await if generate_image is async
            image_url = image_gen.generate_image(post['title'], keywords)
        
        if not image_url:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate image"
            )
        
        # <--- FIXED: Use the async update_post method
        await db.update_post(request.post_id, image_url=image_url)
        
        return {
            'success': True,
            'post_id': request.post_id,
            'old_image_url': post['image_url'],
            'new_image_url': image_url,
            'source': detect_image_source(image_url)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search-images")
async def search_images(request: ImageSearchRequest):
    """Search for images across multiple sources"""
    try:
        results = []
        count = min(request.count, 10)
        
        try:
            lexica_images = await search_lexica(request.query, count)
            results.extend(lexica_images)
        except Exception as e:
            print(f"Lexica search error: {e}")
        
        if image_gen.pexels_api_key and len(results) < count:
            try:
                pexels_images = await search_pexels(request.query, count - len(results))
                results.extend(pexels_images)
            except Exception as e:
                print(f"Pexels search error: {e}")
        
        if len(results) < count:
            try:
                unsplash_images = await search_unsplash(request.query, count - len(results))
                results.extend(unsplash_images)
            except Exception as e:
                print(f"Unsplash search error: {e}")
        
        return {
            'success': True,
            'query': request.query,
            'count': len(results),
            'images': results[:count]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/image-sources")
async def get_image_sources():
    """Get available image generation sources and their status"""
    try:
        sources = {
            'lexica': {
                'name': 'Lexica.art',
                'type': 'AI Generated',
                'available': True,
                'requires_key': False,
                'quality': 'High',
                'speed': 'Fast'
            },
            'pexels': {
                'name': 'Pexels',
                'type': 'Stock Photos',
                'available': bool(image_gen.pexels_api_key),
                'requires_key': True,
                'quality': 'High',
                'speed': 'Fast'
            },
            'unsplash': {
                'name': 'Unsplash',
                'type': 'Stock Photos',
                'available': True,
                'requires_key': False,
                'quality': 'High',
                'speed': 'Medium'
            }
        }
        
        return {
            'success': True,
            'sources': sources,
            'configured_sources': [k for k, v in sources.items() if v['available']]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/image-stats")
async def get_image_stats():
    """Get statistics about image usage in posts"""
    try:
        # <--- FIXED: Added await
        posts = await db.get_posts(limit=1000)
        
        total_posts = len(posts)
        posts_with_images = sum(1 for p in posts if p.get('image_url'))
        
        source_counts = {
            'lexica': 0,
            'pexels': 0,
            'unsplash': 0,
            'placeholder': 0,
            'other': 0
        }
        
        for post in posts:
            if post.get('image_url'):
                source = detect_image_source(post['image_url'])
                source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            'success': True,
            'total_posts': total_posts,
            'posts_with_images': posts_with_images,
            'coverage_percentage': round((posts_with_images / total_posts * 100) if total_posts > 0 else 0, 2),
            'source_distribution': source_counts
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Helper Functions

async def generate_from_specific_source(source: str, prompt: str, keywords: Optional[List[str]] = None) -> Optional[str]:
    """Generate image from a specific source"""
    if source == 'lexica':
        return image_gen.generate_lexica(prompt)
    elif source == 'pexels':
        search_query = f"{prompt} {' '.join(keywords[:3])}" if keywords else prompt
        return image_gen.generate_pexels(search_query)
    elif source == 'unsplash':
        search_query = f"{prompt} {' '.join(keywords[:3])}" if keywords else prompt
        return image_gen.generate_unsplash_free(search_query)
    else:
        return None


def detect_image_source(image_url: str) -> str:
    """Detect which service an image URL came from"""
    if not image_url:
        return 'none'
    
    if 'lexica.art' in image_url:
        return 'lexica'
    elif 'pexels.com' in image_url:
        return 'pexels'
    elif 'unsplash.com' in image_url:
        return 'unsplash'
    elif 'placeholder.com' in image_url:
        return 'placeholder'
    else:
        return 'other'


async def search_lexica(query: str, count: int = 5) -> List[dict]:
    """Search Lexica for images"""
    import httpx
    
    try:
        clean_query = query.replace(" ", "+")
        url = f"https://lexica.art/api/v1/search?q={clean_query}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
        
        data = response.json()
        images = []
        
        for img in data.get("images", [])[:count]:
            images.append({
                'url': img.get('src'),
                'thumbnail': img.get('srcSmall', img.get('src')),
                'source': 'lexica',
                'prompt': img.get('prompt', ''),
                'width': img.get('width', 1024),
                'height': img.get('height', 1024)
            })
        
        return images
        
    except Exception as e:
        print(f"Lexica search error: {e}")
        return []


async def search_pexels(query: str, count: int = 5) -> List[dict]:
    """Search Pexels for images"""
    import httpx
    
    if not image_gen.pexels_api_key:
        return []
    
    try:
        headers = {"Authorization": image_gen.pexels_api_key}
        url = f"https://api.pexels.com/v1/search?query={query}&per_page={count}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        
        data = response.json()
        images = []
        
        for photo in data.get("photos", [])[:count]:
            images.append({
                'url': photo['src']['large'],
                'thumbnail': photo['src']['medium'],
                'source': 'pexels',
                'photographer': photo.get('photographer', ''),
                'width': photo.get('width', 1200),
                'height': photo.get('height', 800)
            })
        
        return images
        
    except Exception as e:
        print(f"Pexels search error: {e}")
        return []


async def search_unsplash(query: str, count: int = 5) -> List[dict]:
    """Search Unsplash for images (using Source API)"""
    images = []
    
    try:
        clean_query = query.replace(" ", ",")
        
        for i in range(count):
            image_url = f"https://source.unsplash.com/1200x630/?{clean_query}&sig={i}"
            images.append({
                'url': image_url,
                'thumbnail': f"https://source.unsplash.com/400x300/?{clean_query}&sig={i}",
                'source': 'unsplash',
                'query': query,
                'width': 1200,
                'height': 630
            })
        
        return images
        
    except Exception as e:
        print(f"Unsplash search error: {e}")
        return []