#!/usr/bin/env python3
"""
WordPress API Diagnostic Script
Tests authentication, user roles, and REST API access
"""
import requests
import sys
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'blog_automation.db')

def get_website_credentials(website_id=None):
    """Read credentials from the database"""
    db_path = os.path.abspath(DB_PATH)
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    if website_id:
        row = conn.execute("SELECT * FROM websites WHERE id = ?", (website_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM websites WHERE cms_type = 'wordpress' LIMIT 1").fetchone()
    
    conn.close()
    
    if not row:
        print("❌ No WordPress website found in database")
        return None
    
    return dict(row)


def diagnose(site_url, username, app_password):
    print(f"\n{'='*60}")
    print(f"🔍 WordPress API Diagnostic")
    print(f"{'='*60}")
    print(f"  Site URL : {site_url}")
    print(f"  Username : {username}")
    print(f"  Password : {'*' * (len(app_password) - 4)}{app_password[-4:]}")
    print(f"{'='*60}\n")
    
    base = site_url.rstrip('/')
    auth = (username, app_password)
    
    # ── Test 1: Is the site reachable? ──
    print("1️⃣  Testing site reachability...")
    try:
        r = requests.get(f"{base}/wp-json/", timeout=10)
        if r.status_code == 200:
            info = r.json()
            print(f"   ✅ Site reachable: {info.get('name', 'Unknown')}")
            print(f"   URL: {info.get('url', 'N/A')}")
        else:
            print(f"   ⚠️  Site returned status {r.status_code}")
    except Exception as e:
        print(f"   ❌ Cannot reach site: {e}")
        return
    
    # ── Test 2: Is REST API accessible (unauthenticated)? ──
    print("\n2️⃣  Testing REST API (no auth)...")
    try:
        r = requests.get(f"{base}/wp-json/wp/v2/posts?per_page=1", timeout=10)
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            print(f"   ✅ REST API is publicly accessible")
        elif r.status_code == 401:
            print(f"   ⚠️  REST API requires authentication even to read")
        elif r.status_code == 403:
            print(f"   ❌ REST API is BLOCKED (security plugin?)")
        else:
            print(f"   ⚠️  Unexpected response: {r.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # ── Test 3: Test authentication with /users/me ──
    print("\n3️⃣  Testing authentication (GET /users/me)...")
    try:
        r = requests.get(f"{base}/wp-json/wp/v2/users/me", auth=auth, timeout=10)
        print(f"   Status: {r.status_code}")
        
        if r.status_code == 200:
            user = r.json()
            print(f"   ✅ Authentication SUCCESSFUL!")
            print(f"   User ID   : {user.get('id')}")
            print(f"   Name      : {user.get('name')}")
            print(f"   Slug      : {user.get('slug')}")
            roles = user.get('roles', [])
            caps = user.get('capabilities', {})
            print(f"   Roles     : {roles}")
            
            # Check if user can publish
            can_publish = caps.get('publish_posts', False)
            can_edit = caps.get('edit_posts', False)
            print(f"   Can edit posts    : {can_edit}")
            print(f"   Can publish posts : {can_publish}")
            
            if not can_publish:
                print(f"\n   🚨 THIS IS THE PROBLEM!")
                print(f"   The user '{username}' has roles: {roles}")
                print(f"   This role does NOT have 'publish_posts' capability.")
                print(f"\n   FIX: In WordPress Admin → Users, change this user's role to:")
                print(f"         • Administrator (full access)")
                print(f"         • Editor (can publish/edit all posts)")
                print(f"         • Author (can publish own posts)")
                return
            else:
                print(f"\n   ✅ User HAS publish_posts capability — role is fine!")
                
        elif r.status_code == 401:
            data = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
            code = data.get('code', 'unknown')
            message = data.get('message', r.text[:200])
            print(f"   ❌ Authentication FAILED!")
            print(f"   Error code: {code}")
            print(f"   Message: {message}")
            
            if 'incorrect_password' in code or 'invalid_password' in code:
                print(f"\n   🚨 The password is WRONG.")
                print(f"   Make sure you're using an APPLICATION PASSWORD, not regular password.")
                print(f"   Generate one at: {base}/wp-admin/profile.php")
            elif 'invalid_username' in code:
                print(f"\n   🚨 The username '{username}' does NOT exist on this WordPress site.")
                print(f"   Check the exact username in WordPress Admin → Users.")
            else:
                print(f"\n   Possible causes:")
                print(f"   - Wrong application password")
                print(f"   - Application Passwords disabled (by plugin or .htaccess)")
                print(f"   - HTTP Basic Auth blocked by server config")
            return
        elif r.status_code == 403:
            print(f"   ❌ Access FORBIDDEN")
            print(f"   Response: {r.text[:300]}")
            print(f"\n   A security plugin may be blocking REST API access.")
            return
        else:
            print(f"   ❌ Unexpected status: {r.status_code}")
            print(f"   Response: {r.text[:300]}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # ── Test 4: Try creating a draft post ──
    print("\n4️⃣  Testing post creation (draft)...")
    try:
        payload = {
            'title': 'AI Blog Test Post (DELETE ME)',
            'content': '<p>This is a test post from the diagnostic script.</p>',
            'status': 'draft'  # draft, not publish
        }
        r = requests.post(
            f"{base}/wp-json/wp/v2/posts",
            auth=auth,
            json=payload,
            timeout=15
        )
        print(f"   Status: {r.status_code}")
        
        if r.status_code == 201:
            result = r.json()
            post_id = result.get('id')
            print(f"   ✅ Draft post created! ID: {post_id}")
            print(f"   Cleaning up (deleting test post)...")
            # Delete the test post
            del_r = requests.delete(
                f"{base}/wp-json/wp/v2/posts/{post_id}?force=true",
                auth=auth, timeout=10
            )
            if del_r.status_code == 200:
                print(f"   ✅ Test post deleted. Everything works!")
            else:
                print(f"   ⚠️  Couldn't delete test post (ID: {post_id}). Delete manually.")
                
            print(f"\n{'='*60}")
            print(f"✅ ALL TESTS PASSED — WordPress publishing should work!")
            print(f"{'='*60}")
        else:
            data = r.json() if r.headers.get('content-type','').startswith('application/json') else {}
            print(f"   ❌ Cannot create post!")
            print(f"   Code: {data.get('code', 'unknown')}")
            print(f"   Message: {data.get('message', r.text[:300])}")
            
            if r.status_code == 401:
                print(f"\n   🚨 Authentication passed /users/me but FAILED on /posts")
                print(f"   This usually means:")
                print(f"   - A security plugin is selectively blocking POST requests")
                print(f"   - .htaccess rules are interfering with POST methods")
                print(f"   - The Application Password has limited scope")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    

if __name__ == "__main__":
    print("\n" + "="*60)
    print("WordPress API Diagnostic Tool")
    print("="*60)
    
    # Try to read from database
    website = get_website_credentials()
    
    if website:
        print(f"\n📂 Found website in database: {website.get('name')} ({website.get('domain')})")
        api_url = website.get('api_url', '')
        api_key = website.get('api_key', '')
        
        if ':' in api_key:
            parts = api_key.split(':', 1)
            diagnose(api_url, parts[0], parts[1])
        else:
            print(f"❌ api_key is not in 'username:password' format: '{api_key[:20]}...'")
    else:
        site_url = input("\nEnter WordPress site URL: ").strip()
        username = input("Enter WordPress username: ").strip()
        password = input("Enter Application Password: ").strip()
        diagnose(site_url, username, password)
