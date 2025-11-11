# fix_meta_final.py
import sqlite3
import re
import os

def truncate_meta(meta: str, max_len: int = 143) -> str:
    """Truncate meta description to exactly max_len characters"""
    if not meta:
        return ""
    
    meta = re.sub(r'\s+', ' ', meta).strip()
    
    if len(meta) <= max_len:
        return meta
    
    truncated = meta[:153]
    last_space = truncated.rfind(' ')
    if last_space > 120:
        truncated = truncated[:last_space]
    
    truncated = truncated.rstrip('.,!?;:- ')
    result = truncated + '...'
    
    if len(result) > max_len:
        result = meta[:153].rstrip('.,!?;:- ') + '...'
    
    return result

def fix_all_posts():
    """Fix all meta descriptions in database"""
    
    db_path = 'data/blog_automation.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if posts table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts';")
    if not cursor.fetchone():
        print("❌ 'posts' table does not exist!")
        print("\nPlease run: python create_tables_manual.py")
        conn.close()
        return
    
    # Get all posts
    cursor.execute("SELECT id, title, meta_description FROM posts")
    posts = cursor.fetchall()
    
    if not posts:
        print("ℹ️ No posts found in database yet.")
        print("   Generate some blog posts first, then run this script again.")
        conn.close()
        return
    
    print(f"\n{'='*80}")
    print(f"Checking {len(posts)} posts for meta description length issues...")
    print(f"{'='*80}\n")
    
    fixed_count = 0
    
    for post_id, title, meta in posts:
        if not meta:
            continue
        
        original_len = len(meta)
        
        if original_len > 143:
            print(f"Post #{post_id}: {title[:50] if title else 'Untitled'}")
            print(f"  ❌ Before: {original_len} chars")
            print(f"     '{meta}'")
            
            # Fix it
            fixed_meta = truncate_meta(meta, 143)
            
            print(f"  ✅ After: {len(fixed_meta)} chars")
            print(f"     '{fixed_meta}'")
            
            # Update database
            cursor.execute(
                "UPDATE posts SET meta_description = ? WHERE id = ?",
                (fixed_meta, post_id)
            )
            
            fixed_count += 1
            print()
    
    conn.commit()
    conn.close()
    
    print(f"{'='*80}")
    if fixed_count > 0:
        print(f"✅ Fixed {fixed_count} post(s)!")
    else:
        print(f"✅ All meta descriptions are already within 143 character limit!")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    fix_all_posts()