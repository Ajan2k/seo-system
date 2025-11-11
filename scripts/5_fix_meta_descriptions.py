# scripts/5_fix_meta_descriptions.py
"""
Fix meta descriptions that exceed 143 characters.
Usage: python scripts/5_fix_meta_descriptions.py
"""

import sqlite3
import os
import sys
import re

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

def truncate_meta(meta: str, max_len: int = 143) -> str:
    """Truncate meta description to exactly max_len characters"""
    if not meta:
        return ""
    
    # Clean whitespace
    meta = re.sub(r'\s+', ' ', meta).strip()
    
    if len(meta) <= max_len:
        return meta
    
    # Truncate to 153 to leave room for ellipsis
    truncated = meta[:153]
    
    # Cut at last space to avoid mid-word
    last_space = truncated.rfind(' ')
    if last_space > 120:
        truncated = truncated[:last_space]
    
    # Remove trailing punctuation
    truncated = truncated.rstrip('.,!?;:- ')
    
    # Add ellipsis
    result = truncated + '...'
    
    # Final check
    if len(result) > max_len:
        result = meta[:153].rstrip('.,!?;:- ') + '...'
    
    return result

def fix_meta_descriptions():
    """Fix all meta descriptions in database"""
    
    db_path = os.path.join(PROJECT_ROOT, 'data', 'blog_automation.db')
    
    if not os.path.exists(db_path):
        print("❌ Database file not found at: data/blog_automation.db")
        print("\n💡 Run this first: python scripts/2_create_tables.py")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if posts table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts';")
    if not cursor.fetchone():
        print("❌ 'posts' table does not exist!")
        print("\n💡 Run this first: python scripts/2_create_tables.py")
        conn.close()
        return
    
    # Get all posts with meta descriptions
    cursor.execute("SELECT id, title, meta_description FROM posts")
    posts = cursor.fetchall()
    
    if not posts:
        print("ℹ️  No posts found in database yet.")
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
            print(f"     '{meta[:80]}...'")
            
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
    print(f"{'='*80}")
    print(f"\n💡 Verify: python scripts/3_check_database.py")
    print()

if __name__ == "__main__":
    fix_meta_descriptions()