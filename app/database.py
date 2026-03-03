# app/database.py
"""
Async SQLite Database Layer (aiosqlite)

Design decisions:
  - All public methods are async def and use context managers.
  - Structured logging replaces print() statements.
  - Inline migration handles schema evolution without an external tool.
  - Type annotations on all public methods.
"""
import aiosqlite
import os
from typing import List, Dict, Optional, Any

from core.logging import get_logger
from core.config import settings

logger = get_logger(__name__)


class Database:
    """
    Thin async repository layer over aiosqlite.
    Each method opens its own connection to remain safe under concurrent
    async use without a connection pool.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.DATABASE_PATH
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else "data", exist_ok=True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _connect(self) -> aiosqlite.Connection:
        """Open a new async SQLite connection with row-factory set."""
        return aiosqlite.connect(self.db_path)

    # ── Schema Initialization ─────────────────────────────────────────────────

    async def init_db(self) -> None:
        """Create tables and run inline migrations. Idempotent."""
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row

            # websites table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS websites (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT    NOT NULL,
                    domain     TEXT    NOT NULL,
                    cms_type   TEXT    NOT NULL,
                    api_url    TEXT    NOT NULL,
                    api_key    TEXT,
                    api_secret TEXT,
                    user_id    INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # posts table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    title            TEXT    NOT NULL,
                    slug             TEXT    NOT NULL,
                    content          TEXT    NOT NULL,
                    meta_description TEXT,
                    keywords         TEXT,
                    focus_keyphrase  TEXT,
                    seo_title        TEXT,
                    category         TEXT,
                    seo_score        INTEGER DEFAULT 0,
                    image_url        TEXT,
                    website_id       INTEGER,
                    published        INTEGER DEFAULT 0,
                    published_url    TEXT,
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (website_id) REFERENCES websites(id)
                )
            """)

            # used_keyphrases table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS used_keyphrases (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER,
                    keyphrase  TEXT    NOT NULL,
                    post_id    INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (website_id) REFERENCES websites(id),
                    FOREIGN KEY (post_id)    REFERENCES posts(id),
                    UNIQUE(website_id, keyphrase)
                )
            """)

            # ── Inline column migrations ───────────────────────────────────────
            cursor = await conn.execute("PRAGMA table_info(posts)")
            rows = await cursor.fetchall()
            existing_columns = {row[1] for row in rows}

            for col, definition in [
                ("focus_keyphrase", "TEXT"),
                ("seo_title", "TEXT"),
                ("user_id", "INTEGER"),
            ]:
                if col not in existing_columns:
                    await conn.execute(f"ALTER TABLE posts ADD COLUMN {col} {definition}")
                    logger.info("Schema migration applied", extra={"added_column": f"posts.{col}"})
                    
            cursor = await conn.execute("PRAGMA table_info(websites)")
            rows = await cursor.fetchall()
            existing_columns_webs = {row[1] for row in rows}

            for col, definition in [
                ("user_id", "INTEGER"),
            ]:
                if col not in existing_columns_webs:
                    await conn.execute(f"ALTER TABLE websites ADD COLUMN {col} {definition}")
                    logger.info("Schema migration applied", extra={"added_column": f"websites.{col}"})

            await conn.commit()
            logger.info("Database tables initialized successfully")

    # ── Keyphrase Tracking ────────────────────────────────────────────────────

    async def add_used_keyphrase(
        self,
        keyphrase: str,
        post_id: int,
        website_id: Optional[int] = None,
    ) -> None:
        sql = """
            INSERT OR IGNORE INTO used_keyphrases (website_id, keyphrase, post_id)
            VALUES (?, ?, ?)
        """
        async with self._connect() as conn:
            await conn.execute(sql, (website_id, keyphrase.lower().strip(), post_id))
            await conn.commit()

    async def is_keyphrase_used(
        self,
        keyphrase: str,
        website_id: Optional[int] = None,
    ) -> bool:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            if website_id:
                sql = "SELECT 1 FROM used_keyphrases WHERE keyphrase = ? AND website_id = ?"
                params: tuple = (keyphrase.lower().strip(), website_id)
            else:
                sql = "SELECT 1 FROM used_keyphrases WHERE keyphrase = ?"
                params = (keyphrase.lower().strip(),)
            cursor = await conn.execute(sql, params)
            return (await cursor.fetchone()) is not None

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
        if not api_url.startswith("http"):
            api_url = f"https://{api_url}"
        sql = """
            INSERT INTO websites (name, domain, cms_type, api_url, api_key, api_secret, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (name, domain, cms_type, api_url, api_key, api_secret, user_id))
            await conn.commit()
            logger.info("Website added", extra={"website_name": name, "cms_type": cms_type, "user_id": user_id})
            return cursor.lastrowid  # type: ignore[return-value]

    async def get_websites(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            query = "SELECT * FROM websites WHERE user_id = ? ORDER BY created_at DESC" if user_id is not None else "SELECT * FROM websites ORDER BY created_at DESC"
            params = (user_id,) if user_id is not None else ()
            cursor = await conn.execute(query, params)
            return [dict(row) for row in await cursor.fetchall()]

    async def get_website(self, website_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            query = "SELECT * FROM websites WHERE id = ? AND user_id = ?" if user_id is not None else "SELECT * FROM websites WHERE id = ?"
            params = (website_id, user_id) if user_id is not None else (website_id,)
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_website(self, website_id: int, user_id: Optional[int] = None) -> None:
        async with self._connect() as conn:
            query = "DELETE FROM websites WHERE id = ? AND user_id = ?" if user_id is not None else "DELETE FROM websites WHERE id = ?"
            params = (website_id, user_id) if user_id is not None else (website_id,)
            await conn.execute(query, params)
            await conn.commit()
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
        if not slug:
            slug = title.lower().replace(" ", "-").replace(",", "").replace(".", "")

        sql = """
            INSERT INTO posts
                (title, slug, content, meta_description, keywords,
                 focus_keyphrase, seo_title, category, website_id, image_url, seo_score, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (
                title, slug, content, meta_description, keywords,
                focus_keyphrase, seo_title, category, website_id, image_url, seo_score, user_id
            ))
            await conn.commit()
            post_id = cursor.lastrowid  # type: ignore[assignment]

        if focus_keyphrase and website_id:
            await self.add_used_keyphrase(focus_keyphrase, post_id, website_id)  # type: ignore[arg-type]

        logger.info(
            "Post saved to database",
            extra={
                "post_id": post_id,
                "title": title[:60],
                "seo_score": seo_score,
                "focus_keyphrase": focus_keyphrase,
            },
        )
        return post_id  # type: ignore[return-value]

    async def get_posts(self, limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = """
            SELECT p.*, w.name AS website_name
            FROM   posts     p
            LEFT JOIN websites w ON p.website_id = w.id
            WHERE p.user_id = ?
            ORDER BY p.created_at DESC
            LIMIT ?
        """ if user_id is not None else """
            SELECT p.*, w.name AS website_name
            FROM   posts     p
            LEFT JOIN websites w ON p.website_id = w.id
            ORDER BY p.created_at DESC
            LIMIT ?
        """
        params = (user_id, limit) if user_id is not None else (limit,)
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, params)
            return [dict(row) for row in await cursor.fetchall()]

    async def get_post(self, post_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            query = "SELECT * FROM posts WHERE id = ? AND user_id = ?" if user_id is not None else "SELECT * FROM posts WHERE id = ?"
            params = (post_id, user_id) if user_id is not None else (post_id,)
            cursor = await conn.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_published_posts_for_internal_linking(
        self,
        website_id: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            if website_id:
                sql = """
                    SELECT id, title, published_url, keywords, focus_keyphrase
                    FROM   posts
                    WHERE  published = 1 AND published_url IS NOT NULL AND website_id = ?
                    ORDER BY created_at DESC LIMIT ?
                """
                params: tuple = (website_id, limit)
            else:
                sql = """
                    SELECT id, title, published_url, keywords, focus_keyphrase
                    FROM   posts
                    WHERE  published = 1 AND published_url IS NOT NULL
                    ORDER BY created_at DESC LIMIT ?
                """
                params = (limit,)
            cursor = await conn.execute(sql, params)
            return [dict(row) for row in await cursor.fetchall()]

    async def update_post(self, post_id: int, user_id: Optional[int] = None, **kwargs: Any) -> None:
        allowed = {
            "title", "slug", "content", "meta_description", "keywords",
            "focus_keyphrase", "seo_title", "category", "seo_score", "image_url",
        }
        fields, values = [], []
        for field in allowed:
            if field in kwargs:
                fields.append(f"{field} = ?")
                values.append(kwargs[field])

        if not fields:
            return

        values.append(post_id)
        if user_id is not None:
            values.append(user_id)
            sql = f"UPDATE posts SET {', '.join(fields)} WHERE id = ? AND user_id = ?"
        else:
            sql = f"UPDATE posts SET {', '.join(fields)} WHERE id = ?"
            
        async with self._connect() as conn:
            await conn.execute(sql, values)
            await conn.commit()

    async def update_post_published(self, post_id: int, published_url: str, user_id: Optional[int] = None) -> None:
        query = "UPDATE posts SET published = 1, published_url = ? WHERE id = ? AND user_id = ?" if user_id is not None else "UPDATE posts SET published = 1, published_url = ? WHERE id = ?"
        params = (published_url, post_id, user_id) if user_id is not None else (published_url, post_id)
        async with self._connect() as conn:
            await conn.execute(query, params)
            await conn.commit()
        logger.info("Post marked as published", extra={"post_id": post_id, "url": published_url, "user_id": user_id})

    async def delete_post(self, post_id: int, user_id: Optional[int] = None) -> None:
        async with self._connect() as conn:
            query = "DELETE FROM posts WHERE id = ? AND user_id = ?" if user_id is not None else "DELETE FROM posts WHERE id = ?"
            params = (post_id, user_id) if user_id is not None else (post_id,)
            await conn.execute(query, params)
            await conn.commit()
        logger.info("Post deleted", extra={"post_id": post_id, "user_id": user_id})


# Global singleton
db = Database()