# check_database.py
import sqlite3
import os
from pathlib import Path

def find_database():
    """Find the database file"""
    possible_paths = [
        'data/blog_automation.db',
        'blog_automation.db',
        'app/data/blog_automation.db',
        './data/blog_automation.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def check_database():
    """Check database structure"""
    db_path = find_database()
    
    if not db_path:
        print("❌ Database file not found!")
        print("\nSearched in:")
        print("  - data/blog_automation.db")
        print("  - blog_automation.db")
        print("  - app/data/blog_automation.db")
        print("\nThe database might not be created yet.")
        print("Try running your app first to create it:")
        print("  python -m app.main")
        return
    
    print(f"✅ Found database at: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"Tables in database:")
    for table in tables:
        print(f"  - {table[0]}")
    
    # Check if posts table exists
    if any('posts' in str(table).lower() for table in tables):
        # Get posts table structure
        cursor.execute("PRAGMA table_info(posts);")
        columns = cursor.fetchall()
        
        print(f"\nColumns in 'posts' table:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Count posts
        cursor.execute("SELECT COUNT(*) FROM posts;")
        count = cursor.fetchone()[0]
        print(f"\nTotal posts: {count}")
        
        # Check posts with long meta descriptions
        cursor.execute("""
            SELECT id, title, LENGTH(meta_description) as len 
            FROM posts 
            WHERE LENGTH(meta_description) > 143
        """)
        long_metas = cursor.fetchall()
        
        if long_metas:
            print(f"\n❌ Posts with meta descriptions > 143 chars: {len(long_metas)}")
            for post_id, title, length in long_metas:
                print(f"   - Post #{post_id}: {title[:40]} ({length} chars)")
        else:
            print(f"\n✅ All meta descriptions are within limit!")
    else:
        print("\n❌ 'posts' table not found!")
    
    conn.close()

if __name__ == "__main__":
    check_database()