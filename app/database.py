from typing import List, Dict, Optional, Any
from sqlalchemy.future import select
from sqlalchemy import delete, insert, update, desc, func
from sqlalchemy.exc import IntegrityError

from app.models import AsyncSessionLocal, User, Website, Post, UsedKeyphrase
from core.logging import get_logger

logger = get_logger(__name__)

class Database:
    """
    Async PostgreSQL Database Layer via SQLAlchemy ORM over asyncpg.
    """

    def __init__(self, db_path: str | None = None) -> None:
        pass

    async def init_db(self) -> None:
        pass # Migrations handled by Alembic now

    def _connect(self):
        """Deprecated – use AsyncSessionLocal instead."""
        raise DeprecationWarning("Use AsyncSessionLocal for all database operations.")

    def _obj_to_dict(self, obj) -> Dict[str, Any]:
        if not obj:
            return None
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    # ── Keyphrase Tracking ────────────────────────────────────────────────────

    async def add_used_keyphrase(
        self,
        keyphrase: str,
        post_id: int,
        website_id: Optional[int] = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            try:
                kp = UsedKeyphrase(website_id=website_id, keyphrase=keyphrase.lower().strip(), post_id=post_id)
                session.add(kp)
                await session.commit()
            except IntegrityError:
                await session.rollback()

    async def is_keyphrase_used(
        self,
        keyphrase: str,
        website_id: Optional[int] = None,
    ) -> bool:
        async with AsyncSessionLocal() as session:
            query = select(UsedKeyphrase).where(UsedKeyphrase.keyphrase == keyphrase.lower().strip())
            if website_id:
                query = query.where(UsedKeyphrase.website_id == website_id)
            result = await session.execute(query)
            return result.scalars().first() is not None

    # ── Website CRUD ──────────────────────────────────────────────────────────

    async def add_website(
        self,
        name: str,
        domain: str,
        cms_type: str,
        api_url: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> int:
        if user_id == 0:
            user_id = None
        if not api_url.startswith("http"):
            api_url = f"https://{api_url}"
        async with AsyncSessionLocal() as session:
            ws = Website(
                name=name, domain=domain, cms_type=cms_type, api_url=api_url,
                api_key=api_key, api_secret=api_secret, user_id=user_id
            )
            session.add(ws)
            await session.commit()
            logger.info("Website added", extra={"website_name": name, "cms_type": cms_type, "user_id": user_id})
            return ws.id

    async def get_websites(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            query = select(Website).order_by(desc(Website.created_at))
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Website.user_id.is_(None))
                else:
                    query = query.where(Website.user_id == user_id)
            result = await session.execute(query)
            return [self._obj_to_dict(ws) for ws in result.scalars().all()]

    async def get_website(self, website_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            query = select(Website).where(Website.id == website_id)
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Website.user_id.is_(None))
                else:
                    query = query.where(Website.user_id == user_id)
            result = await session.execute(query)
            return self._obj_to_dict(result.scalars().first())

    async def delete_website(self, website_id: int, user_id: Optional[int] = None) -> None:
        async with AsyncSessionLocal() as session:
            query = delete(Website).where(Website.id == website_id)
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Website.user_id.is_(None))
                else:
                    query = query.where(Website.user_id == user_id)
            await session.execute(query)
            await session.commit()
            logger.info("Website deleted", extra={"website_id": website_id, "user_id": user_id})

    # ── Post CRUD ─────────────────────────────────────────────────────────────

    async def add_post(
        self,
        title: str,
        slug: str,
        content: str,
        meta_description: str,
        keywords: str,
        category: str,
        focus_keyphrase: Optional[str] = None,
        seo_title: Optional[str] = None,
        website_id: Optional[int] = None,
        image_url: Optional[str] = None,
        seo_score: int = 0,
        user_id: Optional[int] = None,
    ) -> int:
        if user_id == 0:
            user_id = None
        if not slug:
            slug = title.lower().replace(" ", "-").replace(",", "").replace(".", "")

        async with AsyncSessionLocal() as session:
            post = Post(
                title=title, slug=slug, content=content, meta_description=meta_description,
                keywords=keywords, focus_keyphrase=focus_keyphrase, seo_title=seo_title,
                category=category, website_id=website_id, image_url=image_url, 
                seo_score=seo_score, user_id=user_id
            )
            session.add(post)
            await session.commit()
            post_id = post.id

        if focus_keyphrase and website_id:
            await self.add_used_keyphrase(focus_keyphrase, post_id, website_id)

        logger.info(
            "Post saved to database",
            extra={
                "post_id": post_id,
                "title": title[:60],
                "seo_score": seo_score,
                "focus_keyphrase": focus_keyphrase,
            },
        )
        return post_id

    async def get_posts(self, limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            query = select(Post, Website.name.label("website_name")).outerjoin(Website, Post.website_id == Website.id)
            query = query.order_by(desc(Post.created_at)).limit(limit)
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Post.user_id.is_(None))
                else:
                    query = query.where(Post.user_id == user_id)
            
            result = await session.execute(query)
            rows = result.all()
            
            out = []
            for post, website_name in rows:
                p_dict = self._obj_to_dict(post)
                p_dict["website_name"] = website_name
                out.append(p_dict)
            return out

    async def get_post(self, post_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            query = select(Post).where(Post.id == post_id)
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Post.user_id.is_(None))
                else:
                    query = query.where(Post.user_id == user_id)
            result = await session.execute(query)
            return self._obj_to_dict(result.scalars().first())

    async def get_published_posts_for_internal_linking(
        self,
        website_id: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            query = select(Post).where(Post.published == 1, Post.published_url.is_not(None))
            if website_id:
                query = query.where(Post.website_id == website_id)
            query = query.order_by(desc(Post.created_at)).limit(limit)
            result = await session.execute(query)
            return [self._obj_to_dict(p) for p in result.scalars().all()]

    async def update_post(self, post_id: int, user_id: Optional[int] = None, **kwargs: Any) -> None:
        allowed = {
            "title", "slug", "content", "meta_description", "keywords",
            "focus_keyphrase", "seo_title", "category", "seo_score", "image_url",
        }
        update_data = {k: v for k, v in kwargs.items() if k in allowed}
        if not update_data:
            return

        async with AsyncSessionLocal() as session:
            query = update(Post).where(Post.id == post_id)
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Post.user_id.is_(None))
                else:
                    query = query.where(Post.user_id == user_id)
            query = query.values(**update_data)
            await session.execute(query)
            await session.commit()

    async def update_post_published(self, post_id: int, published_url: str, user_id: Optional[int] = None) -> None:
        async with AsyncSessionLocal() as session:
            query = update(Post).where(Post.id == post_id).values(published=1, published_url=published_url)
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Post.user_id.is_(None))
                else:
                    query = query.where(Post.user_id == user_id)
            await session.execute(query)
            await session.commit()
            logger.info("Post marked as published", extra={"post_id": post_id, "url": published_url, "user_id": user_id})

    async def delete_post(self, post_id: int, user_id: Optional[int] = None) -> None:
        async with AsyncSessionLocal() as session:
            query = delete(Post).where(Post.id == post_id)
            if user_id is not None:
                if user_id == 0:
                    query = query.where(Post.user_id.is_(None))
                else:
                    query = query.where(Post.user_id == user_id)
            await session.execute(query)
            await session.commit()
            logger.info("Post deleted", extra={"post_id": post_id, "user_id": user_id})


# Global singleton
db = Database()