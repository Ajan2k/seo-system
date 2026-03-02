"""
WordPress deep auth diagnostic - tests capabilities and post creation.
Also checks if Application Password might have been created under different user.
"""
import requests
import sqlite3

conn = sqlite3.connect('data/blog_automation.db')
row = conn.execute('SELECT api_url, api_key FROM websites WHERE id = 1').fetchone()
api_url, api_key = row
conn.close()

parts = api_key.split(':', 1)
username, app_password = parts[0], parts[1]
auth = (username, app_password)
base = api_url.rstrip('/')

print(f"Base URL: {base}")
print(f"Username: {username}")
print(f"App Password: ...{app_password[-4:]}")

# Check: does the site URL redirect?
print("\n--- Check 1: Does the URL redirect? ---")
r = requests.get(f"{base}/wp-json/wp/v2/posts?per_page=1", auth=auth, timeout=15, allow_redirects=False)
print(f"Status: {r.status_code}")
if r.status_code in (301, 302, 307, 308):
    location = r.headers.get('Location', 'N/A')
    print(f"REDIRECT -> {location}")
    print("THIS could be the problem! The URL redirects, which may drop auth headers.")
    # Follow redirect
    print(f"\nFollowing redirect to: {location}")
    r2 = requests.get(location, auth=auth, timeout=15)
    print(f"Status after redirect: {r2.status_code}")
else:
    print("No redirect (good)")

# Check: list all users to see roles
print("\n--- Check 2: List users ---")
r = requests.get(f"{base}/wp-json/wp/v2/users?context=edit", auth=auth, timeout=10)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    users = r.json()
    for u in users[:5]:
        print(f"  User {u['id']}: {u.get('username', u.get('slug'))} | Roles: {u.get('roles', [])}")

# Check: /users/me on the EXACT base URL
print("\n--- Check 3: /users/me (with context=edit) ---")
r = requests.get(f"{base}/wp-json/wp/v2/users/me?context=edit", auth=auth, timeout=10)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  Roles: {data.get('roles')}")
    caps = data.get('capabilities', {})
    print(f"  publish_posts: {caps.get('publish_posts', 'NOT FOUND')}")
    print(f"  edit_posts: {caps.get('edit_posts', 'NOT FOUND')}")

# Check: Try POST with ?_method=POST (some servers block POST)
print("\n--- Check 4: Direct POST to create draft ---")
payload = {
    'title': 'Test Post - DELETE ME',
    'content': '<p>Test content from diagnostic</p>',
    'status': 'draft'
}
r = requests.post(f"{base}/wp-json/wp/v2/posts", auth=auth, json=payload, timeout=15,
                   headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
print(f"Status: {r.status_code}")
if r.status_code == 201:
    result = r.json()
    post_id = result.get('id')
    print(f"SUCCESS! Created draft post ID: {post_id}")
    # Clean up
    requests.delete(f"{base}/wp-json/wp/v2/posts/{post_id}?force=true", auth=auth)
    print("Test post cleaned up.")
    print("\n=== PUBLISHING SHOULD WORK FROM THIS URL ===")
elif r.status_code in (401, 403):
    resp_data = r.json() if 'json' in r.headers.get('content-type', '') else {}
    print(f"Code: {resp_data.get('code')}")
    print(f"Message: {resp_data.get('message')}")
    print(f"Full response: {r.text[:500]}")
else:
    print(f"Unexpected! Response: {r.text[:500]}")

# Check: Is there an .htaccess or plugin blocking app passwords?
print("\n--- Check 5: Test with Authorization header instead of basic auth ---")
import base64
creds = base64.b64encode(f"{username}:{app_password}".encode()).decode()
r = requests.post(
    f"{base}/wp-json/wp/v2/posts",
    json=payload,
    timeout=15,
    headers={
        'Content-Type': 'application/json',
        'Authorization': f'Basic {creds}',
        'User-Agent': 'Mozilla/5.0'
    }
)
print(f"Status: {r.status_code}")
if r.status_code == 201:
    result = r.json()
    post_id = result.get('id')
    print(f"SUCCESS with Authorization header! Post ID: {post_id}")
    requests.delete(f"{base}/wp-json/wp/v2/posts/{post_id}?force=true", 
                    headers={'Authorization': f'Basic {creds}'})
    print("Cleaned up.")
elif r.status_code in (401, 403):
    print(f"Response: {r.text[:500]}")
