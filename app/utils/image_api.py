# app/utils/image_api.py
"""
Image generation and search utilities.

Supports (in priority order):
  1. HuggingFace Inference – AI image generation (FLUX / SDXL, free tier)
  2. Pollinations.ai       – AI image generation (FLUX model, no API key, backup)
  3. Pexels                – Stock photo search (requires API key)
  4. Lexica.art            – AI image search (no API key)
  5. Unsplash Source       – Stock photo fallback (no API key)
"""

import os
import re
import time
import hashlib
import requests
from typing import Optional, List
from urllib.parse import quote

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class ImageGenerator:
    """Generate and search for blog-quality images using multiple APIs."""

    def __init__(self):
        # Read from centralized settings (loads .env via pydantic-settings)
        self.pexels_api_key = settings.PEXELS_API_KEY
        self.hf_api_key = settings.HF_API_KEY
        logger.info("ImageGenerator initialized", extra={
            "hf_configured": bool(self.hf_api_key),
            "pexels_configured": bool(self.pexels_api_key),
        })

    # ── HuggingFace Inference API (FLUX / SDXL) ──────────────────────────

    def generate_huggingface(
        self,
        prompt: str,
        model: str = "black-forest-labs/FLUX.1-schnell",
        _retried: bool = False,
    ) -> Optional[str]:
        """
        Generate an AI image using HuggingFace's free Inference API.

        Uses open-source models like FLUX.1-schnell (by Black Forest Labs)
        or Stable Diffusion XL. Requires a free HuggingFace API token.

        The generated image is saved locally and served from our own server,
        so it works reliably as a WordPress featured image.

        Args:
            prompt: Text description of the desired image.
            model:  HuggingFace model ID.

        Returns:
            Local file path (served via /static/) or None on failure.
        """
        if not self.hf_api_key:
            logger.debug("HF_API_KEY not set, skipping HuggingFace image generation")
            return None

        try:
            enhanced_prompt = self._enhance_prompt_for_blog(prompt)
            logger.info("Generating image via HuggingFace", extra={
                "model": model.split("/")[-1],
                "prompt_preview": enhanced_prompt[:60],
            })
            print(f"🎨 Generating AI image via HuggingFace ({model.split('/')[-1]})...")

            api_url = f"https://router.huggingface.co/hf-inference/models/{model}"

            response = requests.post(
                api_url,
                headers={"Authorization": f"Bearer {self.hf_api_key}"},
                json={"inputs": enhanced_prompt},
                timeout=120,
            )

            content_type = response.headers.get("content-type", "")

            if response.status_code == 200 and "image" in content_type:
                # Save to local static directory for serving
                os.makedirs("data/images", exist_ok=True)
                filename = f"ai_{hashlib.md5(prompt.encode()).hexdigest()[:12]}_{int(time.time())}.png"
                filepath = os.path.join("data", "images", filename)

                with open(filepath, "wb") as f:
                    f.write(response.content)

                # Return as local URL that our server can serve
                image_url = f"/data/images/{filename}"
                print(f"✅ AI image generated via HuggingFace ({len(response.content)} bytes)")
                logger.info("HuggingFace image generated", extra={
                    "file": filepath, "size": len(response.content),
                })
                return image_url

            # Handle model loading (retry once only)
            if response.status_code == 503 and not _retried:
                try:
                    data = response.json()
                    if "loading" in str(data.get("error", "")).lower():
                        wait = min(data.get("estimated_time", 30), 60)
                        print(f"⏳ Model loading, waiting {wait:.0f}s...")
                        time.sleep(wait)
                        return self.generate_huggingface(prompt, model, _retried=True)
                except Exception:
                    pass

            print(f"⚠️ HuggingFace returned status {response.status_code}")
            try:
                logger.warning("HuggingFace image failed", extra={"status": response.status_code, "body": response.text[:200]})
            except Exception:
                pass
            return None

        except requests.exceptions.Timeout:
            print("⚠️ HuggingFace timed out")
            return None
        except Exception as e:
            print(f"❌ HuggingFace error: {e}")
            logger.error("HuggingFace image error", extra={"error": str(e)})
            return None

    # ── Pollinations.ai (FLUX model, no API key) ─────────────────────────

    def generate_pollinations(
        self,
        prompt: str,
        width: int = 1200,
        height: int = 630,
        seed: Optional[int] = None,
        model: str = "flux",
    ) -> Optional[str]:
        """
        Generate an AI image using Pollinations.ai (100% free, no API key).

        Uses FLUX model by Black Forest Labs. Images are generated server-side
        and returned as direct URLs. May be unavailable during outages.

        Returns:
            Direct image URL or None on failure.
        """
        try:
            enhanced_prompt = self._enhance_prompt_for_blog(prompt)
            encoded_prompt = quote(enhanced_prompt, safe="")

            if seed is None:
                seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16) % 2**31

            image_url = (
                f"https://image.pollinations.ai/prompt/{encoded_prompt}"
                f"?width={width}&height={height}&seed={seed}"
                f"&model={model}&nologo=true"
            )

            print(f"🎨 Generating AI image via Pollinations ({model})...")

            response = requests.get(image_url, timeout=60, stream=True)
            content_type = response.headers.get("content-type", "")

            if response.status_code == 200 and "image" in content_type:
                print(f"✅ AI image generated via Pollinations (FLUX)")
                return image_url

            print(f"⚠️ Pollinations returned status {response.status_code}")
            return None

        except requests.exceptions.Timeout:
            print("⚠️ Pollinations timed out")
            # Return URL anyway — it may be cached and available later
            return image_url if 'image_url' in dir() else None
        except Exception as e:
            print(f"❌ Pollinations error: {e}")
            return None

    # ── Prompt enhancement ────────────────────────────────────────────────

    def _enhance_prompt_for_blog(self, raw_prompt: str) -> str:
        """
        Transform a blog title/topic into a high-quality image generation prompt.

        Blog featured images should be professional, clean, have no embedded
        text (Yoast penalises text-in-images), and be visually appealing.
        """
        # Remove common non-visual words from titles
        clean = re.sub(
            r"\b(guide|complete|ultimate|essential|how to|what is|why|"
            r"best practices|tips|tricks|step.by.step|in \d{4})\b",
            "",
            raw_prompt,
            flags=re.IGNORECASE,
        )
        clean = re.sub(r"\s{2,}", " ", clean).strip()

        prompt = (
            f"Professional high-quality blog header image about {clean}. "
            f"Modern digital illustration style, clean composition, "
            f"vibrant colors, no text overlay, no watermark, "
            f"suitable for a professional technology blog. "
            f"16:9 aspect ratio, photorealistic lighting."
        )
        return prompt

    # ── Lexica.art (AI image search) ──────────────────────────────────────

    def generate_lexica(self, prompt: str) -> Optional[str]:
        """Search for AI-generated images on Lexica.art (free, no key)."""
        try:
            clean_prompt = prompt.replace(" ", "+")
            url = f"https://lexica.art/api/v1/search?q={clean_prompt}"

            response = requests.get(url, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("images") and len(data["images"]) > 0:
                return data["images"][0]["src"]

            return None
        except Exception as e:
            print(f"Lexica API error: {e}")
            return None

    # ── Pexels (stock photos) ─────────────────────────────────────────────

    def generate_pexels(self, query: str) -> Optional[str]:
        """Search for stock photos on Pexels (free with API key)."""
        if not self.pexels_api_key:
            return None

        try:
            headers = {"Authorization": self.pexels_api_key}
            url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("photos") and len(data["photos"]) > 0:
                return data["photos"][0]["src"]["large"]

            return None
        except Exception as e:
            print(f"Pexels API error: {e}")
            return None

    # ── Unsplash Source (stock photo fallback) ────────────────────────────

    def generate_unsplash_free(self, query: str) -> Optional[str]:
        """Use Unsplash Source (no API key needed)."""
        try:
            clean_query = query.replace(" ", ",")
            image_url = f"https://source.unsplash.com/1200x630/?{clean_query}"

            response = requests.head(image_url, timeout=5)
            if response.status_code == 200:
                return image_url

            return None
        except Exception as e:
            print(f"Unsplash Source error: {e}")
            return None

    # ── Main entry point ──────────────────────────────────────────────────

    def generate_image(
        self,
        prompt: str,
        keywords: List[str] = None,
        prefer_ai: bool = True,
    ) -> Optional[str]:
        """
        Generate or find an image using multiple sources in priority order:

          1. HuggingFace (AI-generated, FLUX model, free tier)
          2. Pollinations  (AI-generated, FLUX model, no key but less reliable)
          3. Pexels (stock photos, if API key is set)
          4. Lexica (AI image search)
          5. Unsplash (stock photo fallback)

        Args:
            prompt:    Blog title or topic description.
            keywords:  Optional list of SEO keywords for better results.
            prefer_ai: If True, try AI generation first (default).

        Returns:
            Image URL or a placeholder as last resort.
        """
        if keywords:
            search_query = f"{prompt} {' '.join(keywords[:3])}"
        else:
            search_query = prompt

        # ── 1. HuggingFace AI Generation (FLUX) ──────────────────────────
        if prefer_ai and self.hf_api_key:
            image_url = self.generate_huggingface(prompt)
            if image_url:
                return image_url

        # ── 2. Pollinations AI Generation (FLUX, no key) ──────────────────
        if prefer_ai:
            image_url = self.generate_pollinations(prompt)
            if image_url:
                return image_url

        # ── 3. Pexels stock photos ────────────────────────────────────────
        if self.pexels_api_key:
            image_url = self.generate_pexels(search_query)
            if image_url:
                print(f"✅ Image found via Pexels")
                return image_url

        # ── 4. Lexica AI search ───────────────────────────────────────────
        image_url = self.generate_lexica(search_query)
        if image_url:
            print(f"✅ Image found via Lexica")
            return image_url

        # ── 5. Unsplash fallback ──────────────────────────────────────────
        image_url = self.generate_unsplash_free(search_query)
        if image_url:
            print(f"✅ Image found via Unsplash")
            return image_url

        # ── 6. Placeholder (last resort) ──────────────────────────────────
        print("⚠️ All image APIs failed, using placeholder")
        return f"https://via.placeholder.com/1200x630.png?text={search_query.replace(' ', '+')}"

    # ── Alt text helper ───────────────────────────────────────────────────

    def generate_alt_text(self, image_url: str, keyphrase: str, title: str) -> str:
        """Generate SEO-optimized alt text (max 125 chars, includes keyphrase)."""
        alt_text = f"{keyphrase} - {title}"
        if len(alt_text) > 125:
            alt_text = f"{keyphrase} illustration"
        return alt_text[:125]