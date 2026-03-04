import asyncio
from typing import Optional, Dict, Any, List

import httpx

from app.celery_app import celery_app
from app.database import db
from core.logging import get_logger

logger = get_logger(__name__)

async def run_async_generation_proxy(
    topic: str,
    category: str,
    website_id: Optional[int],
    user_id: int,
    is_custom: bool,
    target_score: int,
    brand_name: str,
    focus_keyword: Optional[str],
    industries: Optional[List[str]]
) -> Dict[str, Any]:
    """Execute the async generation logic inside a Celery task."""
    from app.routes.generate_blog import run_async_generation
    
    return await run_async_generation(
        topic=topic,
        category=category,
        website_id=website_id,
        user_id=user_id,
        is_custom=is_custom,
        target_score=target_score,
        brand_name=brand_name,
        focus_keyword=focus_keyword,
        industries=industries
    )

@celery_app.task(bind=True, max_retries=5)
def generate_blog_task(
    self, 
    topic: str,
    category: str = "Technology",
    website_id: Optional[int] = None,
    user_id: int = 1,
    is_custom: bool = False,
    target_score: int = 80,
    brand_name: str = "Infinitetechai",
    focus_keyword: Optional[str] = None,
    industries: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Celery task to generate a blog post with retry logic for 429s."""
    try:
        logger.info(f"Starting blog generation task {self.request.id} for topic: {topic}")
        # Run the async generation function synchronously in the Celery worker
        result = asyncio.run(
            run_async_generation_proxy(
                topic, category, website_id, user_id, is_custom, 
                target_score, brand_name, focus_keyword, industries
            )
        )
        logger.info(f"Successfully completed task {self.request.id}")
        return result
        
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            # Exponential backoff: 2, 4, 8, 16, 32 seconds
            retry_delay = 2 ** self.request.retries
            logger.warning(
                f"Rate limited (429) by API in task {self.request.id}. "
                f"Retrying in {retry_delay}s (Attempt {self.request.retries + 1}/5)"
            )
            # This raises Retry exception
            raise self.retry(exc=RuntimeError(f"Rate limited (429): {exc}"), countdown=retry_delay)
        
        logger.error(f"HTTP error in task {self.request.id}: {exc}")
        raise RuntimeError(str(exc))
        
    except Exception as exc:
        logger.exception(f"Unexpected error in task {self.request.id}")
        raise RuntimeError(str(exc))
