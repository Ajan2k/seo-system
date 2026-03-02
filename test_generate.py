import asyncio
import httpx
import json

async def main():
    print("Sending test request to /api/generate ...")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=200) as c:
        r = await c.post("/api/generate", json={
            "category":     "technology",
            "custom_topic": "AI tools for productivity",
            "focus_keyword": "AI productivity tools",
            "brand_name":   "TestBrand",
            "target_score": 65,
        })
        print(f"HTTP Status: {r.status_code}")
        data = r.json()
        if r.status_code == 200:
            print(f"\n SUCCESS")
            print(f"  Title      : {data.get('title')}")
            print(f"  SEO Score  : {data.get('seo_score')}/100")
            print(f"  Word count : {data.get('word_count')}")
            print(f"  Keyphrase  : {data.get('focus_keyphrase')}")
            print(f"  Sources    : {data.get('research_sources')}")
            print(f"  Published? : {data.get('ready_to_publish')}")
        else:
            print(f"\n  ERROR {r.status_code}:")
            print(json.dumps(data, indent=2)[:600])

asyncio.run(main())
