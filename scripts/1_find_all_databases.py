# scripts/1_find_all_databases.py
"""
Find all SQLite database files in the project.
Usage: python scripts/1_find_all_databases.py
"""

import os
import sqlite3
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def find_databases():
    """Search for all SQLite database files"""
    
    print("\n" + "="*80)
    print("Searching for Database Files")
    print("="*80 + "\n")
    
    # Search from project root
    search_paths = [PROJECT_ROOT]
    
    found_databases = []
    
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        
        for root, dirs, files in os.walk(search_path):
            # Skip common non-relevant directories
            dirs[:] = [d for d in dirs if d not in [
                'node_modules', '.git', '__pycache__', 'venv', 'env', 
                '.venv', 'site-packages', 'dist', 'build', 'scripts'
            ]]
            
            for file in files:
                if file.endswith('.db') or file.endswith('.sqlite') or file.endswith('.sqlite3'):
                    db_path = os.path.join(root, file)
                    # Make path relative to project root
                    rel_path = os.path.relpath(db_path, PROJECT_ROOT)
                    found_databases.append((db_path, rel_path))
    
    if not found_databases:
        print("❌ No database files found!")
        return []
    
    print(f"Found {len(found_databases)} database file(s):\n")
    
    for i, (db_path, rel_path) in enumerate(found_databases, 1):
        print(f"{i}. {rel_path}")
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check for tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            if tables:
                print(f"   Tables: {', '.join([t[0] for t in tables])}")
            
            # Check for posts
            if any('posts' in str(t).lower() for t in tables):
                cursor.execute("SELECT COUNT(*) FROM posts")
                post_count = cursor.fetchone()[0]
                print(f"   📝 Posts: {post_count}")
                
                if post_count > 0:
                    # Show some post titles
                    cursor.execute("SELECT id, title, LENGTH(meta_description) as meta_len FROM posts ORDER BY id DESC LIMIT 3")
                    recent_posts = cursor.fetchall()
                    print(f"   Recent posts:")
                    for post_id, title, meta_len in recent_posts:
                        status = "✅" if meta_len <= 143 else f"❌ ({meta_len} chars)"
                        print(f"      - #{post_id}: {title[:50]} - Meta: {status}")
            
            # Check for websites
            if any('websites' in str(t).lower() for t in tables):
                cursor.execute("SELECT COUNT(*) FROM websites")
                web_count = cursor.fetchone()[0]
                if web_count > 0:
                    print(f"   🌐 Websites: {web_count}")
            
            conn.close()
        except Exception as e:
            print(f"   ⚠️ Error reading database: {e}")
        
        print()
    
    print("="*80)
    print("\n💡 Next steps:")
    print("   - If posts exist in old database, run: python scripts/4_migrate_posts.py")
    print("   - To create new database, run: python scripts/2_create_tables.py")
    print("   - To check database, run: python scripts/3_check_database.py")
    print("="*80 + "\n")
    
    return found_databases

if __name__ == "__main__":
    find_databases()