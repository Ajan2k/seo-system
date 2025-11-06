import requests
from typing import Dict, Optional
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import time
import re
import html as html_lib


class CMSPublisher:
    """Publish blog posts to different CMS platforms (WordPress, Ghost, Custom)"""

    def __init__(self):
        self.session = self._create_session_with_retries()

    def _create_session_with_retries(self):
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _generate_slug(self, title: str) -> str:
        """Generate URL-friendly slug from title."""
        # local, lightweight slugify (avoid dependency)
        s = title.lower()
        s = re.sub(r'[^a-z0-9\s-]', '', s)
        s = re.sub(r'\s+', '-', s)
        s = re.sub(r'-{2,}', '-', s)
        return s.strip('-')[:60]

    def _markdown_to_html(self, markdown_content: str) -> str:
        """Convert a subset of Markdown to HTML with image-first handling."""
        text = (markdown_content or '').replace('\r\n', '\n')

        # 1) Extract code blocks to placeholders to avoid interfering transforms
        code_blocks: list[str] = []

        def _codeblock_repl(m):
            code = m.group(1)
            token = f"[[[CODE_BLOCK_{len(code_blocks)}]]]"
            code_blocks.append(code)
            return token

        text = re.sub(r'```(.*?)```', _codeblock_repl, text, flags=re.DOTALL)

        # 2) Images FIRST (so they don't get turned into links)
        text = re.sub(r'!\[(.*?)\]\((.*?)\)', r'<img src="\2" alt="\1" />', text)

        # 3) Headings
        text = re.sub(r'^\s*###\s+(.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*##\s+(.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*#\s+(.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

        # 4) Bold and italic
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
        text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)

        # 5) Convert links (images already handled)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)

        # 6) Inline code
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

        # 7) Lists and paragraphs with simple state machine
        lines = text.split('\n')
        out = []
        in_ul = False
        in_ol = False

        def close_lists():
            nonlocal in_ul, in_ol
            if in_ul:
                out.append('</ul>')
                in_ul = False
            if in_ol:
                out.append('</ol>')
                in_ol = False

        for line in lines:
            stripped = line.strip()

            if stripped == '':
                close_lists()
                out.append('')
                continue

            # Keep placeholders and block-level HTML as-is
            if stripped.startswith('[[[CODE_BLOCK_'):
                close_lists()
                out.append(stripped)
                continue

            if re.match(r'^<(h[1-6]|ul|ol|li|pre|img|blockquote|figure|p|table|hr)\b', stripped):
                close_lists()
                out.append(stripped)
                continue

            # Unordered list item
            m_ul = re.match(r'^(\*|\-)\s+(.+)', stripped)
            if m_ul:
                if in_ol:
                    out.append('</ol>')
                    in_ol = False
                if not in_ul:
                    out.append('<ul>')
                    in_ul = True
                out.append(f"<li>{m_ul.group(2)}</li>")
                continue

            # Ordered list item
            m_ol = re.match(r'^\d+\.\s+(.+)', stripped)
            if m_ol:
                if in_ul:
                    out.append('</ul>')
                    in_ul = False
                if not in_ol:
                    out.append('<ol>')
                    in_ol = True
                out.append(f"<li>{m_ol.group(1)}</li>")
                continue

            # Paragraph
            close_lists()
            out.append(f'<p>{stripped}</p>')

        close_lists()
        html = '\n'.join(out)

        # 8) Restore code blocks
        for i, code in enumerate(code_blocks):
            escaped = html_lib.escape(code.strip('\n'))
            html = html.replace(f'[[[CODE_BLOCK_{i}]]]', f'<pre><code>{escaped}</code></pre>')

        return html

    def _download_and_upload_image(self, image_url: str, api_url: str, auth: tuple) -> Optional[int]:
        """Download image from URL and upload to WordPress; return media ID."""
        try:
            if not image_url:
                return None
            print(f"📸 Downloading image from: {image_url}")

            # Skip placeholders
            if 'placeholder.com' in image_url:
                print("⚠️ Skipping placeholder image")
                return None

            # Download image
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            img_response = self.session.get(image_url, headers=headers, timeout=30, allow_redirects=True)
            img_response.raise_for_status()

            content_type = img_response.headers.get('content-type', 'image/jpeg')

            # Filename heuristic
            filename = image_url.split('/')[-1].split('?')[0] or f'image-{int(time.time())}.jpg'
            if '.' not in filename:
                filename += '.jpg'

            print(f"📤 Uploading to WordPress: {filename}")
            media_url = f"{api_url.rstrip('/')}/wp-json/wp/v2/media"

            files = {'file': (filename, img_response.content, content_type)}
            headers = {'User-Agent': 'SEO-Publisher/1.0', 'Cache-Control': 'no-cache'}

            media_response = self.session.post(media_url, auth=auth, files=files, headers=headers, timeout=60)

            if media_response.status_code == 201:
                media_data = media_response.json()
                media_id = media_data['id']
                print(f"✅ Image uploaded: ID {media_id}")
                return media_id

            print(f"❌ Image upload failed: {media_response.status_code}")
            print(f"Response: {media_response.text}")
            return None

        except Exception as e:
            print(f"❌ Image upload error: {e}")
            return None

    def _inject_inline_image(self, html: str, img_url: str, alt_text: str) -> str:
        """Insert an inline hero image after the first paragraph, or at the top."""
        if not img_url:
            return html
        block = f'<figure><img src="{img_url}" alt="{alt_text}" /><figcaption>{alt_text}</figcaption></figure>'
        if '</p>' in html:
            return html.replace('</p>', f'</p>\n{block}', 1)
        return block + '\n' + html

    def _ensure_internal_link(self, html: str, site_base: str, keyphrase: str) -> str:
        """Ensure at least one internal link exists; fallback to homepage."""
        base = site_base.rstrip('/')
        # Strip /wp-json... if someone passed API root instead of site root
        base = re.sub(r'/wp-json.*$', '', base)
        if f'href="{base}/' in html:
            return html
        safe_title = (keyphrase or 'Learn more').strip()
        return html + f'\n<p>Explore more on <a href="{base}/" title="{safe_title}">{base}</a>.</p>'

    @staticmethod
    def publish_wordpress(api_url: str, api_key: str, post_data: Dict,
                          image_url: str = None) -> Optional[str]:
        """
        Publish to WordPress via REST API. api_key format: "username:application_password"
        Expects post_data keys: title, content, meta_description, seo_title, keywords, category, focus_keyphrase, slug (optional).
        """
        try:
            publisher = CMSPublisher()

            # Auth prep
            auth_parts = api_key.split(":")
            if len(auth_parts) != 2:
                raise ValueError("WordPress API key must be 'username:password'")
            auth = (auth_parts[0], auth_parts[1])

            # Slug: use provided or fallback
            slug = post_data.get('slug') or publisher._generate_slug(post_data['title'])

            print("\n" + "=" * 60)
            print("📝 Publishing to WordPress")
            print("=" * 60)
            print(f"Title: {post_data['title']}")
            print(f"Slug: {slug}")
            print(f"API URL: {api_url}")

            # Convert markdown → HTML
            content_html = publisher._markdown_to_html(post_data['content'])
            if not content_html or len(content_html.strip()) < 100:
                print("❌ Error: HTML content is too short or empty")
                raise ValueError("Content conversion failed - HTML is empty or too short")
            print(f"Content: {len(post_data['content'])} chars (markdown) → {len(content_html)} chars (HTML)")

            # Upload featured image (if provided)
            featured_media_id = None
            featured_media_src = None
            chosen_img = image_url or post_data.get('image_url')

            if chosen_img:
                featured_media_id = publisher._download_and_upload_image(chosen_img, api_url, auth)

            # Fetch source_url for inline image
            if featured_media_id:
                media_get = publisher.session.get(
                    f"{api_url.rstrip('/')}/wp-json/wp/v2/media/{featured_media_id}",
                    auth=auth, timeout=10
                )
                if media_get.status_code == 200:
                    featured_media_src = media_get.json().get('source_url')

            # Alt text including keyphrase
            alt_text = (f"{post_data.get('focus_keyphrase', '')} - {post_data['title']}".strip(" -"))[:125]

            # Inject inline image if not present
            if featured_media_src and '<img ' not in content_html:
                content_html = publisher._inject_inline_image(content_html, featured_media_src, alt_text or post_data['title'])

            # Ensure at least one internal link (fallback to homepage)
            content_html = publisher._ensure_internal_link(content_html, api_url, post_data.get('focus_keyphrase', post_data['title']))

            # Category handling
            category_ids = []
            primary_category_id = None
            if post_data.get('category'):
                print(f"\n📁 Processing category: {post_data['category']}")
                try:
                    cat_url = f"{api_url.rstrip('/')}/wp-json/wp/v2/categories"
                    # Try to find existing
                    cat_response = publisher.session.get(
                        cat_url,
                        params={'search': post_data['category']},
                        auth=auth,
                        timeout=10
                    )
                    if cat_response.status_code == 200:
                        categories = cat_response.json()
                        if categories:
                            primary_category_id = categories[0]['id']
                            category_ids.append(primary_category_id)
                            print(f"✅ Found existing category: ID {primary_category_id}")
                        else:
                            # Create new category
                            new_cat = {
                                'name': post_data['category'],
                                'slug': publisher._generate_slug(post_data['category'])
                            }
                            create_response = publisher.session.post(cat_url, json=new_cat, auth=auth, timeout=10)
                            if create_response.status_code == 201:
                                primary_category_id = create_response.json()['id']
                                category_ids.append(primary_category_id)
                                print(f"✅ Created new category: ID {primary_category_id}")
                except Exception as e:
                    print(f"⚠️ Category error: {e}")

            # Tags handling
            tag_ids = []
            if post_data.get('keywords'):
                print("\n🏷️  Processing tags...")
                try:
                    tags_url = f"{api_url.rstrip('/')}/wp-json/wp/v2/tags"
                    keywords = [k.strip() for k in post_data['keywords'].split(',')[:5]]
                    for keyword in keywords:
                        if not keyword:
                            continue
                        tag_response = publisher.session.get(tags_url, params={'search': keyword}, auth=auth, timeout=10)
                        if tag_response.status_code == 200:
                            tags = tag_response.json()
                            if tags:
                                tag_ids.append(tags[0]['id'])
                            else:
                                new_tag = {'name': keyword, 'slug': publisher._generate_slug(keyword)}
                                create_response = publisher.session.post(tags_url, json=new_tag, auth=auth, timeout=10)
                                if create_response.status_code == 201:
                                    tag_ids.append(create_response.json()['id'])
                    print(f"✅ Processed {len(tag_ids)} tags")
                except Exception as e:
                    print(f"⚠️ Tags error: {e}")

            # Prepare post payload
            post_url = f"{api_url.rstrip('/')}/wp-json/wp/v2/posts"
            payload = {
                'title': post_data['title'],
                'content': content_html,
                'slug': slug,
                'status': 'publish',
                'excerpt': post_data.get('meta_description', ''),
                'comment_status': 'open',
                'ping_status': 'open',
                'format': 'standard'
            }
            if category_ids:
                payload['categories'] = category_ids
            if tag_ids:
                payload['tags'] = tag_ids
            if featured_media_id:
                payload['featured_media'] = featured_media_id

            # Yoast SEO meta (both focuskw and focuskw_text_input)
            yoast_meta = {}
            if post_data.get('focus_keyphrase'):
                yoast_meta['_yoast_wpseo_focuskw'] = post_data['focus_keyphrase']
                yoast_meta['_yoast_wpseo_focuskw_text_input'] = post_data['focus_keyphrase']
            if post_data.get('meta_description'):
                yoast_meta['_yoast_wpseo_metadesc'] = post_data['meta_description']
            if post_data.get('seo_title'):
                yoast_meta['_yoast_wpseo_title'] = post_data['seo_title']

            if yoast_meta:
                payload['meta'] = yoast_meta
                print("\n🎯 Yoast SEO metadata added:")
                print(f"   - Focus Keyphrase: {yoast_meta.get('_yoast_wpseo_focuskw')}")
                if yoast_meta.get('_yoast_wpseo_metadesc'):
                    print(f"   - Meta Description: {yoast_meta.get('_yoast_wpseo_metadesc', '')[:50]}...")
                if yoast_meta.get('_yoast_wpseo_title'):
                    print(f"   - SEO Title: {yoast_meta.get('_yoast_wpseo_title')}")

            # Debug
            print("\n📤 Publishing post...")
            print(f"Payload keys: {list(payload.keys())}")
            print(f"Content preview: {content_html[:200]}...")

            # Publish
            response = publisher.session.post(
                post_url,
                auth=auth,
                json=payload,
                timeout=60,
                headers={'Content-Type': 'application/json', 'User-Agent': 'SEO-Publisher/1.0'}
            )

            if response.status_code == 201:
                result = response.json()
                post_id = result.get('id')
                published_url = result.get('link', '')

                # Confirm Yoast meta via bridge endpoint (requires tiny plugin)
                if post_id:
                    try:
                        bridge_url = f"{api_url.rstrip('/')}/wp-json/aiblog/v1/yoast/{post_id}"
                        bridge_payload = {
                            "focuskw": post_data.get('focus_keyphrase', '') or '',
                            "metadesc": post_data.get('meta_description', '') or '',
                            "title": post_data.get('seo_title', '') or ''
                        }
                        if primary_category_id:
                            bridge_payload["primary_category"] = primary_category_id

                        r = publisher.session.post(bridge_url, auth=auth, timeout=15, json=bridge_payload)
                        if r.status_code == 200:
                            print("✅ Yoast meta confirmed via bridge endpoint")
                        else:
                            print(f"⚠️ Yoast bridge returned {r.status_code}: {r.text}")
                    except Exception as e:
                        print(f"⚠️ Yoast bridge call failed: {e}")

                # Set image alt text
                if featured_media_id and alt_text:
                    try:
                        print("\n🖼️  Setting image alt text...")
                        media_url = f"{api_url.rstrip('/')}/wp-json/wp/v2/media/{featured_media_id}"
                        alt_response = publisher.session.post(
                            media_url, auth=auth, json={'alt_text': alt_text}, timeout=10
                        )
                        if alt_response.status_code == 200:
                            print(f"✅ Image alt text set: {alt_text}")
                        else:
                            print(f"⚠️ Alt text update returned status: {alt_response.status_code}")
                    except Exception as e:
                        print(f"⚠️ Could not set image alt text: {e}")

                # Clean link fallback
                if published_url and '?p=' in published_url:
                    base_url = api_url.rstrip('/')
                    base_url = re.sub(r'/wp-json.*$', '', base_url)
                    published_url = f"{base_url}/{slug}/"

                print("\n" + "=" * 60)
                print("✅ Successfully Published!")
                print("=" * 60)
                print(f"URL: {published_url}")
                print(f"Post ID: {post_id}")
                print("=" * 60 + "\n")

                return published_url

            # Failure
            print("\n❌ Publishing failed!")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"\n❌ WordPress publish error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def publish_ghost(api_url: str, api_key: str, post_data: Dict,
                      image_url: str = None) -> Optional[str]:
        """Publish to Ghost via Admin API"""
        try:
            import jwt
            import datetime

            def _slugify(s: str) -> str:
                s = s.lower()
                s = re.sub(r'[^a-z0-9\s-]', '', s)
                s = re.sub(r'\s+', '-', s)
                s = re.sub(r'-{2,}', '-', s)
                return s.strip('-')[:60]

            slug = _slugify(post_data['title'])

            key_parts = api_key.split(':')
            if len(key_parts) != 2:
                raise ValueError("Ghost API key must be 'id:secret'")
            key_id, key_secret = key_parts

            iat = int(datetime.datetime.now().timestamp())
            header = {'alg': 'HS256', 'typ': 'JWT', 'kid': key_id}
            payload = {'iat': iat, 'exp': iat + 5 * 60, 'aud': '/admin/'}

            token = jwt.encode(payload, bytes.fromhex(key_secret), algorithm='HS256', headers=header)

            post_url = f"{api_url}/ghost/api/admin/posts/"
            headers = {'Authorization': f'Ghost {token}', 'Content-Type': 'application/json'}

            payload = {
                'posts': [{
                    'title': post_data['title'],
                    'slug': slug,
                    'markdown': post_data['content'],
                    'status': 'published',
                    'meta_description': post_data.get('meta_description', ''),
                    'feature_image': image_url
                }]
            }

            response = requests.post(post_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['posts'][0].get('url')

        except Exception as e:
            print(f"Ghost publish error: {e}")
            return None

    @staticmethod
    def publish_custom(api_url: str, api_key: str, post_data: Dict,
                       image_url: str = None) -> Optional[str]:
        """Publish to custom REST API"""
        try:
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

            def _slugify(s: str) -> str:
                s = s.lower()
                s = re.sub(r'[^a-z0-9\s-]', '', s)
                s = re.sub(r'\s+', '-', s)
                s = re.sub(r'-{2,}', '-', s)
                return s.strip('-')[:60]

            slug = _slugify(post_data['title'])

            payload = {
                'title': post_data['title'],
                'slug': slug,
                'content': post_data['content'],
                'meta_description': post_data.get('meta_description', ''),
                'keywords': post_data.get('keywords', ''),
                'image_url': image_url,
                'category': post_data.get('category', '')
            }

            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get('url', result.get('post_url', api_url))

        except Exception as e:
            print(f"Custom API publish error: {e}")
            return None

    def publish(self, cms_type: str, api_url: str, api_key: str, post_data: Dict,
                image_url: str = None) -> Optional[str]:
        """Route to appropriate CMS publisher"""
        publishers = {
            'wordpress': self.publish_wordpress,
            'ghost': self.publish_ghost,
            'custom': self.publish_custom
        }
        publisher = publishers.get(cms_type.lower())
        if not publisher:
            print(f"Unknown CMS type: {cms_type}")
            return None
        return publisher(api_url, api_key, post_data, image_url)