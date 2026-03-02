# app/utils/web_researcher.py
"""
Web Research Engine for AI Blog Automation
==========================================
Searches the web for real, current information about a topic BEFORE
calling the AI, so generated content is:

  - Factually grounded (real stats, not hallucinated numbers)
  - Up-to-date (current year events and trends)
  - Topically relevant (based on what actually ranks / appears in news)

Search strategy (tried in priority order, stops when we have enough data):
  1. SerpAPI            – if SERP_API_KEY is set → most reliable
  2. Google News RSS    – always free, good for recent news
  3. Bing HTML search   – free, moderately scrapeable
  4. Wikipedia summary  – always works; good for definitions & background

Scraping strategy:
  - Fetches up to MAX_PAGES_TO_SCRAPE of the collected URLs
  - Extracts headings (H2/H3), paragraph text, and stat sentences
  - Returns a ResearchContext with a `.to_prompt_block()` method ready
    to prepend to the Groq prompt
"""

from __future__ import annotations

import asyncio
import json
import re
import random
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from core.config  import settings
from core.logging import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_CONTENT_PER_PAGE = 3_000   # chars kept per scraped page
MAX_PAGES_TO_SCRAPE  = 4       # how many URLs to read full content from
REQUEST_TIMEOUT      = 12      # seconds per HTTP request
SEARCH_DELAY         = 0.6     # polite delay between requests (seconds)

BLOCKED_DOMAINS: set[str] = {
    "youtube.com", "youtu.be", "reddit.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "linkedin.com", "pinterest.com",
    "tiktok.com", "quora.com", "amazon.com", "ebay.com",
    "play.google.com", "apps.apple.com", "accounts.google.com",
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ScrapedArticle:
    """Content extracted from a single webpage."""
    url:           str
    title:         str
    content:       str         # plain-text body
    facts:         List[str]   # sentences with numbers / % / $
    headings:      List[str]   # H2 / H3 heading text
    word_count:    int = 0
    source_domain: str = ""

    def __post_init__(self) -> None:
        self.word_count    = len(self.content.split())
        parsed             = urlparse(self.url)
        self.source_domain = parsed.netloc.replace("www.", "").lower()


@dataclass
class ResearchContext:
    """Aggregated web research ready to inject into the AI generation prompt."""
    topic:           str
    keyphrase:       str
    articles:        List[ScrapedArticle] = field(default_factory=list)
    key_facts:       List[str]            = field(default_factory=list)
    common_headings: List[str]            = field(default_factory=list)
    sources:         List[str]            = field(default_factory=list)
    search_queries:  List[str]            = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return bool(self.articles)

    def to_prompt_block(self) -> str:
        """
        Returns a formatted block that is prepended to the AI prompt.
        The AI is explicitly instructed to use these facts and cite
        sources naturally rather than inventing statistics.
        """
        if not self.has_data:
            return ""

        lines = [
            "=== WEB RESEARCH CONTEXT (current, real-world data) ===",
            f"Topic:            {self.topic}",
            f"Focus keyphrase:  {self.keyphrase}",
            f"Sources checked:  {', '.join(self.sources[:6])}",
            "",
        ]

        if self.key_facts:
            lines.append("KEY FACTS & STATISTICS (use these; cite sources naturally):")
            for i, fact in enumerate(self.key_facts[:18], 1):
                lines.append(f"  {i}. {fact.strip()}")
            lines.append("")

        if self.common_headings:
            lines.append("SECTION ANGLES FOUND IN TOP-RANKING ARTICLES (incorporate these):")
            for h in self.common_headings[:12]:
                lines.append(f"  - {h}")
            lines.append("")

        for i, art in enumerate(self.articles[:3], 1):
            lines.append(f"SOURCE {i}: {art.source_domain}")
            lines.append(f"Title:   {art.title}")
            snippet = art.content[:500].replace("\n", " ").strip()
            if snippet:
                lines.append(f"Excerpt: {snippet}...")
            lines.append("")

        lines += [
            "=== END OF RESEARCH CONTEXT ===",
            "",
            "IMPORTANT INSTRUCTIONS FOR THE AI:",
            "  • Use the statistics and facts listed above in your article.",
            "  • Do NOT invent or fabricate any numbers.",
            "  • Cite sources naturally, e.g. 'According to [source]...'",
            "  • Build on the above angles but write original, comprehensive content.",
            "",
        ]
        return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

async def research_topic(
    topic:     str,
    keyphrase: str,
    category:  str = "",
) -> ResearchContext:
    """
    Orchestrate web research for ``topic`` + ``keyphrase``.

    Priority order (earlier sources are more reliable):
      1. Wikipedia – always works; great for definitions & background
      2. SerpAPI   – if SERPAPI_API_KEY is configured
      3. Google News RSS – free, no key needed
      4. Bing HTML – free, no key needed (less reliable in restricted envs)

    Research failure is non-fatal: generation continues without context.
    """
    ctx              = ResearchContext(topic=topic, keyphrase=keyphrase)
    queries          = _build_queries(topic, keyphrase, category)
    ctx.search_queries = queries

    logger.info("Starting web research",
                extra={"topic": topic, "keyphrase": keyphrase, "queries": queries})

    collected_urls: List[str] = []

    async with httpx.AsyncClient(
        headers          = _browser_headers(),
        timeout          = REQUEST_TIMEOUT,
        follow_redirects = True,
    ) as client:

        # ── 1. Wikipedia (Always works) ───────────────────────────────────
        for search_term in [keyphrase, topic, category]:
            if search_term:
                wiki_url = _wikipedia_url(search_term)
                if wiki_url not in collected_urls:
                    collected_urls.append(wiki_url)

        # ── 2. SerpAPI (if key configured) ───────────────────────────────
        serp_key = getattr(settings, "SERPAPI_API_KEY", "") or getattr(settings, "SERP_API_KEY", "")
        if serp_key:
            for q in queries[:2]:
                urls = await _search_serpapi(client, q, serp_key)
                collected_urls.extend(u for u in urls if u not in collected_urls)
                if len(collected_urls) >= MAX_PAGES_TO_SCRAPE * 2:
                    break
                await asyncio.sleep(SEARCH_DELAY)

        # ── 3. Google News RSS ────────────────────────────────────────────
        if len(collected_urls) < MAX_PAGES_TO_SCRAPE:
            for q in [keyphrase or topic, f"{topic} {category}".strip()]:
                urls = await _google_news_rss(client, q)
                collected_urls.extend(u for u in urls if u not in collected_urls)
                await asyncio.sleep(SEARCH_DELAY)

        # ── 4. Bing HTML ──────────────────────────────────────────────────
        if len(collected_urls) < MAX_PAGES_TO_SCRAPE:
            for q in queries[:2]:
                urls = await _search_bing(client, q)
                collected_urls.extend(u for u in urls if u not in collected_urls)
                await asyncio.sleep(SEARCH_DELAY)

        # Filter and cap
        collected_urls = _filter_urls(collected_urls)[:MAX_PAGES_TO_SCRAPE * 2]

        # ── Scrape pages ──────────────────────────────────────────────────
        scraped: List[ScrapedArticle] = []
        for url in collected_urls[:MAX_PAGES_TO_SCRAPE]:
            article = await _scrape_page(client, url)
            if article and article.word_count >= 80:
                scraped.append(article)
            await asyncio.sleep(SEARCH_DELAY)

    ctx.articles = scraped
    ctx.sources  = list({a.source_domain for a in scraped})

    all_facts    = [f for art in scraped for f in art.facts]
    all_headings = [h for art in scraped for h in art.headings]

    ctx.key_facts       = _deduplicate(all_facts)[:20]
    ctx.common_headings = _deduplicate(all_headings)[:15]

    logger.info("Web research finished", extra={
        "articles": len(scraped),
        "facts":    len(ctx.key_facts),
        "headings": len(ctx.common_headings),
        "sources":  ctx.sources,
    })
    return ctx


# ── Search adapters ───────────────────────────────────────────────────────────

async def _search_serpapi(
    client:  httpx.AsyncClient,
    query:   str,
    api_key: str,
) -> List[str]:
    """SerpAPI Google search results (most reliable)."""
    try:
        r = await client.get(
            "https://serpapi.com/search",
            params={
                "q":       query,
                "api_key": api_key,
                "engine":  "google",
                "num":     10,
                "hl":      "en",
                "gl":      "us",
            },
        )
        r.raise_for_status()
        data = r.json()
        urls = [res.get("link", "") for res in data.get("organic_results", [])]
        logger.debug("SerpAPI search", extra={"query": query, "urls": len(urls)})
        return [u for u in urls if u.startswith("http")]
    except Exception as exc:
        logger.warning("SerpAPI failed", extra={"query": query, "error": str(exc)})
        return []


async def _google_news_rss(client: httpx.AsyncClient, query: str) -> List[str]:
    """Google News RSS – free, no key, constantly updated."""
    try:
        encoded = quote_plus(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        r   = await client.get(url)
        r.raise_for_status()

        # Parse as XML
        soup  = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        urls  = []
        for item in items[:12]:
            link_tag = item.find("link")
            if link_tag:
                # Google News wraps article links; the <link> text is the real URL
                link_text = link_tag.text.strip() if link_tag.text else ""
                if link_text.startswith("http"):
                    urls.append(link_text)

        logger.debug("Google News RSS", extra={"query": query, "urls": len(urls)})
        return urls
    except Exception as exc:
        logger.warning("Google News RSS failed", extra={"query": query, "error": str(exc)})
        return []


async def _search_bing(client: httpx.AsyncClient, query: str) -> List[str]:
    """
    Bing HTML search (free, no API key).
    Bing is less aggressive than Google/DDG about blocking scrapers.
    """
    try:
        encoded = quote_plus(query)
        url     = f"https://www.bing.com/search?q={encoded}&count=10&form=QBLH"
        r       = await client.get(url)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        urls: List[str] = []

        # Bing results are in <li class="b_algo"> → <h2> → <a href="...">
        for li in soup.select("li.b_algo"):
            a = li.find("a", href=True)
            if a and a["href"].startswith("http"):
                urls.append(a["href"])

        logger.debug("Bing search", extra={"query": query, "urls": len(urls)})
        return urls
    except Exception as exc:
        logger.warning("Bing search failed", extra={"query": query, "error": str(exc)})
        return []


def _wikipedia_url(topic: str) -> str:
    """Construct a Wikipedia article URL for the topic."""
    slug = "_".join(topic.strip().title().split())
    return f"https://en.wikipedia.org/wiki/{quote_plus(slug)}"


# ── Page scraper ──────────────────────────────────────────────────────────────

async def _scrape_page(client: httpx.AsyncClient, url: str) -> Optional[ScrapedArticle]:
    """
    Download a page and extract:
      - readable body text (paragraphs / list items)
      - sentences with statistics (numbers, %, $, year references)
      - H2 / H3 headings
    Returns None on any non-recoverable error.
    """
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return None
        if "text/html" not in r.headers.get("content-type", ""):
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # Remove boilerplate
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "noscript", "iframe", "svg",
                         "figure", "figcaption", "button"]):
            tag.decompose()

        # Title
        page_title = (
            soup.find("title").get_text(strip=True)
            if soup.find("title") else urlparse(url).netloc
        )

        # Headings
        headings: List[str] = []
        for h in soup.find_all(["h2", "h3"]):
            text = h.get_text(strip=True)
            if 5 < len(text) < 120:
                headings.append(text)

        # Main content
        main_el = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_=re.compile(r"(content|post|article|entry|blog)", re.I))
            or soup.body
        )
        if not main_el:
            return None

        parts: List[str] = []
        for elem in main_el.find_all(["p", "li"]):
            t = elem.get_text(separator=" ", strip=True)
            if len(t) > 40:
                parts.append(t)

        full_text = " ".join(parts)[:MAX_CONTENT_PER_PAGE]

        # Extract stat/fact sentences
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        stat_pattern = re.compile(
            r'\b(\d[\d,\.]*\s*(%|percent|billion|million|thousand|\$|USD|€|£|GB|TB|ms|seconds?|minutes?|hours?|years?|x faster|times faster)|\b20[12]\d\b)',
            re.I,
        )
        facts: List[str] = []
        for s in sentences:
            if stat_pattern.search(s):
                c = s.strip()
                if 30 < len(c) < 300:
                    facts.append(c)

        return ScrapedArticle(
            url      = url,
            title    = page_title,
            content  = full_text,
            facts    = facts[:12],
            headings = headings[:10],
        )

    except Exception as exc:
        logger.debug("Scrape failed", extra={"url": url[:60], "error": str(exc)})
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_queries(topic: str, keyphrase: str, category: str) -> List[str]:
    """Return 3–4 diverse search queries to maximise research coverage."""
    from datetime import datetime
    year = datetime.now().year

    queries: List[str] = []
    if keyphrase:
        queries.append(f"{keyphrase} {year}")
        queries.append(f"{topic} complete guide {year}")
    else:
        queries.append(f"{topic} {year}")
        queries.append(f"what is {topic}")

    if category and category.lower() not in topic.lower():
        queries.append(f"{keyphrase or topic} {category}")

    queries.append(f"{topic} statistics facts benefits")
    return queries[:4]


def _filter_urls(urls: List[str]) -> List[str]:
    """Deduplicate and remove blocked domains."""
    seen:  set       = set()
    clean: List[str] = []
    for url in urls:
        if not url.startswith("http"):
            continue
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").lower()
        if domain in BLOCKED_DOMAINS:
            continue
        norm = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if norm in seen:
            continue
        seen.add(norm)
        clean.append(url)
    return clean


def _deduplicate(items: List[str]) -> List[str]:
    """Remove near-duplicate strings (matched by first 60 chars)."""
    seen:   set       = set()
    result: List[str] = []
    for s in items:
        key = s[:60].lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(s)
    return result


def _browser_headers() -> dict:
    """Return randomised browser-like HTTP headers."""
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    return {
        "User-Agent":      random.choice(agents),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT":             "1",
        "Connection":      "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
