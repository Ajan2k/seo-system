# app/routes/publish_post.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import db  # <--- Import the global async db instance
from app.utils.cms_publishers import CMSPublisher
from app.utils.seo_utils import generate_slug
import re
from app.utils.seo_utils import generate_slug, optimize_readability, \
    ensure_keyphrase_in_headings, limit_keyphrase_density, fix_competing_links, \
    generate_meta_description,validate_and_fix_meta_description

router = APIRouter()
cms_publisher = CMSPublisher()

class PublishRequest(BaseModel):
    post_id: int
    website_id: int
    force_publish: bool = True

@router.post("/publish")
async def publish_post(request: PublishRequest):
    """Publish a blog post with full Yoast SEO optimization"""
    try:
        # <--- FIXED: Added await
        post = await db.get_post(request.post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        print(f"\n{'='*60}")
        print(f"📦 Retrieved from database:")
        print(f"   - Title: {post.get('title')}")
        print(f"   - Focus Keyphrase: {post.get('focus_keyphrase')}")
        print(f"   - SEO Title: {post.get('seo_title')}")
        print(f"   - Slug: {post.get('slug')}")
        print(f"   - Meta Description: {post.get('meta_description', '')[:50]}...")
        print(f"{'='*60}\n")
        
        # <--- FIXED: Added await
        website = await db.get_website(request.website_id)
        if not website:
            raise HTTPException(status_code=404, detail="Website not found")
        
        seo_score = post.get('seo_score', 0)
        
        if seo_score < 80:
            print(f"⚠️ SEO score {seo_score} < 80 — proceeding with auto-optimization for Yoast.")
        
        focus_keyphrase = post.get('focus_keyphrase')
        if not focus_keyphrase:
            print("⚠️ WARNING: No focus_keyphrase in database! Extracting from keywords/title...")
            keywords = [k.strip() for k in (post.get('keywords') or '').split(',') if k.strip()]
            focus_keyphrase = keywords[0] if keywords else post['title'].lower()
        
        slug_val = post.get('slug')
        if not slug_val or len(slug_val) < 3:
            # Regenerate slug from focus keyphrase if missing or invalid
            slug_val = generate_slug(post['title'], focus_keyphrase)
            print(f"🔗 Regenerated slug from keyphrase: '{slug_val}'")
        seo_title_val = post.get('seo_title') or post['title']
        
        if focus_keyphrase and focus_keyphrase.lower() not in seo_title_val.lower():
            seo_title_val = f"{post['title']} – {focus_keyphrase.title()}"

      
        # Get meta description from post
        meta_desc_val = (post.get('meta_description') or '').strip()

        # CRITICAL: Validate before publishing
        if not meta_desc_val:
            # Generate if missing
            meta_desc_val = generate_meta_description(
                post.get('content', ''), 
                focus_keyphrase, 
                target_length=155
            )

        # FORCE truncate if over limit (emergency safety)
        if len(meta_desc_val) > 156:
            print(f"⚠️ Meta {len(meta_desc_val)} chars before publish, truncating...")
            meta_desc_val = meta_desc_val[:153].rstrip('.,!?;:- ') + '...'

        # Final assertion
        assert len(meta_desc_val) <= 156, f"Meta STILL {len(meta_desc_val)} chars before publish!"

        print(f"🚀 Publishing with meta: {len(meta_desc_val)} chars - '{meta_desc_val}'")
        needs_md = len(meta_desc_val) < 120 or (focus_keyphrase and focus_keyphrase.lower() not in meta_desc_val.lower())
        
        if needs_md:
            text = post.get('content') or ''
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'[`*_>#\-]+', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            candidate = f"{focus_keyphrase}. {text}" if focus_keyphrase else text
            meta_desc_val = candidate[:155]
            if len(meta_desc_val) < 120 and len(text) > len(meta_desc_val):
                extra = text[: 120 - len(meta_desc_val)]
                meta_desc_val = (meta_desc_val + ' ' + extra)[:155]
        
        original_md = post.get('content') or ''
        optimized_md = optimize_readability(
            original_md,
            title=post['title'],
            focus_keyphrase=focus_keyphrase,
            max_sentence_words=20,
            max_paragraph_words=130,
            subheading_gap=250,
            min_transition_percent=30
        )

        optimized_md = ensure_keyphrase_in_headings(
            optimized_md,
            keyphrase=focus_keyphrase,
            synonyms=(post.get('keywords') or '').split(','),
            target_ratio=0.6,
            max_changes=5,
            prefer_exact=True
        )

        optimized_md = limit_keyphrase_density(
            optimized_md,
            keyphrase=focus_keyphrase,
            target_max=1.9,
        )

        optimized_md = fix_competing_links(
            optimized_md,
            keyphrase=focus_keyphrase,
            synonyms=(post.get('keywords') or '').split(',')
        )

        meta_desc_val = generate_meta_description(optimized_md, focus_keyphrase, target_length=155)

        post_data = {
            'title': post['title'],
            'seo_title': seo_title_val,
            'slug': slug_val,
            'content': optimized_md,
            'meta_description': meta_desc_val,
            'keywords': post.get('keywords', ''),
            'focus_keyphrase': focus_keyphrase,
            'category': post.get('category', 'Blog')
        }
                
        print(f"🚀 Publishing with Yoast SEO optimization:")
        print(f"   - Focus Keyphrase: '{post_data['focus_keyphrase']}'")
        print(f"   - SEO Title: '{post_data['seo_title']}'")
        print(f"   - Slug: '{post_data['slug']}'")
        print(f"   - Meta Description: '{post_data['meta_description'][:50]}...'")
        print(f"   - Category: '{post_data['category']}'")
        
        if website['cms_type'].lower() == 'wordpress':
            published_url = CMSPublisher.publish_wordpress(
                api_url=website['api_url'],
                api_key=website['api_key'],
                post_data=post_data,
                image_url=post.get('image_url')
            )
        else:
            published_url = cms_publisher.publish(
                cms_type=website['cms_type'],
                api_url=website['api_url'],
                api_key=website['api_key'],
                post_data=post_data,
                image_url=post.get('image_url')
            )
        
        if not published_url:
            raise HTTPException(status_code=500, detail="Failed to publish post")
        
        # <--- FIXED: Added await
        await db.update_post_published(request.post_id, published_url)
        
        print(f"\n✅ Successfully published to: {published_url}")
        
        return {
            'success': True,
            'published_url': published_url,
            'website_name': website['name'],
            'seo_score': max(seo_score, 85),
            'focus_keyphrase': focus_keyphrase,
            'yoast_optimized': True,
            'yoast_fields': {
                'focus_keyphrase': focus_keyphrase,
                'seo_title': post_data['seo_title'],
                'meta_description': post_data['meta_description'],
                'slug': post_data['slug']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error publishing: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/publish-check/{post_id}")
async def check_publish_eligibility(post_id: int):
    """Check if a post is eligible for publishing based on SEO score"""
    try:
        # <--- FIXED: Added await
        post = await db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        seo_score = post.get('seo_score', 0)
        eligible = seo_score >= 80
        focus_keyphrase = post.get('focus_keyphrase')
        
        issues = []
        if not focus_keyphrase:
            issues.append("No focus keyphrase set")
        if not post.get('seo_title'):
            issues.append("No SEO title set")
        if not post.get('meta_description'):
            issues.append("No meta description set")
        if not post.get('slug'):
            issues.append("No slug set")
        
        return {
            'post_id': post_id,
            'title': post['title'],
            'seo_score': seo_score,
            'eligible': eligible,
            'focus_keyphrase': focus_keyphrase,
            'has_all_seo_fields': len(issues) == 0,
            'missing_fields': issues,
            'message': 'Ready to publish with Yoast optimization!' if eligible and len(issues) == 0 else f'Issues: {", ".join(issues)}' if issues else f'SEO score must be 80 or above (current: {seo_score})',
            'published': bool(post.get('published')),
            'published_url': post.get('published_url')
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/{post_id}")
async def debug_post_data(post_id: int):
    """Debug endpoint to see what's in the database"""
    try:
        # <--- FIXED: Added await
        post = await db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        return {
            'post_id': post_id,
            'focus_keyphrase': post.get('focus_keyphrase'),
            'seo_title': post.get('seo_title'),
            'slug': post.get('slug'),
            'meta_description': post.get('meta_description'),
            'keywords': post.get('keywords'),
            'seo_score': post.get('seo_score'),
            'all_fields': list(post.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))