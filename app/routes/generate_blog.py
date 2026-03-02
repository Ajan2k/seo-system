# app/routes/generate_blog.py
"""
Research → Generate → Optimise → Save pipeline
===============================================
Every blog post goes through 3 stages before it is persisted:

  1. Web Research  – DuckDuckGo + Google News RSS scraped for real facts,
                     current statistics, and common editorial angles.
  2. AI Generation – Groq LLaMA-3.3-70b prompt is prefixed with the
                     research context so output is factually grounded.
  3. SEO Optimisation – Multi-pass readability, keyphrase density,
                        heading coverage, and outbound link checks.
"""

from __future__ import annotations

import re
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import db
from app.utils.image_api import ImageGenerator
from app.utils.search_trends import extract_keywords_from_topic, search_trending_topics
from app.utils.seo_utils import (
    add_outbound_links,
    calculate_seo_score,
    ensure_keyphrase_in_headings,
    ensure_keyphrase_in_intro,
    fix_competing_links,
    generate_focus_keyphrase,
    generate_meta_description,
    generate_seo_title,
    generate_slug,
    limit_keyphrase_density,
    optimize_readability,
    suggest_improvements,
    validate_and_fix_meta_description,
)
from core.config import settings
from core.logging import get_logger

logger    = get_logger(__name__)
router    = APIRouter()
image_gen = ImageGenerator()


# ── Request schema ────────────────────────────────────────────────────────────

class BlogGenerateRequest(BaseModel):
    category:     str
    website_id:   Optional[int]        = None
    custom_topic: Optional[str]        = None
    target_score: int                  = 80
    focus_keyword: Optional[str]       = None
    brand_name:   Optional[str]        = "Infinitetechai"
    industries:   Optional[List[str]]  = ["healthcare", "education", "e-commerce", "real estate"]


# ── Groq API client ───────────────────────────────────────────────────────────

class GroqAPI:
    """Async Groq API client – research-grounded blog generation."""

    def __init__(self) -> None:
        import sys, os
        # Force UTF-8 on Windows to prevent cp1252 encoding crashes
        if sys.platform == "win32":
            os.environ.setdefault("PYTHONIOENCODING", "utf-8")

        self.api_key  = settings.GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        # Explicitly set UTF-8 encoding headers to avoid charmap errors on Windows
        self.client   = httpx.AsyncClient(
            timeout=settings.GROQ_TIMEOUT,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        if not self.api_key:
            logger.warning("GROQ_API_KEY not configured – generation will fail")

    async def generate_blog(
        self,
        topic:      str,
        keywords:   List[str],
        brand_name: str                  = "Infinitetechai",
        industries: Optional[List[str]]  = None,
        attempt:    int                  = 1,
        research:   Optional[object]     = None,   # ResearchContext | None
    ) -> dict:
        """
        Generate a research-grounded, SEO-optimised blog post.

        When ``research`` is provided, real facts, statistics and editorial
        angles from the web are injected into the prompt so the AI writes
        from actual sourced data instead of hallucinating numbers.
        """
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured")

        # Flatten keyword list and deduplicate
        clean_kw: List[str] = []
        for kw in keywords:
            items = [kw] if isinstance(kw, str) else (kw if isinstance(kw, list) else [])
            for item in items:
                if isinstance(item, str) and item.strip():
                    clean_kw.append(item.strip())

        primary_keyword    = clean_kw[0] if clean_kw else topic.lower()
        secondary_keywords = clean_kw[1:4] if len(clean_kw) > 1 else []
        industries         = industries or ["healthcare", "education", "e-commerce"]

        # Build research prefix block
        has_research   = bool(research and getattr(research, "has_data", False))
        research_block = research.to_prompt_block() if has_research else ""  # type: ignore[union-attr]

        if has_research:
            logger.info(
                "Research context injected into prompt",
                extra={
                    "facts":    len(getattr(research, "key_facts", [])),
                    "headings": len(getattr(research, "common_headings", [])),
                    "sources":  getattr(research, "sources", []),
                },
            )

        # Heading suggestion block from research
        heading_suggestions = ""
        if has_research and getattr(research, "common_headings", []):
            top = getattr(research, "common_headings", [])[:6]
            heading_suggestions = (
                "\n\nSUGGESTED ANGLES (from web research -- adapt freely):\n"
                + "\n".join(f"  - {h}" for h in top)
            )

        # ── Detect topic type: specific headline vs generic category ─────
        # Specific headlines typically have named entities, quotes, or are
        # news-style (e.g. "Microsoft Uncovers Whisper Leak Attack").
        # Generic topics are broader (e.g. "artificial intelligence").
        is_headline = bool(
            len(topic.split()) >= 6
            and (
                any(w[0].isupper() for w in topic.split()[1:] if w and w[0].isalpha())
                or any(c in topic for c in ["'", '"', ":", "--", "?"])
                or re.search(r'\b(uncover|reveal|announce|launch|report|study|attack|leak|breach|warn|intro)\w*', topic, re.IGNORECASE)
            )
        )

        logger.info("Topic type detected", extra={"is_headline": is_headline, "topic": topic})

        # ── Build the right prompt structure based on topic type ──────────
        if is_headline:
            # News / specific headline: content must directly cover the story
            structure_block = f"""
MANDATORY STRUCTURE (adapt headings to match the topic - do NOT use generic headings)
================================================================================

# [Write a compelling title that accurately describes: {topic}]

## Introduction  (180-220 words)
- Open with the core story/news/claim from the title
- Include "{primary_keyword}" in the first two sentences
- Briefly state what happened and why it matters{heading_suggestions}

## [Background / Context]  (220-260 words)
- Explain the background needed to understand the topic
- Define any technical terms for a general audience

## [Main Story / Analysis]  (300-350 words)
- Deep dive into the specific event, finding, or claim in the title
- Include facts, details, timeline, key players
- {"Use data from the research context above" if has_research else "Use credible sources"}

## [Impact / Implications]  (260-300 words)
- Who is affected and how?
- What does this mean for the industry?
- Short-term vs long-term implications

## [Expert Perspectives / Industry Response]  (200-250 words)
- Different viewpoints on the topic
- Industry reactions and expert opinions

## [What This Means for Businesses / Readers]  (200-250 words)
- Practical takeaways
- How businesses or individuals should respond
- Mention {brand_name} solutions naturally if relevant

## [Looking Ahead / What to Watch]  (140-170 words)
- Future developments to watch
- Upcoming milestones or decisions

## Conclusion  (130-160 words)
- Summarize the key points from the article
- What the reader should remember
- Optional CTA: "{brand_name} helps organizations navigate these changes."
"""
        else:
            # Generic / guide-style topic: use the structured template
            structure_block = f"""
MANDATORY STRUCTURE
================================================================================

# {topic}

## Introduction  (180-220 words)
- Open with a compelling hook referencing a real fact{"from the research above" if has_research else ""}
- Include "{primary_keyword}" in the first two sentences
- State what the reader will learn{heading_suggestions}

## What is {primary_keyword}?  (220-260 words)
- Precise definition, context, current relevance, key components

## Key Benefits of {primary_keyword}  (280-320 words)
- 5-7 benefits with supporting data points
- {"Cite specific figures from the research context" if has_research else "Include realistic % or $ metrics"}
- Mix bullet points with short explanatory paragraphs

## How {primary_keyword} Works  (260-300 words)
### Core Mechanism
### Step-by-Step Implementation
1. Step with detail
2. Step with detail
3. Step with detail
4. Step with detail

## Real-World Applications  (280-320 words)
### {industries[0] if industries else 'Healthcare'} - specific use-case with measurable outcome
### {industries[1] if len(industries) > 1 else 'Education'} - specific use-case with measurable outcome
### {industries[2] if len(industries) > 2 else 'Retail'} - specific use-case with measurable outcome
Mention {brand_name} solutions naturally in at least one sub-section.

## Best Practices & Expert Tips  (230-270 words)
- 6 actionable best practices (numbered)
- At least 2 expert tips attributed naturally

## Common Challenges - and How to Solve Them  (180-220 words)
- 3 challenges with practical solutions

## Future Outlook  (140-170 words)
- {"Reference forward-looking data from the research context" if has_research else "Emerging trends for the next 2-3 years"}
- Brief mention of {brand_name}'s vision

## Conclusion  (130-160 words)
- 3 key takeaways
- CTA: "Contact {brand_name} today to explore how {primary_keyword} can transform your business."
"""

        prompt = f"""{research_block}
Write a comprehensive, SEO-optimized blog post on the following topic.

CRITICAL RULE: The content MUST directly address and expand upon the given topic.
Every section of the article must be relevant to this specific topic.
Do NOT write a generic guide that ignores the title.

TOPIC: "{topic}"
PRIMARY KEYWORD: "{primary_keyword}"
SECONDARY KEYWORDS: {', '.join(secondary_keywords) if secondary_keywords else 'none'}
BRAND NAME: {brand_name}

================================================================================
CONTENT REQUIREMENTS
================================================================================

WORD COUNT:      1,700-2,000 words (strict)
KEYWORD DENSITY: 1.5-2 % for primary keyword (natural placement only)
TONE:            Conversational yet authoritative
FACTS:           {"Use ONLY statistics from the RESEARCH CONTEXT above. Do NOT invent numbers." if has_research else "Use credible industry statistics (McKinsey, Gartner, Forrester, IDC)."}

{structure_block}

================================================================================
SEO & QUALITY RULES
================================================================================

1. Every H2 must be unique and descriptive
2. At least 3 H2s must include '{primary_keyword}' or a close variant
3. Paragraphs: max 120 words; sentences: max 25 words
4. Use transition words (Furthermore, However, As a result...)
5. Include 2 outbound reference mentions (anchor text only, no bare URLs)
6. Do NOT use placeholder text like "[insert statistic]"
7. Do NOT repeat the same fact more than once
8. The H1 title MUST accurately summarize the article content
9. Write in markdown format - start immediately with # followed by the title
"""

        try:
            logger.info("Calling Groq API", extra={"attempt": attempt, "has_research": has_research})

            # Sanitize all non-ASCII chars from the prompt before sending.
            # Windows cp1252 codec cannot handle Unicode box-drawing / em-dashes,
            # so we replace known chars and fall back to '?' for everything else.
            _SUBS = [
                ("\u2501", "="), ("\u2500", "-"), ("\u2502", "|"),
                ("\u2013", "-"), ("\u2014", "--"), ("\u2019", "'"),
                ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'),
                ("\u2022", "-"), ("\u2026", "..."), ("\u2192", "->"),
                ("\u2190", "<-"), ("\u2212", "-"), ("\u00b7", "-"),
            ]
            prompt_clean = prompt
            for bad, good in _SUBS:
                prompt_clean = prompt_clean.replace(bad, good)
            prompt_clean = prompt_clean.encode("ascii", errors="replace").decode("ascii")

            # Serialize to UTF-8 bytes ourselves so httpx never re-encodes
            # through the Windows default (cp1252) codec.
            import json as _json
            _body = _json.dumps(
                {
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a senior SEO content strategist with 15+ years of experience. "
                                "You write comprehensive, factually accurate blog posts that rank on "
                                "Page 1 of Google. You NEVER invent statistics - use only data "
                                "from the research context provided, or well-known public figures. "
                                "You write in clean markdown with rich structure. "
                                "CRITICAL: Your article content MUST directly match and expand upon "
                                "the given topic/title. Never write generic filler content that "
                                "ignores the specific subject."
                            ),
                        },
                        {"role": "user", "content": prompt_clean},
                    ],
                    "temperature": 0.65,
                    "max_tokens":  settings.GROQ_MAX_TOKENS,
                    "top_p":       0.9,
                },
                ensure_ascii=True,   # ASCII-only JSON is always safe on Windows
            ).encode("utf-8")

            response = await self.client.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                content=_body,
            )

            response.raise_for_status()

            result = response.json()
            if "choices" not in result or not result["choices"]:
                raise ValueError("No content in Groq API response")

            raw_content = result["choices"][0]["message"]["content"]
            if not raw_content or len(raw_content.strip()) < 100:
                raise ValueError(f"Content too short: {len(raw_content)} chars")

            logger.info("Groq API responded", extra={
                "chars": len(raw_content),
                "words": len(raw_content.split()),
            })
            return self._parse(raw_content, topic, primary_keyword, clean_kw, brand_name)

        except httpx.TimeoutException:
            logger.error("Groq API timed out")
            raise HTTPException(status_code=504, detail="AI generation timed out – please retry")
        except httpx.HTTPStatusError as exc:
            logger.error("Groq API HTTP error", extra={"status": exc.response.status_code})
            raise HTTPException(status_code=500, detail=f"Groq API error: {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("Groq API connection error", extra={"error": str(exc)})
            raise HTTPException(status_code=500, detail=f"API connection error: {exc}")
        except HTTPException:
            raise
        except Exception:
            logger.exception("Unexpected error calling Groq API")
            raise HTTPException(status_code=500, detail="AI generation failed – see server logs")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _parse(
        self,
        raw:      str,
        topic:    str,
        kw:       str,
        all_kw:   List[str],
        brand:    str,
    ) -> dict:
        """Parse raw LLM output into structured blog data.

        The AI-generated H1 title is preferred over the input topic to ensure
        the title accurately represents the generated content.
        """
        content = raw.strip()

        # Extract H1 title from the AI-generated content (this matches what
        # the AI actually wrote, so title and content stay aligned)
        title = topic  # fallback
        m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if m:
            ai_title = m.group(1).strip()
            # Use the AI title if it's meaningful (at least 15 chars and
            # shares at least one significant word with the original topic)
            topic_words = {w.lower() for w in topic.split() if len(w) > 3}
            ai_words    = {w.lower() for w in ai_title.split() if len(w) > 3}
            overlap     = topic_words & ai_words
            if len(ai_title) >= 15 and (overlap or kw.lower() in ai_title.lower()):
                title = ai_title
                logger.info("Using AI-generated title", extra={"title": title})
            elif len(ai_title) >= 15:
                # AI title is reasonable but doesn't overlap with topic;
                # still prefer it because it matches the content that was written
                title = ai_title
                logger.warning(
                    "AI title differs from requested topic, using AI title for content alignment",
                    extra={"ai_title": ai_title, "original_topic": topic},
                )

        # Only append keyphrase suffix if it's truly missing and the title is
        # too generic (very short)
        if kw.lower() not in title.lower() and len(title) < 40:
            title = f"{title}: {kw.title()} Guide"

        meta_seed = self._first_paragraph(content)
        blog      = content

        if not re.search(r'^##\s+', content, re.MULTILINE):
            blog = self._scaffold(content, topic, kw, all_kw, brand)

        if len(blog.split()) < 800:
            logger.warning("Content too short – enhancing", extra={"words": len(blog.split())})
            blog = self._pad(blog, topic, kw, brand)

        logger.info("Blog parsed", extra={"words": len(blog.split())})
        return {"title": title, "content": blog, "meta_description": meta_seed, "keywords": all_kw}

    @staticmethod
    def _first_paragraph(content: str) -> str:
        for line in content.split("\n"):
            clean = line.strip()
            if clean and not clean.startswith("#") and len(clean) > 50:
                return re.sub(r"\s+", " ", re.sub(r"[*_`\[\]]", "", clean)).strip()
        return ""

    def _pad(self, content: str, topic: str, kw: str, brand: str) -> str:
        """Append well-structured sections when AI output is too short."""
        out = content
        if "benefit" not in content.lower():
            out += f"""

## Key Benefits of {kw}

- **Operational Efficiency** – Teams report 40–60 % reductions in manual processing time.
- **Cost Optimisation** – Lower overheads while maintaining output quality.
- **Better Decision-Making** – Real-time data surfaces actionable insights faster.
- **Competitive Advantage** – Early adopters consistently out-perform laggards.
- **Scalability** – Grow capacity without proportional headcount increases.
- **Improved ROI** – Deployments typically break even within 12–18 months.

{brand} has helped organisations across sectors achieve these outcomes.
"""
        if "implementation" not in content.lower():
            out += f"""

## How to Implement {kw} Successfully

1. **Discovery & Assessment** – Audit current processes; identify pain points.
2. **Strategy & Planning** – Define KPIs and align stakeholders.
3. **Pilot Deployment** – Run a controlled proof-of-concept.
4. **Full Rollout** – Scale based on validated pilot learnings.
5. **Continuous Optimisation** – Measure, iterate, and improve monthly.

{brand} provides expert guidance at every stage.
"""
        if "challenge" not in content.lower():
            out += f"""

## Common Challenges and How to Overcome Them

**Resistance to Change** – Invest in change management and early buy-in.
**Data Quality Issues** – Establish governance policies before deployment.
**Budget Constraints** – Start with a focused pilot that proves ROI, then expand.
"""
        if "conclusion" not in content.lower():
            out += f"""

## Conclusion

{kw} delivers measurable results for organisations that adopt it strategically.
{brand} has the expertise, technology, and track record to help you succeed.

**Ready to take the next step?** Contact {brand} today to schedule a free consultation.
"""
        return out

    def _scaffold(self, content: str, topic: str, kw: str, kws: List[str], brand: str) -> str:
        """Wrap unstructured text in a heading skeleton."""
        paras = [p.strip() for p in content.split("\n\n") if p.strip() and not p.startswith("#")]
        if len(paras) < 3:
            return self._fallback(topic, kw, kws, brand)

        out = f"# {topic}\n\n"
        sections = [
            ("## Introduction",            paras[0]),
            (f"## What is {kw}?",          paras[1] if len(paras) > 1 else f"{kw} is transformative."),
            (f"## Benefits of {kw}",       "- Efficiency\n- Cost savings\n- Better outcomes"),
            ("## How It Works",            "1. Assess\n2. Plan\n3. Deploy\n4. Optimise"),
            ("## Best Practices",          paras[2] if len(paras) > 2 else f"Follow proven frameworks."),
            ("## Industry Applications",   f"### Healthcare\n### Education\n### Retail"),
            ("## Conclusion",              f"Contact {brand} to begin your {kw} journey today."),
        ]
        for heading, body in sections:
            out += f"{heading}\n\n{body}\n\n"
        return out

    @staticmethod
    def _fallback(topic: str, kw: str, kws: List[str], brand: str) -> str:
        """Emergency scaffold when API content is unusable."""
        return f"""# {topic}

## Introduction

{kw} is reshaping how organisations operate. This guide covers definitions,
benefits, implementation steps, and real-world applications.

## What is {kw}?

{kw} refers to a systematic approach to optimising organisational performance
through technology and strategy.

## Key Benefits of {kw}

- 40–60 % operational efficiency gains
- 30–50 % cost reductions
- Faster time-to-market

## How {kw} Works

1. Assess – evaluate current state
2. Design – architect the solution
3. Implement – deploy iteratively
4. Optimise – measure and improve

## Industry Applications

### Healthcare
Reduced admin overhead by 40 % in pilot programmes.

### Education
50 % improvement in student engagement metrics.

### Retail
55 % higher conversion rates through personalisation.

## Best Practices

1. Start with clear objectives.
2. Secure executive sponsorship.
3. Pilot before scaling.
4. Monitor KPIs from day one.

## Conclusion

{kw} is a high-ROI investment. Contact {brand} to start your journey today.
"""


groq_api = GroqAPI()


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_keywords(keywords: list) -> List[str]:
    """Return a flat, unique, lowercase list of keyword strings."""
    seen:   set       = set()
    result: List[str] = []
    for kw in keywords:
        items = [kw] if isinstance(kw, str) else (kw if isinstance(kw, list) else [])
        for item in items:
            if isinstance(item, str):
                k = item.strip().lower()
                if k and k not in seen:
                    seen.add(k)
                    result.append(k)
    return result


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_blog(request: BlogGenerateRequest):
    """
    Main blog generation endpoint.

    Pipeline:
      1. Resolve topic & keywords
      2. Web research (DuckDuckGo + Google News RSS  →  real facts & stats)
      3. AI generation with research grounding (up to 3 attempts)
      4. Multi-pass SEO optimisation
      5. Image fetching
      6. Database persistence
    """
    # Local import avoids any circular dependency
    from app.utils.web_researcher import research_topic

    try:
        logger.info(
            "Blog generation started",
            extra={"category": request.category, "custom_topic": request.custom_topic},
        )

        # ── 1. Topic & keywords ───────────────────────────────────────────
        if request.custom_topic:
            topic    = request.custom_topic.strip()
            keywords = extract_keywords_from_topic(topic)
        else:
            trending = search_trending_topics(request.category, count=1)
            topic    = trending[0] if trending else f"Complete Guide to {request.category}"
            keywords = extract_keywords_from_topic(topic)

        keywords = clean_keywords(keywords)[:7]

        # ── 2. Focus keyphrase ────────────────────────────────────────────
        if request.focus_keyword:
            focus = request.focus_keyword.strip().lower()
        else:
            focus = generate_focus_keyphrase(keywords, topic)

        if request.website_id and await db.is_keyphrase_used(focus, request.website_id):
            logger.warning("Keyphrase already used – appending category", extra={"keyphrase": focus})
            focus = f"{focus} {request.category}".strip()

        logger.info("Topic & keyphrase resolved", extra={
            "topic": topic, "keyphrase": focus, "keywords": keywords[:5],
        })

        # ── 3. Web Research ───────────────────────────────────────────────
        research = None
        try:
            research = await research_topic(
                topic=topic, keyphrase=focus, category=request.category,
            )
            logger.info("Web research complete", extra={
                "articles": len(research.articles),
                "facts":    len(research.key_facts),
                "sources":  research.sources,
            })
        except Exception as exc:
            # Research is non-fatal – generation continues without it
            logger.warning(
                "Web research failed – proceeding without research context",
                extra={"error": str(exc)},
            )

        # ── 4. AI Generation loop (up to 3 attempts) ─────────────────────
        max_attempts = 3
        best_post: dict | None = None
        best_score = 0

        for attempt in range(max_attempts):
            logger.info("Generation attempt", extra={"attempt": attempt + 1, "of": max_attempts})
            try:
                blog_data = await groq_api.generate_blog(
                    topic=topic,
                    keywords=[focus] + keywords,
                    brand_name=request.brand_name,
                    industries=request.industries,
                    attempt=attempt + 1,
                    research=research,
                )

                if not blog_data.get("content") or len(blog_data["content"].strip()) < 500:
                    logger.warning("Content too short – retrying", extra={"attempt": attempt + 1})
                    continue

                # ── 5. SEO optimisation ───────────────────────────────────
                try:
                    blog_data["content"] = optimize_readability(
                        content=blog_data["content"], title=blog_data["title"],
                        focus_keyphrase=focus, min_transition_percent=30.0,
                        max_paragraph_words=150, max_sentence_words=20,
                        max_long_sentence_ratio=0.25, subheading_gap=250,
                    )
                    blog_data["content"] = ensure_keyphrase_in_intro(
                        content=blog_data["content"], focus_keyphrase=focus,
                        variants=blog_data.get("synonyms", []), bold=True,
                    )
                    blog_data["content"] = ensure_keyphrase_in_headings(
                        content=blog_data["content"], keyphrase=focus,
                        synonyms=blog_data.get("synonyms", []),
                        target_ratio=0.5, max_changes=3,
                    )
                    blog_data["content"] = limit_keyphrase_density(
                        content=blog_data["content"], keyphrase=focus,
                        target_min=1.0, target_max=1.6, hard_cap=38,
                    )
                    blog_data["content"] = fix_competing_links(
                        content=blog_data["content"], keyphrase=focus,
                        synonyms=blog_data.get("synonyms", []),
                    )
                    blog_data["content"] = add_outbound_links(
                        content=blog_data["content"], keywords=keywords,
                        topic=topic, max_links=3, avoid_anchor_terms=[focus],
                    )
                except Exception as opt_exc:
                    logger.warning("SEO optimisation step failed – continuing", extra={"error": str(opt_exc)})

                # Run intro injection again after optimisation (idempotent)
                blog_data["content"] = ensure_keyphrase_in_intro(blog_data["content"], focus)

                # ── 6. SEO metadata ───────────────────────────────────────
                seo_title = generate_seo_title(blog_data["title"], focus)
                blog_data["seo_title"] = seo_title

                raw_meta = blog_data.get("meta_description") or blog_data.get("content", "")
                meta = generate_meta_description(content=raw_meta, keyphrase=focus)
                blog_data["meta_description"] = meta

                slug = generate_slug(blog_data["title"], focus)
                blog_data["slug"] = slug

                # ── 7. SEO score ──────────────────────────────────────────
                seo_details   = calculate_seo_score(
                    title=seo_title, content=blog_data["content"],
                    keywords=keywords, meta_description=meta, focus_keyphrase=focus,
                )
                current_score = seo_details["total_score"]

                logger.info("SEO score", extra={
                    "attempt":    attempt + 1,
                    "score":      current_score,
                    "target":     request.target_score,
                    "word_count": len(blog_data["content"].split()),
                    "meta_len":   len(meta),
                })

                if current_score > best_score:
                    best_score = current_score
                    best_post  = {
                        **blog_data,
                        "seo_details":     seo_details,
                        "keywords":        keywords,
                        "focus_keyphrase": focus,
                    }

                if current_score >= request.target_score:
                    logger.info("Target SEO score achieved", extra={"score": current_score})
                    break

            except HTTPException:
                raise
            except Exception as attempt_exc:
                logger.error("Attempt failed", extra={"attempt": attempt + 1, "error": str(attempt_exc)})
                if attempt == max_attempts - 1:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Generation failed after {max_attempts} attempts: {attempt_exc}",
                    )

        # ── 8. Require content ────────────────────────────────────────────
        if not best_post:
            raise HTTPException(
                status_code=503,
                detail="Failed to generate content. Check GROQ_API_KEY and retry.",
            )

        final       = best_post
        final_score = final["seo_details"]["total_score"]

        # ── 9. Featured image ─────────────────────────────────────────────
        image_url = None
        try:
            image_url = image_gen.generate_image(
                prompt=final["title"], keywords=[focus] + keywords,
            )
            logger.info("Featured image fetched", extra={"url": image_url})
        except Exception as img_exc:
            logger.warning("Image fetch failed – post saved without image",
                           extra={"error": str(img_exc)})

        # ── 10. Persist ───────────────────────────────────────────────────
        post_id = await db.add_post(
            title            = final["title"],
            slug             = final.get("slug", ""),
            content          = final["content"],
            meta_description = final["meta_description"],
            keywords         = ",".join(keywords),
            category         = request.category,
            focus_keyphrase  = focus,
            seo_title        = final["seo_title"],
            website_id       = request.website_id,
            image_url        = image_url,
            seo_score        = final_score,
        )

        suggestions      = suggest_improvements(final["seo_details"])
        ready_to_publish = final_score >= 80

        logger.info("Blog generation complete", extra={
            "post_id":          post_id,
            "seo_score":        final_score,
            "word_count":       len(final["content"].split()),
            "research_sources": research.sources if research else [],
            "ready":            ready_to_publish,
        })

        return {
            "success":          True,
            "post_id":          post_id,
            "title":            final["title"],
            "seo_title":        final["seo_title"],
            "slug":             final["slug"],
            "content":          final["content"],
            "meta_description": final["meta_description"],
            "keywords":         keywords,
            "focus_keyphrase":  focus,
            "seo_score":        final_score,
            "seo_details":      final["seo_details"],
            "suggestions":      suggestions,
            "image_url":        image_url,
            "ready_to_publish": ready_to_publish,
            "word_count":       len(final["content"].split()),
            "research_sources": research.sources if research else [],
        }

    except HTTPException:
        raise  # already formatted; don't double-wrap
    except Exception:
        logger.exception("Unhandled error in generate_blog",
                         extra={"category": request.category})
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during blog generation. Please try again.",
        )


@router.get("/trending/{category}")
async def get_trending_topics(category: str, count: int = 5):
    """Return trending topics for a given category from Google News & DuckDuckGo."""
    try:
        topics = search_trending_topics(category, count)
        return {"success": True, "topics": topics, "count": len(topics)}
    except Exception as exc:
        logger.error("Trending topics fetch failed", extra={"category": category, "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/regenerate/{post_id}")
async def regenerate_for_better_seo(post_id: int):
    """
    Re-run the full Research → Generate pipeline for an existing post
    that scored below 80. A new post is created (old post preserved).
    """
    try:
        post = await db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail=f"Post {post_id} not found")

        current_score = post.get("seo_score", 0)
        if current_score >= 80:
            return {
                "success":       True,
                "message":       "Post already has a good SEO score (≥80) – no regeneration needed",
                "current_score": current_score,
            }

        req    = BlogGenerateRequest(
            category    = post["category"],
            custom_topic = post["title"],
            target_score = 80,
            website_id  = post.get("website_id"),
        )
        result = await generate_blog(req)

        logger.info("Post regenerated", extra={
            "post_id":     post_id,
            "old_score":   current_score,
            "new_score":   result["seo_score"],
            "new_post_id": result["post_id"],
        })

        return {
            "success":     True,
            "old_score":   current_score,
            "new_score":   result["seo_score"],
            "improvement": result["seo_score"] - current_score,
            "new_post_id": result["post_id"],
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Regeneration failed", extra={"post_id": post_id})
        raise HTTPException(status_code=500, detail="Regeneration failed – see server logs")