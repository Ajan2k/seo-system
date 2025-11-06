# app/database.py

import aiosqlite
import os
from typing import List, Dict, Optional

class Database:
    def __init__(self, db_path: str = "data/posts.db"):
        self.db_path = db_path
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else "data", exist_ok=True)

    async def init_db(self):
        """Initialize database tables asynchronously."""
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Create websites table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS websites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    cms_type TEXT NOT NULL,
                    api_url TEXT NOT NULL,
                    api_key TEXT,
                    api_secret TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create posts table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    content TEXT NOT NULL,
                    meta_description TEXT,
                    keywords TEXT,
                    focus_keyphrase TEXT,
                    seo_title TEXT,
                    category TEXT,
                    seo_score INTEGER DEFAULT 0,
                    image_url TEXT,
                    website_id INTEGER,
                    published INTEGER DEFAULT 0,
                    published_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (website_id) REFERENCES websites(id)
                )
            """)

            # Create used keyphrases table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS used_keyphrases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER,
                    keyphrase TEXT NOT NULL,
                    post_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (website_id) REFERENCES websites(id),
                    FOREIGN KEY (post_id) REFERENCES posts(id),
                    UNIQUE(website_id, keyphrase)
                )
            """)

            # Add missing columns (migration logic)
            cursor = await conn.execute("PRAGMA table_info(posts)")
            rows = await cursor.fetchall()
            columns = [row[1] for row in rows]

            if 'focus_keyphrase' not in columns:
                await conn.execute("ALTER TABLE posts ADD COLUMN focus_keyphrase TEXT")
                print("✅ Added focus_keyphrase column to database")

            if 'seo_title' not in columns:
                await conn.execute("ALTER TABLE posts ADD COLUMN seo_title TEXT")
                print("✅ Added seo_title column to database")

            await conn.commit()
            print("✅ Database tables initialized successfully")

    async def add_used_keyphrase(self, keyphrase: str, post_id: int, website_id: int = None):
        """Track used keyphrase asynchronously."""
        sql = """
            INSERT OR IGNORE INTO used_keyphrases (website_id, keyphrase, post_id)
            VALUES (?, ?, ?)
        """
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(sql, (website_id, keyphrase.lower().strip(), post_id))
            await conn.commit()

    async def is_keyphrase_used(self, keyphrase: str, website_id: int = None) -> bool:
        """Check if keyphrase was already used asynchronously."""
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            if website_id:
                sql = "SELECT 1 FROM used_keyphrases WHERE keyphrase = ? AND website_id = ?"
                params = (keyphrase.lower().strip(), website_id)
            else:
                sql = "SELECT 1 FROM used_keyphrases WHERE keyphrase = ?"
                params = (keyphrase.lower().strip(),)

            cursor = await conn.execute(sql, params)
            result = await cursor.fetchone()
            return result is not None

    async def get_published_posts_for_internal_linking(self, website_id: int = None, limit: int = 20) -> List[Dict]:
        """Get published posts for internal linking asynchronously."""
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            if website_id:
                sql = """
                    SELECT id, title, published_url, keywords, focus_keyphrase
                    FROM posts
                    WHERE published = 1 AND published_url IS NOT NULL AND website_id = ?
                    ORDER BY created_at DESC LIMIT ?
                """
                params = (website_id, limit)
            else:
                sql = """
                    SELECT id, title, published_url, keywords, focus_keyphrase
                    FROM posts
                    WHERE published = 1 AND published_url IS NOT NULL
                    ORDER BY created_at DESC LIMIT ?
                """
                params = (limit,)

            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_website(self, name: str, domain: str, cms_type: str, api_url: str,
                          api_key: str = None, api_secret: str = None) -> int:
        """Add a new website configuration."""
        if not api_url.startswith('http'):
            api_url = f"https://{api_url}"
        
        sql = """
            INSERT INTO websites (name, domain, cms_type, api_url, api_key, api_secret)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (name, domain, cms_type, api_url, api_key, api_secret))
            await conn.commit()
            return cursor.lastrowid

    async def get_websites(self) -> List[Dict]:
        """Get all websites."""
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM websites ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_website(self, website_id: int) -> Optional[Dict]:
        """Get a specific website by ID."""
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM websites WHERE id = ?", (website_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_website(self, website_id: int):
        """Delete a website."""
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("DELETE FROM websites WHERE id = ?", (website_id,))
            await conn.commit()

    async def add_post(self, title: str, slug: str, content: str, meta_description: str,
                       keywords: str, category: str, focus_keyphrase: str = None,
                       seo_title: str = None, website_id: int = None,
                       image_url: str = None, seo_score: int = 0) -> int:
        """Add a new post to the database with all SEO fields."""
        if not slug:
            slug = title.lower().replace(' ', '-').replace(',', '').replace('.', '')

        sql = """
            INSERT INTO posts (title, slug, content, meta_description, keywords,
                             focus_keyphrase, seo_title, category, website_id,
                             image_url, seo_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (
                title, slug, content, meta_description, keywords,
                focus_keyphrase, seo_title, category, website_id,
                image_url, seo_score
            ))
            await conn.commit()
            post_id = cursor.lastrowid

        # Track the used keyphrase if provided
        if focus_keyphrase and website_id:
            await self.add_used_keyphrase(focus_keyphrase, post_id, website_id)

        return post_id

    async def get_posts(self, limit: int = 50) -> List[Dict]:
        """Get recent posts with all fields."""
        sql = """
            SELECT p.*, w.name as website_name
            FROM posts p
            LEFT JOIN websites w ON p.website_id = w.id
            ORDER BY p.created_at DESC LIMIT ?
        """
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (limit,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_post(self, post_id: int) -> Optional[Dict]:
        """Get a specific post by ID with all SEO fields."""
        sql = "SELECT * FROM posts WHERE id = ?"
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (post_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_post(self, post_id: int, **kwargs):
        """Update a post with any provided fields."""
        update_fields, values = [], []
        allowed_fields = ['title', 'slug', 'content', 'meta_description', 'keywords',
                         'focus_keyphrase', 'seo_title', 'category', 'seo_score', 'image_url']
        
        for field in allowed_fields:
            if field in kwargs:
                update_fields.append(f"{field} = ?")
                values.append(kwargs[field])

        if update_fields:
            values.append(post_id)
            query = f"UPDATE posts SET {', '.join(update_fields)} WHERE id = ?"
            # <--- FIXED: Removed the extra 'await'
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute(query, values)
                await conn.commit()

    async def update_post_published(self, post_id: int, published_url: str):
        """Update post as published with the URL."""
        sql = "UPDATE posts SET published = 1, published_url = ? WHERE id = ?"
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(sql, (published_url, post_id))
            await conn.commit()

    async def delete_post(self, post_id: int):
        """Delete a post."""
        # <--- FIXED: Removed the extra 'await'
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            await conn.commit()


# Create a global instance for easy access
db = Database()