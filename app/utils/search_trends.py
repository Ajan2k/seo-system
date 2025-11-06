import os
import requests
import feedparser
import random
import hashlib
import re
from typing import List, Set
from datetime import datetime

def search_trending_topics(category: str, count: int = 5, exclude_topics: List[str] = None) -> List[str]:
    """
    Search for trending topics with uniqueness guarantee
    Returns a list of unique trending topic titles
    """
    topics: List[str] = []
    seen: Set[str] = set()
    exclude_topics = exclude_topics or []
    
    # Normalize excluded topics for comparison
    excluded_normalized = {normalize_topic(t) for t in exclude_topics if t}
    
    print(f"🔍 Searching for topics in category: {category}")
    print(f"📋 Excluding {len(excluded_normalized)} previously used topics")
    
    def add_title(title: str):
        if not title:
            return False
        
        t = str(title).strip()
        normalized = normalize_topic(t)
        
        # Skip if already seen or excluded
        if t and normalized and normalized not in seen and normalized not in excluded_normalized:
            seen.add(normalized)
            topics.append(t)
            return True
        return False
    
    # Use a session and ignore system proxies
    session = requests.Session()
    session.trust_env = False
    
    # Method 0: SerpAPI (if available)
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if serpapi_key and len(topics) < count * 3:
        try:
            print("🔎 Trying SerpAPI...")
            params_news = {
                "engine": "google_news",
                "q": category,
                "gl": "us",
                "hl": "en",
                "api_key": serpapi_key,
            }
            r = session.get("https://serpapi.com/search.json", params=params_news, timeout=10)
            r.raise_for_status()
            data = r.json()
            news = data.get("news_results", []) or []
            for item in news:
                add_title(item.get("title"))
            
            # Google search for trends
            params_google = {
                "engine": "google",
                "q": f"{category} trends {datetime.now().year}",
                "gl": "us",
                "hl": "en",
                "api_key": serpapi_key,
            }
            r2 = session.get("https://serpapi.com/search.json", params=params_google, timeout=10)
            r2.raise_for_status()
            data2 = r2.json()
            for item in data2.get("organic_results", []) or []:
                add_title(item.get("title"))
            
            print(f"✅ Found {len(topics)} topics from SerpAPI")
        except Exception as e:
            print(f"⚠️ SerpAPI error: {e}")
    
    # Method 1: Google News RSS fallback
    if len(topics) < count * 3:
        try:
            print("🔎 Trying Google News RSS...")
            rss_url = f"https://news.google.com/rss/search?q={category.replace(' ', '+')}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                add_title(getattr(entry, "title", ""))
            print(f"✅ Total topics now: {len(topics)}")
        except Exception as e:
            print(f"⚠️ Google News RSS error: {e}")
    
    # Method 2: DuckDuckGo fallback
    if len(topics) < count * 3:
        try:
            print("🔎 Trying DuckDuckGo...")
            ddg_url = "https://api.duckduckgo.com/"
            params = {"q": f"{category} latest", "format": "json"}
            r = session.get(ddg_url, params=params, timeout=5)
            r.raise_for_status()
            data = r.json()
            for topic in data.get("RelatedTopics", []) or []:
                if isinstance(topic, dict) and topic.get("Text"):
                    add_title(topic["Text"].split(" - ")[0])
            print(f"✅ Total topics now: {len(topics)}")
        except Exception as e:
            print(f"⚠️ DuckDuckGo error: {e}")
    
    # Generate unique variations
    print(f"🎲 Generating unique topic variations...")
    variations = generate_unique_topic_variations(category, count * 5, excluded_normalized)
    for variation in variations:
        add_title(variation)
    
    print(f"✅ Total unique topics found: {len(topics)}")
    
    # Shuffle to randomize selection
    random.shuffle(topics)
    
    return topics[:count * 2]  # Return more than requested


def generate_unique_topic_variations(category: str, count: int = 20, exclude: Set[str] = None) -> List[str]:
    """Generate unique topic variations for a category"""
    
    exclude = exclude or set()
    current_year = datetime.now().year
    
    templates = []
    
    # Simple template groups (no nested list comprehensions)
    templates.extend([
        f"How to Get Started with {category} in {current_year}",
        f"How to Master {category}: Complete Guide",
        f"How to Implement {category} Successfully",
        f"How to Choose the Right {category} Solution",
        f"How to Optimize Your {category} Strategy",
        f"How {category} Works: A Step-by-Step Guide",
        f"How to Scale {category} for Your Business",
        f"How to Measure {category} Success",
        f"How to Integrate {category} into Your Business",
        f"How to Build a {category} Strategy from Scratch",
    ])
    
    templates.extend([
        f"The Ultimate {category} Guide for {current_year}",
        f"The Complete {category} Resource",
        f"The Definitive {category} Guide",
        f"The Essential {category} Handbook",
        f"The Comprehensive {category} Manual",
        f"{category}: The Ultimate Resource",
        f"Everything You Need to Know About {category}",
        f"The Only {category} Guide You'll Ever Need",
        f"The {current_year} {category} Bible",
        f"Complete {category} Training",
    ])
    
    templates.extend([
        f"Best Practices for {category} in {current_year}",
        f"{category} Best Practices Every Professional Should Know",
        f"Top {category} Strategies",
        f"Proven {category} Techniques for Success",
        f"{category}: Expert Tips and Best Practices",
        f"Advanced {category} Best Practices",
        f"{category} Best Practices for Beginners",
        f"Industry Best Practices in {category}",
        f"Modern {category} Best Practices",
        f"Essential {category} Best Practices",
    ])
    
    templates.extend([
        f"Top {category} Trends in {current_year}",
        f"Future of {category}: What to Expect",
        f"Emerging {category} Trends",
        f"{category} Trends Shaping {current_year}",
        f"The Evolution of {category}",
        f"{category} Innovation in {current_year}",
        f"Next-Generation {category} Solutions",
        f"Revolutionary {category} Approaches",
        f"{category} Trends You Can't Ignore",
        f"The Changing Landscape of {category}",
    ])
    
    templates.extend([
        f"Comparing Top {category} Solutions",
        f"{category} vs Traditional Approaches",
        f"Understanding Different {category} Methods",
        f"Which {category} Solution is Best?",
        f"{category} Tools Comparison",
        f"Evaluating {category} Platforms",
        f"Top {category} Solutions",
        f"{category} Vendor Comparison Guide",
        f"Choosing Between {category} Options",
        f"Best {category} Tools",
    ])
    
    templates.extend([
        f"Mastering {category}",
        f"Understanding {category}",
        f"Implementing {category}",
        f"Leveraging {category} for Success",
        f"Optimizing {category}",
        f"Maximizing {category} Benefits",
        f"Building with {category}",
        f"Creating {category} Solutions",
        f"Developing {category} Strategies",
        f"Scaling {category}",
        f"Transforming Business with {category}",
        f"Revolutionizing {category}",
    ])
    
    templates.extend([
        f"{category} for Healthcare",
        f"{category} for Education",
        f"{category} for E-commerce",
        f"{category} for Manufacturing",
        f"{category} for Finance",
        f"{category} for Real Estate",
        f"{category} for Retail",
        f"{category} for Technology Companies",
        f"{category} for Small Businesses",
        f"{category} for Enterprises",
        f"How Healthcare Uses {category}",
        f"How Education Benefits from {category}",
    ])
    
    templates.extend([
        f"The Business Benefits of {category}",
        f"ROI of {category} Implementation",
        f"Why Your Business Needs {category}",
        f"The Value of {category}",
        f"{category} Benefits",
        f"Maximizing ROI with {category}",
        f"Cost-Benefit Analysis of {category}",
        f"The Impact of {category}",
        f"Measuring {category} Value",
        f"{category} Returns on Investment",
    ])
    
    templates.extend([
        f"Overcoming {category} Challenges",
        f"Common {category} Mistakes and How to Avoid Them",
        f"Solving {category} Implementation Issues",
        f"{category} Challenges",
        f"Troubleshooting {category} Problems",
        f"Addressing {category} Roadblocks",
        f"{category} Solutions to Common Problems",
        f"Fixing {category} Issues: A Practical Guide",
        f"{category} Problem-Solving Guide",
        f"Navigating {category} Obstacles",
    ])
    
    templates.extend([
        f"Getting Started with {category}",
        f"{category} for Absolute Beginners",
        f"Your First Steps in {category}",
        f"Introduction to {category}",
        f"{category} Basics: Where to Start",
        f"Starting Your {category} Journey",
        f"Beginner's {category} Roadmap",
        f"{category} 101: The Fundamentals",
        f"{category} Quick Start Guide",
        f"Learn {category} from Scratch",
    ])
    
    templates.extend([
        f"Advanced {category} Techniques",
        f"Next-Level {category} Strategies",
        f"Scaling {category} for Enterprise",
        f"Advanced {category}",
        f"Expert {category} Tactics",
        f"Professional {category} Strategies",
        f"Advanced {category} Implementation",
        f"Enterprise {category} Solutions",
        f"Master-Level {category}",
        f"{category} for Experts",
    ])
    
    templates.extend([
        f"Top {category} Tools for {current_year}",
        f"Best {category} Platforms",
        f"{category} Software Comparison",
        f"Essential {category} Tools",
        f"Modern {category} Technology Stack",
        f"{category} Tools",
        f"Choosing {category} Technology",
        f"The Best {category} Solutions",
        f"{category} Software Guide",
        f"Top {category} Platforms",
    ])
    
    templates.extend([
        f"Building a {category} Strategy",
        f"{category} Strategic Planning Guide",
        f"Creating Your {category} Roadmap",
        f"{category} Strategy",
        f"Strategic {category} Implementation",
        f"Planning {category} Initiatives",
        f"{category} Strategy Framework",
        f"Developing {category} Plans",
        f"{category} Planning Guide",
        f"Your {category} Strategy Blueprint",
    ])
    
    templates.extend([
        f"Real-World {category} Success Stories",
        f"{category} Case Studies",
        f"How Companies Succeed with {category}",
        f"{category} Examples and Use Cases",
        f"Learning from {category} Success",
        f"{category} Implementation Examples",
        f"Successful {category} Projects",
        f"{category} in Action",
        f"{category} Success Stories",
        f"Companies Winning with {category}",
    ])
    
    templates.extend([
        f"{category}: From Beginner to Expert",
        f"The Psychology of {category}",
        f"{category} Myths Debunked",
        f"The Science Behind {category}",
        f"{category}: Common Misconceptions",
        f"The Truth About {category}",
        f"{category} Secrets Revealed",
        f"What No One Tells You About {category}",
        f"The Hidden Benefits of {category}",
        f"{category}: Beyond the Basics",
        f"Rethinking {category}",
        f"{category}: A Fresh Perspective",
        f"The Untold Story of {category}",
        f"{category}: Breaking Barriers",
        f"Revolutionary {category} Insights",
        f"The {category} Transformation",
        f"{category}: Game-Changing Strategies",
        f"Unlocking {category} Potential",
        f"The {category} Revolution",
        f"{category}: New Horizons",
    ])
    
    # Additional simple templates
    templates.extend([
        f"Why {category} Matters in {current_year}",
        f"{category} Explained Simply",
        f"Understanding {category} Better",
        f"{category} Made Easy",
        f"Demystifying {category}",
        f"{category} Simplified",
        f"The {category} Handbook",
        f"{category} Deep Dive",
        f"Comprehensive {category} Overview",
        f"{category} Masterclass",
        f"Professional {category} Guide",
        f"{category} Training Course",
        f"Learn {category} Fast",
        f"{category} Crash Course",
        f"Quick {category} Tutorial",
        f"{category} Essentials",
        f"{category} Fundamentals",
        f"Core {category} Concepts",
        f"{category} Principles",
        f"{category} Framework",
        f"{category} Methodology",
        f"Practical {category} Guide",
        f"Applied {category}",
        f"{category} in Practice",
        f"Hands-On {category}",
    ])
    
    # Filter out excluded topics and ensure all are strings
    unique_variations = []
    for template in templates:
        # Ensure template is a string
        if not isinstance(template, str):
            continue
            
        normalized = normalize_topic(template)
        if normalized and normalized not in exclude and len(normalized) > 10:
            unique_variations.append(template)
            exclude.add(normalized)
    
    # Shuffle for randomness
    random.shuffle(unique_variations)
    
    return unique_variations[:count]


def normalize_topic(topic) -> str:
    """Normalize topic for comparison"""
    if not topic:
        return ""
    
    # Ensure it's a string
    if not isinstance(topic, str):
        return ""
    
    # Convert to lowercase
    normalized = topic.lower().strip()
    
    # Remove common prefixes
    prefixes = [
        'the ', 'a ', 'an ', 'how to ', 'what is ', 'why ', 'when ', 'where ',
        'best ', 'top ', 'ultimate ', 'complete ', 'essential ', 'definitive '
    ]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    
    # Remove years and numbers
    normalized = re.sub(r'\b20\d{2}\b', '', normalized)
    normalized = re.sub(r'\b\d+\b', '', normalized)
    
    # Remove special characters
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # Remove extra spaces
    normalized = ' '.join(normalized.split())
    
    return normalized.strip()


def extract_keywords_from_topic(topic: str) -> List[str]:
    """Extract potential keywords from a topic title"""
    
    if not topic or not isinstance(topic, str):
        return []
    
    # Stop words to exclude
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'is', 'are', 'was', 'were', 'how', 'what', 'when', 'where',
        'why', 'which', 'who', 'that', 'this', 'these', 'those', 'your', 'you',
        'guide', 'complete', 'ultimate', 'best', 'top', 'learn', 'everything',
        'need', 'know', 'about', 'get', 'started', 'step', 'steps'
    }
    
    # Clean and split
    words = topic.lower()
    words = re.sub(r'[^\w\s]', ' ', words)
    words = words.split()
    
    # Extract meaningful keywords
    keywords = []
    for word in words:
        if word not in stop_words and len(word) > 3 and not word.isdigit():
            keywords.append(word)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)
    
    return unique_keywords[:7]


def get_topic_hash(topic: str) -> str:
    """Generate a unique hash for a topic"""
    if not topic or not isinstance(topic, str):
        return ""
    
    normalized = normalize_topic(topic)
    if not normalized:
        return ""
    
    return hashlib.md5(normalized.encode()).hexdigest()[:16]


def are_topics_similar(topic1: str, topic2: str, threshold: float = 0.6) -> bool:
    """Check if two topics are too similar"""
    
    if not topic1 or not topic2:
        return False
    
    if not isinstance(topic1, str) or not isinstance(topic2, str):
        return False
    
    norm1 = normalize_topic(topic1)
    norm2 = normalize_topic(topic2)
    
    if not norm1 or not norm2:
        return False
    
    # If normalized forms are identical
    if norm1 == norm2:
        return True
    
    # Word overlap similarity
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return False
    
    # Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    similarity = intersection / union if union > 0 else 0
    
    return similarity >= threshold