#!/usr/bin/env python3
"""
WordPress Setup Helper Script
Helps configure WordPress for clean URL publishing
"""

import requests
import sys
from typing import Optional

def check_wordpress_setup(site_url: str, username: str, password: str):
    """Check WordPress configuration"""
    
    print(f"\n🔍 Checking WordPress setup for {site_url}...")
    
    auth = (username, password)
    
    # 1. Test connection
    print("\n1. Testing API connection...")
    try:
        test_url = f"{site_url.rstrip('/')}/wp-json/wp/v2/posts?per_page=1"
        response = requests.get(test_url, auth=auth, timeout=10)
        
        if response.status_code == 401:
            print("❌ Authentication failed. Please check:")
            print("   - Username is correct")
            print("   - You're using an Application Password (not regular password)")
            print("   - Generate one at: User Profile → Application Passwords")
            return False
        
        if response.status_code == 200:
            print("✅ API connection successful!")
        else:
            print(f"❌ Connection failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False
    
    # 2. Check permalink structure
    print("\n2. Checking permalink structure...")
    posts = response.json()
    
    if posts:
        sample_url = posts[0].get('link', '')
        print(f"   Sample post URL: {sample_url}")
        
        if '?p=' in sample_url:
            print("⚠️  WARNING: WordPress is using default permalinks!")
            print("\n   To fix this:")
            print("   1. Login to WordPress Admin")
            print("   2. Go to Settings → Permalinks")
            print("   3. Select 'Post name' option")
            print("   4. Click 'Save Changes'")
            print("\n   This will enable clean URLs like:")
            print(f"   {site_url}/your-post-title/")
        else:
            print("✅ Clean permalinks are enabled!")
    else:
        print("ℹ️  No posts found to check permalink structure")
    
    # 3. Check REST API endpoints
    print("\n3. Checking REST API endpoints...")
    endpoints = [
        ('Posts', '/wp-json/wp/v2/posts'),
        ('Categories', '/wp-json/wp/v2/categories'),
        ('Tags', '/wp-json/wp/v2/tags'),
        ('Media', '/wp-json/wp/v2/media')
    ]
    
    all_good = True
    for name, endpoint in endpoints:
        try:
            url = f"{site_url.rstrip('/')}{endpoint}"
            resp = requests.get(url, auth=auth, timeout=5)
            if resp.status_code == 200:
                print(f"   ✅ {name} endpoint: OK")
            else:
                print(f"   ❌ {name} endpoint: Status {resp.status_code}")
                all_good = False
        except:
            print(f"   ❌ {name} endpoint: Failed")
            all_good = False
    
    if all_good:
        print("\n✅ WordPress is properly configured for publishing!")
        print("\nYou can now use these credentials in your app:")
        print(f"  Site URL: {site_url}")
        print(f"  Username: {username}")
        print(f"  Password: [your_application_password]")
    else:
        print("\n⚠️  Some issues were found. Please check the errors above.")
    
    return all_good

if __name__ == "__main__":
    print("=" * 60)
    print("WordPress Setup Checker for SEO Publishing System")
    print("=" * 60)
    
    # Get credentials
    site_url = input("\nEnter WordPress site URL (e.g., https://infinitecard.in): ").strip()
    username = input("Enter WordPress username: ").strip()
    password = input("Enter Application Password: ").strip()
    
    if not all([site_url, username, password]):
        print("❌ All fields are required!")
        sys.exit(1)
    
    # Ensure URL has protocol
    if not site_url.startswith('http'):
        site_url = f"https://{site_url}"
    
    # Run checks
    success = check_wordpress_setup(site_url, username, password)
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 Setup complete! Your WordPress is ready for publishing.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Please fix the issues above and try again.")
        print("=" * 60)