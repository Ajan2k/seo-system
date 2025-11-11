# scripts/2_create_tables.py
"""
Create database tables in data/blog_automation.db
Usage: python scripts/2_create_tables.py
"""

import sqlite3
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def create_tables():
    """Create database tables"""
    
    # Database path relative to project root
    db_path = os.path.join(PROJECT_ROOT, 'data', 'blog_automation.db')
    data_dir = os.path.join(PROJECT_ROOT, 'data')
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"✅ Created directory: data/\n")
    
    print(f"Creating tables in: data/blog_automation.db\n")
    
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
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_website_id ON posts(website_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_focus_keyphrase ON posts(focus_keyphrase)')
    print("✅ Created indexes")
    
    # Add trigger to prevent meta descriptions > 143 chars
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS check_meta_length_insert
        BEFORE INSERT ON posts
        FOR EACH ROW
        WHEN LENGTH(NEW.meta_description) > 143
        BEGIN
            SELECT RAISE(ABORT, 'Meta description exceeds 143 characters');
        END;
    ''')
    
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS check_meta_length_update
        BEFORE UPDATE ON posts
        FOR EACH ROW
        WHEN LENGTH(NEW.meta_description) > 143
        BEGIN
            SELECT RAISE(ABORT, 'Meta description exceeds 143 characters');
        END;
    ''')
    print("✅ Created database triggers (meta description length validation)")
    
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
    print(f"\n💡 Database location: data/blog_automation.db")
    print(f"💡 Next step: python scripts/3_check_database.py")
    print()
    
    conn.close()

if __name__ == "__main__":
    create_tables()