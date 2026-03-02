import sqlite3

conn = sqlite3.connect('data/blog_automation.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT id, name, domain, cms_type, api_url, api_key FROM websites').fetchall()
for r in rows:
    api_key = r['api_key'] or ''
    parts = api_key.split(':', 1)
    username = parts[0] if parts else 'N/A'
    print(f"ID: {r['id']}")
    print(f"  Name:     {r['name']}")
    print(f"  Domain:   {r['domain']}")
    print(f"  CMS:      {r['cms_type']}")
    print(f"  API URL:  {r['api_url']}")
    print(f"  Username: {username}")
    print(f"  API Key:  {api_key[:40]}...")
    print()
conn.close()
