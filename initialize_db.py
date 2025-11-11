# initialize_db.py
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def init_database():
    """Initialize database with proper tables"""
    try:
        print("Initializing database tables...")
        
        from app.database import db
        
        # This should create all necessary tables
        await db.init_db()
        
        print("✅ Database tables created successfully!\n")
        
        # Verify tables were created
        import sqlite3
        conn = sqlite3.connect('data/blog_automation.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("Tables in database:")
        for table in tables:
            print(f"  ✅ {table[0]}")
        
        # Check if posts table exists now
        if any('posts' in str(table).lower() for table in tables):
            cursor.execute("PRAGMA table_info(posts);")
            columns = cursor.fetchall()
            
            print(f"\nColumns in 'posts' table:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(init_database())