import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

class Database:
    def __init__(self, db_path: str = "data/posts.db"):
        self.db_path = db_path
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else "data", exist_ok=True)
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create websites table
        cursor.execute("""
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
        
        # Create posts table with all SEO fields
        cursor.execute("""
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
        cursor.execute("""
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
        
        # Add missing columns to existing posts table if needed
        cursor.execute("PRAGMA table_info(posts)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'focus_keyphrase' not in columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN focus_keyphrase TEXT")
            print("✅ Added focus_keyphrase column to database")
            
        if 'seo_title' not in columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN seo_title TEXT")
            print("✅ Added seo_title column to database")
        
        conn.commit()
        conn.close()

    def add_used_keyphrase(self, keyphrase: str, post_id: int, website_id: int = None):
        """Track used keyphrase to avoid duplicates"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO used_keyphrases (website_id, keyphrase, post_id)
                VALUES (?, ?, ?)
            """, (website_id, keyphrase.lower().strip(), post_id))
            conn.commit()
        except:
            pass
        finally:
            conn.close()

    def is_keyphrase_used(self, keyphrase: str, website_id: int = None) -> bool:
        """Check if keyphrase was already used"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if website_id:
            cursor.execute("""
                SELECT COUNT(*) FROM used_keyphrases 
                WHERE keyphrase = ? AND website_id = ?
            """, (keyphrase.lower().strip(), website_id))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM used_keyphrases 
                WHERE keyphrase = ?
            """, (keyphrase.lower().strip(),))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def get_published_posts_for_internal_linking(self, website_id: int = None, limit: int = 20) -> List[Dict]:
        """Get published posts for internal linking"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if website_id:
            cursor.execute("""
                SELECT id, title, published_url, keywords, focus_keyphrase
                FROM posts
                WHERE published = 1 AND published_url IS NOT NULL AND website_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (website_id, limit))
        else:
            cursor.execute("""
                SELECT id, title, published_url, keywords, focus_keyphrase
                FROM posts
                WHERE published = 1 AND published_url IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        posts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return posts

    # Website CRUD
    def add_website(self, name: str, domain: str, cms_type: str, api_url: str, 
                    api_key: str = None, api_secret: str = None):
        """Add a new website configuration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Ensure api_url is properly formatted
        if not api_url.startswith('http'):
            api_url = f"https://{api_url}"
        
        cursor.execute("""
            INSERT INTO websites (name, domain, cms_type, api_url, api_key, api_secret)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, domain, cms_type, api_url, api_key, api_secret))
        conn.commit()
        website_id = cursor.lastrowid
        conn.close()
        return website_id
    
    def get_websites(self) -> List[Dict]:
        """Get all websites"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM websites ORDER BY created_at DESC")
        websites = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return websites
    
    def get_website(self, website_id: int) -> Optional[Dict]:
        """Get a specific website by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM websites WHERE id = ?", (website_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def delete_website(self, website_id: int):
        """Delete a website"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM websites WHERE id = ?", (website_id,))
        conn.commit()
        conn.close()
    
    # Post CRUD - Fixed version with all SEO fields
    def add_post(self, title: str, slug: str, content: str, meta_description: str, 
                 keywords: str, category: str, focus_keyphrase: str = None, 
                 seo_title: str = None, website_id: int = None, 
                 image_url: str = None, seo_score: int = 0):
        """Add a new post to the database with all SEO fields"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # If no slug provided, generate one
        if not slug:
            slug = title.lower().replace(' ', '-').replace(',', '').replace('.', '')
        
        cursor.execute("""
            INSERT INTO posts (title, slug, content, meta_description, keywords, 
                             focus_keyphrase, seo_title, category, website_id, 
                             image_url, seo_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, slug, content, meta_description, keywords, 
              focus_keyphrase, seo_title, category, website_id, 
              image_url, seo_score))
        
        conn.commit()
        post_id = cursor.lastrowid
        
        # Track the used keyphrase if provided
        if focus_keyphrase and website_id:
            self.add_used_keyphrase(focus_keyphrase, post_id, website_id)
        
        conn.close()
        return post_id
    
    def get_posts(self, limit: int = 50) -> List[Dict]:
        """Get recent posts with all fields"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, w.name as website_name 
            FROM posts p
            LEFT JOIN websites w ON p.website_id = w.id
            ORDER BY p.created_at DESC
            LIMIT ?
        """, (limit,))
        posts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return posts
    
    def get_post(self, post_id: int) -> Optional[Dict]:
        """Get a specific post by ID with all SEO fields"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, slug, content, meta_description, keywords,
                   focus_keyphrase, seo_title, category, seo_score, image_url,
                   website_id, published, published_url, created_at
            FROM posts 
            WHERE id = ?
        """, (post_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    
    def update_post(self, post_id: int, **kwargs):
        """Update a post with any provided fields"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build the update query dynamically
        update_fields = []
        values = []
        
        allowed_fields = ['title', 'slug', 'content', 'meta_description', 
                         'keywords', 'focus_keyphrase', 'seo_title', 
                         'category', 'seo_score', 'image_url']
        
        for field in allowed_fields:
            if field in kwargs:
                update_fields.append(f"{field} = ?")
                values.append(kwargs[field])
        
        if update_fields:
            values.append(post_id)
            query = f"UPDATE posts SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def update_post_published(self, post_id: int, published_url: str):
        """Update post as published with the URL"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE posts 
            SET published = 1, published_url = ?
            WHERE id = ?
        """, (published_url, post_id))
        conn.commit()
        conn.close()
    
    def delete_post(self, post_id: int):
        """Delete a post"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()

# Create a global instance for easy access
db = Database()