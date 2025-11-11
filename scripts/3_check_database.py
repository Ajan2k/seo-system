# scripts/3_check_database.py
"""
Check database structure and content.
Usage: python scripts/3_check_database.py
"""

import sqlite3
import os
import sys

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def check_database():
    """Check database structure and content"""
    
    db_path = os.path.join(PROJECT_ROOT, 'data', 'blog_automation.db')
    
    if not os.path.exists(db_path):
        print("❌ Database file not found at: data/blog_automation.db")
        print("\n💡 Run this first: python scripts/2_create_tables.py")
        return
    
    print(f"✅ Found database at: data/blog_automation.db\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    if not tables:
        print("❌ No tables found in database!")
        print("\n💡 Run this first: python scripts/2_create_tables.py")
        conn.close()
        return
    
    print(f"Tables in database:")
    for table in tables:
        print(f"  ✅ {table[0]}")
    print()
    
    # Check posts table
    if any('posts' in str(table).lower() for table in tables):
        # Get posts table structure
        cursor.execute("PRAGMA table_info(posts);")
        columns = cursor.fetchall()
        
        print(f"Columns in 'posts' table:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        print()
        
        # Count posts
        cursor.execute("SELECT COUNT(*) FROM posts;")
        count = cursor.fetchone()[0]
        print(f"Total posts: {count}\n")
        
        if count > 0:
            # Check posts with long meta descriptions
            cursor.execute("""
                SELECT id, title, LENGTH(meta_description) as len, focus_keyphrase
                FROM posts 
                WHERE LENGTH(meta_description) > 143
            """)
            long_metas = cursor.fetchall()
            
            if long_metas:
                print(f"❌ Posts with meta descriptions > 143 chars: {len(long_metas)}")
                for post_id, title, length, keyphrase in long_metas:
                    print(f"   - Post #{post_id}: {title[:40]} ({length} chars)")
                print(f"\n💡 Fix these: python scripts/5_fix_meta_descriptions.py")
            else:
                print(f"✅ All meta descriptions are within 143 character limit!")
            
            # Show recent posts
            print(f"\nRecent posts:")
            cursor.execute("""
                SELECT id, title, LENGTH(meta_description) as meta_len, 
                       seo_score, focus_keyphrase, published
                FROM posts 
                ORDER BY id DESC 
                LIMIT 5
            """)
            recent = cursor.fetchall()
            for post_id, title, meta_len, score, keyphrase, published in recent:
                status = "✅" if meta_len <= 143 else f"❌ {meta_len} chars"
                pub = "📤 Published" if published else "📝 Draft"
                print(f"   #{post_id}: {title[:40]}")
                print(f"      Meta: {status} | SEO: {score}/100 | {pub}")
                if keyphrase:
                    print(f"      Focus: {keyphrase}")
        
        print()
    
    # Check websites table
    if any('websites' in str(table).lower() for table in tables):
        cursor.execute("SELECT COUNT(*) FROM websites;")
        web_count = cursor.fetchone()[0]
        print(f"Total websites: {web_count}")
        
        if web_count > 0:
            cursor.execute("SELECT id, name, cms_type, domain FROM websites")
            websites = cursor.fetchall()
            print("\nWebsites:")
            for web_id, name, cms, domain in websites:
                print(f"   #{web_id}: {name} ({cms}) - {domain}")
        print()
    
    conn.close()

if __name__ == "__main__":
    check_database()