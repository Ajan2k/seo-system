# add_meta_constraint.py
import sqlite3

def add_constraint():
    conn = sqlite3.connect('data/blog_automation.db')
    cursor = conn.cursor()
    
    # SQLite doesn't support CHECK constraints easily on existing tables
    # So we'll add a trigger instead
    
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS check_meta_length
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
    
    conn.commit()
    conn.close()
    
    print("✅ Database triggers added to enforce 143 character limit!")

if __name__ == "__main__":
    add_constraint()