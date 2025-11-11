# scripts/4_migrate_posts.py
"""
Migrate posts from old database to new database.
Usage: python scripts/4_migrate_posts.py <path_to_old_db>
Example: python scripts/4_migrate_posts.py blog_automation.db
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def migrate_posts(old_db_path):
    """Migrate posts from old database to new database"""
    
    # Convert relative path to absolute from project root
    if not os.path.isabs(old_db_path):
        old_db_path = os.path.join(PROJECT_ROOT, old_db_path)
    
    new_db_path = os.path.join(PROJECT_ROOT, 'data', 'blog_automation.db')
    
    if not os.path.exists(old_db_path):
        print(f"❌ Old database not found: {old_db_path}")
        print("\n💡 Run this first: python scripts/1_find_all_databases.py")
        return
    
    if not os.path.exists(new_db_path):
        print(f"❌ New database not found: data/blog_automation.db")
        print("\n💡 Run this first: python scripts/2_create_tables.py")
        return
    
    # Backup new database first
    backup_dir = os.path.join(PROJECT_ROOT, 'data', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"blog_automation.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(new_db_path, backup_path)
    print(f"✅ Backed up new database to: data/backups/\n")
    
    # Connect to both databases
    old_conn = sqlite3.connect(old_db_path)
    new_conn = sqlite3.connect(new_db_path)
    
    old_cursor = old_conn.cursor()
    new_cursor = new_conn.cursor()
    
    print("="*80)
    print("Migrating Posts")
    print("="*80 + "\n")
    
    # Get posts from old database
    try:
        old_cursor.execute("SELECT * FROM posts")
        posts = old_cursor.fetchall()
    except Exception as e:
        print(f"❌ Error reading old database: {e}")
        return
    
    # Get column names
    old_cursor.execute("PRAGMA table_info(posts)")
    old_columns = [col[1] for col in old_cursor.fetchall()]
    
    new_cursor.execute("PRAGMA table_info(posts)")
    new_columns = [col[1] for col in new_cursor.fetchall()]
    
    print(f"Found {len(posts)} posts in old database")
    print(f"Columns match: {set(old_columns) & set(new_columns)}\n")
    
    # Migrate each post
    migrated = 0
    fixed_meta = 0
    
    for post in posts:
        post_dict = dict(zip(old_columns, post))
        
        # Fix meta description if too long
        meta = post_dict.get('meta_description', '')
        if meta and len(meta) > 143:
            original_len = len(meta)
            meta = meta[:153].rstrip('.,!?;:- ') + '...'
            print(f"  📝 Post #{post_dict.get('id')}: {post_dict.get('title', '')[:50]}")
            print(f"     Meta: {original_len} → {len(meta)} chars")
            post_dict['meta_description'] = meta
            fixed_meta += 1
        
        # Build insert query with only matching columns
        common_columns = [col for col in old_columns if col in new_columns and col != 'id']
        placeholders = ', '.join(['?' for _ in common_columns])
        column_names = ', '.join(common_columns)
        
        values = [post_dict.get(col) for col in common_columns]
        
        try:
            new_cursor.execute(
                f"INSERT INTO posts ({column_names}) VALUES ({placeholders})",
                values
            )
            migrated += 1
        except Exception as e:
            print(f"  ❌ Error migrating post #{post_dict.get('id')}: {e}")
    
    # Migrate websites if they exist
    try:
        old_cursor.execute("SELECT * FROM websites")
        websites = old_cursor.fetchall()
        
        if websites:
            old_cursor.execute("PRAGMA table_info(websites)")
            web_columns = [col[1] for col in old_cursor.fetchall()]
            
            for website in websites:
                web_dict = dict(zip(web_columns, website))
                common_cols = [col for col in web_columns if col != 'id']
                
                new_cursor.execute(
                    f"INSERT INTO websites ({', '.join(common_cols)}) VALUES ({', '.join(['?' for _ in common_cols])})",
                    [web_dict.get(col) for col in common_cols]
                )
            
            print(f"\n✅ Migrated {len(websites)} website(s)")
    except:
        print("\nℹ️  No websites to migrate")
    
    new_conn.commit()
    
    old_conn.close()
    new_conn.close()
    
    print("\n" + "="*80)
    print(f"✅ Migration Complete!")
    print(f"   - Migrated: {migrated} posts")
    print(f"   - Fixed meta descriptions: {fixed_meta}")
    print(f"   - Backup: data/backups/")
    print("="*80)
    print(f"\n💡 Next step: python scripts/3_check_database.py")
    print()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        old_db = sys.argv[1]
        migrate_posts(old_db)
    else:
        print("\n❌ Missing argument: old database path")
        print("\nUsage: python scripts/4_migrate_posts.py <path_to_old_database>")
        print("\nExamples:")
        print("  python scripts/4_migrate_posts.py blog_automation.db")
        print("  python scripts/4_migrate_posts.py app/data/blog.db")
        print("\n💡 First, run: python scripts/1_find_all_databases.py")
        print()