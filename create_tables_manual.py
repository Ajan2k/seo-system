# create_tables_manual.py
import sqlite3
import os

def create_tables():
    """Manually create database tables"""
    
    db_path = 'data/blog_automation.db'
    
    if not os.path.exists('data'):
        os.makedirs('data')
        print("✅ Created 'data' directory")
    
    print(f"Creating tables in: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create websites table
    cursor.execute('''
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
    ''')
    print("✅ Created 'websites' table")
    
    # Create posts table with ALL required fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT,
            content TEXT NOT NULL,
            meta_description TEXT,
            keywords TEXT,
            category TEXT,
            focus_keyphrase TEXT,
            seo_title TEXT,
            seo_score INTEGER DEFAULT 0,
            website_id INTEGER,
            image_url TEXT,
            published BOOLEAN DEFAULT 0,
            published_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (website_id) REFERENCES websites(id)
        )
    ''')
    print("✅ Created 'posts' table")
    
    # Create indexes
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_posts_website_id 
        ON posts(website_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_posts_published 
        ON posts(published)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_posts_focus_keyphrase 
        ON posts(focus_keyphrase)
    ''')
    
    print("✅ Created indexes")
    
    conn.commit()
    
    # Verify tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"\n{'='*60}")
    print("Tables created:")
    for table in tables:
        print(f"  ✅ {table[0]}")
        
        # Show columns
        cursor.execute(f"PRAGMA table_info({table[0]});")
        columns = cursor.fetchall()
        for col in columns:
            print(f"     - {col[1]} ({col[2]})")
        print()
    
    print(f"{'='*60}\n")
    print("✅ Database initialization complete!")
    
    conn.close()

if __name__ == "__main__":
    create_tables()