# scripts/check_db_config.py
"""
Check which database your app is configured to use.
Usage: python scripts/check_db_config.py
"""

import sys
import os

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from app.database import db
    
    print("\n" + "="*80)
    print("Database Configuration")
    print("="*80 + "\n")
    
    # Try different ways to get the database path
    db_path = None
    
    if hasattr(db, 'db_path'):
        db_path = db.db_path
        print(f"✅ Database path (from db.db_path): {db_path}")
    elif hasattr(db, 'database_url'):
        db_path = db.database_url
        print(f"✅ Database URL (from db.database_url): {db_path}")
    else:
        print("⚠️  Could not automatically detect database path")
    
    # Check if the file exists
    print("\nChecking common database locations:")
    possible_paths = [
        os.path.join(PROJECT_ROOT, 'data', 'blog_automation.db'),
        os.path.join(PROJECT_ROOT, 'blog_automation.db'),
        os.path.join(PROJECT_ROOT, 'app', 'blog_automation.db'),
    ]
    
    for path in possible_paths:
        rel_path = os.path.relpath(path, PROJECT_ROOT)
        if os.path.exists(path):
            size = os.path.getsize(path)
            size_kb = size / 1024
            print(f"  ✅ {rel_path} ({size_kb:.2f} KB)")
        else:
            print(f"  ❌ {rel_path} (not found)")
    
    print("\n" + "="*80)
    print("\n💡 Recommended location: data/blog_automation.db")
    print("💡 To use this, ensure app/database.py has:")
    print('   self.db_path = "data/blog_automation.db"')
    print("\n" + "="*80 + "\n")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()