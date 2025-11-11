# reset_database.py
import os
import sqlite3
from datetime import datetime

# Paths
DB_PATH = "data/posts.db"
BACKUP_PATH = f"data/posts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def reset_database():
    """Reset the database by deleting and recreating it"""
    
    print("=" * 60)
    print("Database Reset Tool")
    print("=" * 60)
    
    # Check if database exists
    if os.path.exists(DB_PATH):
        print(f"\n📁 Found existing database: {DB_PATH}")
        
        # Try to backup if possible
        try:
            import shutil
            shutil.copy(DB_PATH, BACKUP_PATH)
            print(f"✅ Backup created: {BACKUP_PATH}")
        except Exception as e:
            print(f"⚠️  Could not create backup: {e}")
        
        # Delete the corrupted database
        try:
            os.remove(DB_PATH)
            print(f"✅ Deleted corrupted database")
        except Exception as e:
            print(f"❌ Error deleting database: {e}")
            return False
    else:
        print(f"\n📁 No existing database found")
    
    # Create fresh database
    print(f"\n🔨 Creating fresh database...")
    
    try:
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Create new database with proper schema
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Websites table
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
        
        # Posts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                slug TEXT,
                content TEXT NOT NULL,
                meta_description TEXT,
                keywords TEXT,
                category TEXT,
                seo_score INTEGER,
                image_url TEXT,
                website_id INTEGER,
                published BOOLEAN DEFAULT 0,
                published_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (website_id) REFERENCES websites(id)
            )
        """)
        
        # Topic tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS used_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                topic TEXT NOT NULL,
                normalized_topic TEXT NOT NULL UNIQUE,
                topic_hash TEXT NOT NULL,
                post_id INTEGER,
                website_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (website_id) REFERENCES websites(id)
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_posts_title ON posts(title)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_used_topics_normalized 
            ON used_topics(normalized_topic)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_used_topics_category 
            ON used_topics(category)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_used_topics_hash 
            ON used_topics(topic_hash)
        """)
        
        conn.commit()
        conn.close()
        
        print(f"✅ Database created successfully!")
        print(f"📍 Location: {os.path.abspath(DB_PATH)}")
        
        # Verify database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        print(f"\n📊 Tables created:")
        for table in tables:
            print(f"   - {table[0]}")
        
        print("\n" + "=" * 60)
        print("✅ Database reset complete!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error creating database: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n⚠️  This will DELETE the existing database and create a new one.")
    print("⚠️  All existing posts, websites, and topics will be LOST.\n")
    
    response = input("Do you want to continue? (yes/no): ").lower().strip()
    
    if response in ['yes', 'y']:
        success = reset_database()
        if success:
            print("\n✅ You can now run your application!")
        else:
            print("\n❌ Database reset failed. Please check the errors above.")
    else:
        print("\n❌ Database reset cancelled.")