# app/routes/generate_blog.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import httpx
import re
from typing import List, Optional

from app.utils.search_trends import search_trending_topics, extract_keywords_from_topic
from app.utils.seo_utils import (
    calculate_seo_score, suggest_improvements,
    generate_focus_keyphrase, generate_seo_title, generate_meta_description,validate_and_fix_meta_description,
    generate_slug, add_outbound_links, ensure_keyphrase_in_intro,
    optimize_readability, ensure_keyphrase_in_headings, limit_keyphrase_density,
    fix_competing_links
)
from app.utils.image_api import ImageGenerator
from app.database import db

router = APIRouter()
image_gen = ImageGenerator()


class BlogGenerateRequest(BaseModel):
    category: str
    website_id: Optional[int] = None
    custom_topic: Optional[str] = None
    target_score: int = 80
    focus_keyword: Optional[str] = None 
    brand_name: Optional[str] = "Infinitetechai"
    industries: Optional[List[str]] = ["healthcare", "education", "e-commerce", "real estate"]


class GroqAPI:
    """Async Groq API client for blog generation"""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.client = httpx.AsyncClient(timeout=120.0)

        if not self.api_key:
            print("⚠️ WARNING: GROQ_API_KEY not found in environment variables")

    async def generate_blog(
        self,
        topic: str,
        keywords: List[str],
        brand_name: str = "Infinitetechai",
        industries: List[str] = None,
        attempt: int = 1
    ) -> dict:
        """Generate SEO-optimized blog post"""

        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured")

        # Ensure keywords is a flat list of strings
        clean_keywords = []
        for kw in keywords:
            if isinstance(kw, str):
                clean_keywords.append(kw.strip())
            elif isinstance(kw, list):
                for item in kw:
                    if isinstance(item, str):
                        clean_keywords.append(item.strip())

        primary_keyword = clean_keywords[0] if clean_keywords else topic.lower()
        secondary_keywords = clean_keywords[1:4] if len(clean_keywords) > 1 else []

        if industries is None:
            industries = ["healthcare", "education", "e-commerce"]

        prompt = f"""Write a comprehensive, SEO-optimized blog post about "{topic}".

REQUIREMENTS:

1. PRIMARY KEYWORD: "{primary_keyword}" - Use naturally with **1.5-1.9% density** (do NOT specify exact count; aim for natural placement)
2. SECONDARY KEYWORDS: {', '.join(secondary_keywords)} - Use each 4-6 times naturally
3. WORD COUNT: 1,600-1,900 words (exactly)
4. BRAND NAME: {brand_name}

STRUCTURE (MUST FOLLOW):

# {topic}

## Introduction (200-250 words)
- Hook the reader with an engaging opening
- Mention the primary keyword in the first sentence
- Explain why this topic matters
- Preview what the article will cover

## What is {primary_keyword}? (250-300 words)
- Clear definition
- Background and context
- Current relevance
- Key components

## Benefits of {primary_keyword} (300-350 words)
- List 5-7 key benefits with explanations
- Use bullet points for better readability
- Include real-world examples
- Mention {brand_name} solutions

## How {primary_keyword} Works (300-350 words)
### Core Principles
- Explain the fundamental concepts
- Use numbered steps for processes

### Implementation Process
1. Step one with details
2. Step two with details
3. Step three with details
4. Step four with details

## Industry Applications (300-350 words)
### {industries[0] if industries else 'Healthcare'}
- Specific use cases
- Benefits for this industry
- Example: "{brand_name} helped a healthcare provider increase efficiency by 45%"

### {industries[1] if len(industries) > 1 else 'Education'}
- Specific use cases
- Real-world applications

### {industries[2] if len(industries) > 2 else 'E-commerce'}
- Implementation examples
- ROI metrics

## Best Practices for {primary_keyword} (250-300 words)
- List 6-8 actionable best practices
- Use a mix of bullet points and short paragraphs
- Include expert tips from {brand_name}

## Common Challenges and Solutions (200-250 words)
- Identify 3-4 common challenges
- Provide practical solutions
- Reference {brand_name} expertise

## Future Trends (150-200 words)
- Emerging trends in {primary_keyword}
- What to expect in the next 2-3 years
- How {brand_name} is staying ahead

## Conclusion (150-200 words)
- Summarize key points
- Reinforce the value of {primary_keyword}
- Strong call-to-action mentioning {brand_name}
- "Contact {brand_name} today to learn more about {primary_keyword} solutions"

WRITING GUIDELINES:
- Use conversational yet professional tone
- Include questions to engage readers
- Add relevant statistics and data points
- Cite credible sources (IBM Watson, Gartner, Forrester, etc.)
- Use transition words between sections
- Vary sentence length for better readability
- Include practical examples throughout

SEO OPTIMIZATION:
- Keyword density: 2% for primary keyword
- Keywords in headings (at least 50% of H2s should contain keywords)
- Natural keyword placement
- Use synonyms and related terms

Write the complete blog post now in markdown format. Start with # {topic} and include all sections."""

        try:
            print(f"🤖 Calling Groq API (Attempt {attempt})...")

            response = await self.client.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert SEO content writer with 10+ years of experience. You create comprehensive, engaging blog posts that rank well on Google while providing real value to readers. Always write complete, detailed content in markdown format with proper headings, paragraphs, lists, and formatting."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4500,
                    "top_p": 0.9
                }
            )

            response.raise_for_status()

            result = response.json()

            if 'choices' not in result or len(result['choices']) == 0:
                raise ValueError("No content in API response")

            raw_content = result["choices"][0]["message"]["content"]

            if not raw_content or len(raw_content.strip()) < 100:
                raise ValueError(f"Content too short: {len(raw_content)} characters")

            print(f"✅ Received {len(raw_content)} characters from API")

            parsed = self._parse_blog_content(raw_content, topic, primary_keyword, clean_keywords, brand_name)

            return parsed

        except httpx.TimeoutException:
            print("❌ API request timed out")
            raise HTTPException(status_code=504, detail="API request timed out")
        except httpx.HTTPStatusError as e:
            print(f"❌ API returned status code: {e.response.status_code}")
            print(f"Response: {e.response.text}")
            raise HTTPException(status_code=500, detail=f"Groq API error: {e.response.status_code}")
        except httpx.RequestError as e:
            print(f"❌ API request error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"API connection error: {str(e)}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def _parse_blog_content(self, raw_content: str, topic: str, primary_keyword: str,
                            all_keywords: List[str], brand_name: str) -> dict:
        """Parse and validate blog content"""
        content = raw_content.strip()
        title = topic
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()

        if primary_keyword.lower() not in title.lower():
            title = f"{title}: Complete {primary_keyword.title()} Guide"

        meta_description = self._extract_meta_description(content, primary_keyword)
        blog_content = content
        
        if not re.search(r'^##\s+', content, re.MULTILINE):
            blog_content = self._add_structure(content, topic, primary_keyword, all_keywords, brand_name)

        word_count = len(blog_content.split())
        if word_count < 800:
            print(f"⚠️ Content too short ({word_count} words), enhancing...")
            blog_content = self._enhance_content(blog_content, topic, primary_keyword, all_keywords, brand_name)

        print(f"📝 Final content: {len(blog_content)} chars, {len(blog_content.split())} words")

        return {
            'title': title,
            'content': blog_content,
            'meta_description': meta_description,
            'keywords': all_keywords
        }

    def _extract_meta_description(self, content: str, keyword: str) -> str:
        """Extract and optimize meta description"""
        lines = content.split('\n')
        first_para = ""

        for line in lines:
            clean_line = line.strip()
            if clean_line and not clean_line.startswith('#') and len(clean_line) > 50:
                first_para = clean_line
                break

        meta = re.sub(r'[*_`\[\]]', '', first_para)

        if keyword.lower() not in meta.lower():
            meta = f"Discover {keyword}: {meta}"

        if len(meta) > 160:
            meta = meta[:157] + "..."
        elif len(meta) < 140:
            meta = meta + f" Learn more about {keyword}."
            if len(meta) > 160:
                meta = meta[:157] + "..."

        return meta

    def _enhance_content(self, content: str, topic: str, keyword: str,
                         keywords: List[str], brand: str) -> str:
        """Enhance short content to meet word count requirements"""
        enhanced = content

        if "benefit" not in content.lower():
            enhanced += f"""

## Key Benefits of {keyword}

Implementing {keyword} solutions offers numerous advantages for organizations:

- **Increased Efficiency**: Streamline operations and reduce manual work by up to 60%
- **Cost Savings**: Reduce operational costs while improving output quality
- **Enhanced User Experience**: Deliver better experiences that drive engagement
- **Scalability**: Grow your operations without proportional cost increases
- **Data-Driven Insights**: Make informed decisions based on real-time analytics
- **Competitive Advantage**: Stay ahead of competitors with cutting-edge solutions
- **Improved ROI**: See measurable returns on your technology investments

{brand} has helped organizations across industries achieve these benefits and more.
"""

        if "implementation" not in content.lower() and "how to" not in content.lower():
            enhanced += f"""

## Implementing {keyword} Successfully

### Step-by-Step Implementation Guide

1. **Assessment Phase**
   - Evaluate your current capabilities and needs
   - Identify gaps and opportunities
   - Define clear, measurable objectives

2. **Planning Phase**
   - Develop a comprehensive strategy
   - Allocate resources and budget
   - Create a realistic timeline

3. **Execution Phase**
   - Begin implementation with pilot programs
   - Monitor progress and gather feedback
   - Make adjustments based on results

4. **Optimization Phase**
   - Analyze performance metrics
   - Identify areas for improvement
   - Scale successful elements

5. **Maintenance Phase**
   - Provide ongoing support and training
   - Keep systems updated
   - Continuously optimize for better results

{brand} provides expert guidance throughout every phase of implementation.
"""

        if "case study" not in content.lower() and "example" not in content.lower():
            enhanced += f"""

## Real-World Success Stories

### Healthcare: 45% Efficiency Improvement

A major healthcare provider partnered with {brand} to implement {keyword} solutions. Results included:
- 45% reduction in processing time
- 60% improvement in patient satisfaction
- 30% cost savings in operations

### Education: Enhanced Learning Outcomes

An educational institution leveraged {keyword} to transform their approach:
- 50% increase in student engagement
- 35% improvement in learning outcomes
- 40% reduction in administrative burden

### E-commerce: Revenue Growth

A leading e-commerce platform used {keyword} to boost performance:
- 55% increase in conversion rates
- 40% improvement in customer retention
- 65% reduction in cart abandonment
"""

        if "best practice" not in content.lower():
            enhanced += f"""

## Best Practices for {keyword}

### Essential Guidelines for Success

1. **Start with Clear Objectives**
   - Define what success looks like
   - Set measurable KPIs
   - Align with business goals

2. **Choose the Right Tools**
   - Evaluate options carefully
   - Consider scalability
   - Prioritize integration capabilities

3. **Invest in Training**
   - Ensure team readiness
   - Provide ongoing education
   - Foster a culture of learning

4. **Monitor and Measure**
   - Track key metrics regularly
   - Use data to inform decisions
   - Adjust strategies based on insights

5. **Stay Updated**
   - Keep pace with industry trends
   - Adopt new technologies when beneficial
   - Continuously innovate

6. **Partner with Experts**
   - Work with experienced providers like {brand}
   - Leverage specialized knowledge
   - Accelerate time to value
"""

        return enhanced

    def _add_structure(self, content: str, topic: str, keyword: str,
                       keywords: List[str], brand: str) -> str:
        """Add proper heading structure to unstructured content"""
        structured = f"# {topic}\n\n"
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and not p.strip().startswith('#')]

        if len(paragraphs) < 3:
            return self._generate_complete_article(topic, keyword, keywords, brand)

        sections = [
            ("## Introduction", paragraphs[0] if paragraphs else f"Understanding {keyword} is essential in today's digital landscape."),
            (f"## What is {keyword}?", paragraphs[1] if len(paragraphs) > 1 else f"{keyword} represents a comprehensive approach to solving modern challenges."),
            (f"## Benefits of {keyword}", """
### Key Advantages

- Enhanced operational efficiency
- Significant cost reductions
- Improved user satisfaction
- Better decision-making capabilities
- Scalable growth potential
"""),
            ("## Implementation Guide", """
### Getting Started

1. Assess your current situation
2. Define clear objectives
3. Choose the right approach
4. Execute with precision
5. Monitor and optimize
"""),
            (f"## Best Practices", paragraphs[2] if len(paragraphs) > 2 else f"Following industry best practices ensures success with {keyword}."),
            ("## Industry Applications", f"""
### Healthcare
{keyword} is transforming patient care and operational efficiency.

### Education
Educational institutions leverage {keyword} for better learning outcomes.

### E-commerce
Online retailers use {keyword} to boost sales and customer satisfaction.
"""),
            ("## Conclusion", f"Implementing {keyword} effectively requires expertise and dedication. {brand} provides the solutions and support you need to succeed. Contact us today to learn more.")
        ]

        for heading, content_text in sections:
            structured += f"{heading}\n\n{content_text}\n\n"

        return structured

    def _generate_complete_article(self, topic: str, keyword: str,
                                   keywords: List[str], brand: str) -> str:
        """Generate a complete article when API content is insufficient"""
        secondary_kw = keywords[1] if len(keywords) > 1 else f"{keyword} solutions"

        article = f"""# {topic}

## Introduction to {keyword}

In today's rapidly evolving digital landscape, {keyword} has emerged as a critical component for organizations seeking to maintain competitive advantage. Whether you're in healthcare, education, e-commerce, or manufacturing, understanding and implementing {keyword} effectively can transform your operations and drive significant business value.

This comprehensive guide explores everything you need to know about {keyword}, from fundamental concepts to advanced implementation strategies. We'll examine real-world applications, best practices, and how {brand} can help you achieve your {keyword} objectives.

## What is {keyword}?

{keyword} refers to the systematic approach of leveraging technology and strategic methodologies to enhance organizational capabilities. At its core, {keyword} encompasses:

- **Strategic Planning**: Aligning {keyword} initiatives with business objectives
- **Technical Implementation**: Deploying the right tools and platforms
- **Process Optimization**: Streamlining workflows for maximum efficiency
- **Data Management**: Leveraging information for better decision-making
- **Continuous Improvement**: Adapting and evolving based on results

The importance of {keyword} cannot be overstated. Organizations that effectively implement {keyword} strategies see average improvements of 40-60% in operational efficiency and 30-50% reductions in costs.

## Key Benefits of {keyword}

Implementing {keyword} delivers tangible benefits:

- **Increased Efficiency**: 40-60% improvement in process efficiency
- **Cost Reduction**: 30-50% decrease in operational costs
- **Better Decisions**: Data-driven insights for smarter choices
- **Competitive Edge**: Stay ahead with innovative {keyword} solutions
- **Scalability**: Grow without proportional cost increases
- **ROI**: Measurable returns within 12-18 months

{brand} has helped hundreds of organizations achieve these results.

## How to Implement {keyword}

### Step-by-Step Guide

1. **Assessment**: Evaluate current state and needs
2. **Planning**: Develop comprehensive strategy
3. **Execution**: Implement with expert guidance
4. **Optimization**: Continuously improve performance
5. **Scaling**: Expand successful initiatives

{brand} provides end-to-end support throughout implementation.

## Industry Applications

### Healthcare
{keyword} improves patient care and operational efficiency with 45% average improvements.

### Education
Educational institutions see 50% increases in engagement using {keyword}.

### E-commerce
Online retailers achieve 55% conversion rate improvements with {keyword}.

## Best Practices

1. Start with clear objectives
2. Choose scalable solutions
3. Invest in training
4. Monitor key metrics
5. Partner with experts like {brand}

## Conclusion

{keyword} represents a significant opportunity for business transformation. Success requires the right strategy, technology, and partner.

Contact {brand} today to learn how {keyword} can drive your success.
"""
        return article


groq_api = GroqAPI()


def clean_keywords(keywords):
    """Ensure keywords is a flat list of strings"""
    if not keywords:
        return []

    clean = []
    for kw in keywords:
        if isinstance(kw, str):
            clean.append(kw.strip().lower())
        elif isinstance(kw, list):
            for item in kw:
                if isinstance(item, str):
                    clean.append(item.strip().lower())

    seen = set()
    unique = []
    for k in clean:
        if k and k not in seen:
            seen.add(k)
            unique.append(k)

    return unique


@router.post("/generate")
async def generate_blog(request: BlogGenerateRequest):
    """Generate SEO-optimized blog post with Yoast SEO requirements"""

    try:
        print(f"\n{'='*60}")
        print(f"🎯 Starting Blog Generation with Yoast SEO Optimization")
        print(f"{'='*60}\n")

        # Step 1: Get topic and keywords
        if request.custom_topic:
            topic = request.custom_topic
            keywords = extract_keywords_from_topic(topic)
        else:
            trending_topics = search_trending_topics(request.category, count=1)
            topic = trending_topics[0] if trending_topics else f"Complete Guide to {request.category}"
            keywords = extract_keywords_from_topic(topic)

        keywords = clean_keywords(keywords)[:7]

        # Step 2: Generate or use provided focus keyphrase
        if request.focus_keyword:  # <--- USE PROVIDED FOCUS KEYWORD
            focus_keyphrase = request.focus_keyword.strip().lower()
            print(f"🎯 Using provided Focus Keyphrase: '{focus_keyphrase}'")
        else:
            focus_keyphrase = generate_focus_keyphrase(keywords, topic)
            print(f"🎯 Generated Focus Keyphrase: '{focus_keyphrase}'")

        # Step 3: Check if keyphrase already used
        if request.website_id and await db.is_keyphrase_used(focus_keyphrase, request.website_id):
            print(f"⚠️ Keyphrase '{focus_keyphrase}' already used, generating alternative...")
            focus_keyphrase = f"{focus_keyphrase} {request.category}"

        print(f"📝 Topic: {topic}")
        print(f"🔑 Keywords: {', '.join(keywords[:5])}\n")

        # Step 4: Generate blog content
        max_attempts = 3
        best_post = None
        best_score = 0

        for attempt in range(max_attempts):
            try:
                print(f"{'─'*60}")
                print(f"🔄 Generation Attempt {attempt + 1}/{max_attempts}")
                print(f"{'─'*60}\n")

                blog_data = await groq_api.generate_blog(
                    topic=topic,
                    keywords=[focus_keyphrase] + keywords,
                    brand_name=request.brand_name,
                    industries=request.industries,
                    attempt=attempt + 1
                )

                if not blog_data.get('content') or len(blog_data['content'].strip()) < 500:
                    print(f"❌ Content too short or empty, retrying...\n")
                    continue

                # Content optimization
                try:
                    blog_data['content'] = optimize_readability(
                        content=blog_data['content'],
                        title=blog_data['title'],
                        focus_keyphrase=blog_data.get('focus_keyphrase', ''),
                        min_transition_percent=30.0,
                        max_paragraph_words=150,
                        max_sentence_words=20,
                        max_long_sentence_ratio=0.25,
                        subheading_gap=250
                    )
                    
                    blog_data['content'] = ensure_keyphrase_in_intro(
                        content=blog_data['content'],
                        focus_keyphrase=blog_data.get('focus_keyphrase', ''),
                        variants=blog_data.get('synonyms', []),
                        bold=True
                    )
                    
                    blog_data['content'] = ensure_keyphrase_in_headings(
                        content=blog_data['content'],
                        keyphrase=blog_data.get('focus_keyphrase', ''),
                        synonyms=blog_data.get('synonyms', []),
                        target_ratio=0.5,
                        max_changes=3
                    )
                    
                    blog_data['content'] = limit_keyphrase_density(
                        content=blog_data['content'],
                        keyphrase=blog_data.get('focus_keyphrase', ''),
                        target_min=1.0,
                        target_max=1.6,
                        hard_cap=38
                    )
                    
                    blog_data['content'] = fix_competing_links(
                        content=blog_data['content'],
                        keyphrase=blog_data.get('focus_keyphrase', ''),
                        synonyms=blog_data.get('synonyms', [])
                    )
                    
                    blog_data['content'] = add_outbound_links(
                        content=blog_data['content'],
                        keywords=keywords,
                        topic=topic,
                        max_links=3,
                        avoid_anchor_terms=[blog_data.get('focus_keyphrase', '')]
                    )

                except Exception as e:
                    print(f"❌ Error in content optimization: {e}")

                blog_data['content'] = ensure_keyphrase_in_intro(blog_data['content'], focus_keyphrase)

                seo_title = generate_seo_title(blog_data['title'], focus_keyphrase)
                blog_data['seo_title'] = seo_title

                

                meta_description = generate_meta_description(blog_data['content'], focus_keyphrase, target_length=155)

                # CRITICAL: Validate length before saving
                if len(meta_description) > 156:
                    print(f"❌ WARNING: Meta {len(meta_description)} chars, emergency truncating...")
                    meta_description = meta_description[:153].rstrip('.,!?;:- ') + '...'

                # Final verification
                assert len(meta_description) <= 156, f"Meta STILL too long: {len(meta_description)} chars"

                blog_data['meta_description'] = meta_description

                print(f"\n✅ Meta Description Validated:")
                print(f"   Length: {len(meta_description)}/156 chars")
                print(f"   Content: '{meta_description}'")

                print(f"✅ Final meta length: {len(meta_description)} chars")
                print(f"   Content: '{meta_description}'")

                slug = generate_slug(blog_data['title'], focus_keyphrase)
                blog_data['slug'] = slug

                print(f"📊 SEO Title: {seo_title}")
                print(f"📊 Meta Description: {meta_description}")
                print(f"📊 Slug: {slug}")

                word_count = len(blog_data['content'].split())
                print(f"📊 Word count: {word_count}")

                seo_details = calculate_seo_score(
                    title=seo_title,
                    content=blog_data['content'],
                    keywords=keywords,
                    meta_description=meta_description,
                    focus_keyphrase=focus_keyphrase
                )

                current_score = seo_details['total_score']

                print(f"📈 SEO Score: {current_score}/100")
                print(f"   ├─ Content Length: {seo_details['length_score']}")
                print(f"   ├─ Keyphrase in Title: {seo_details['title_keyphrase_score']}")
                print(f"   ├─ Keyphrase in Intro: {seo_details['intro_keyphrase_score']}")
                print(f"   ├─ Keyphrase Density: {seo_details['density_score']} ({seo_details['keyword_density']}%)")
                print(f"   ├─ Meta Description: {seo_details['meta_score']}")
                print(f"   ├─ Heading Structure: {seo_details['heading_score']}")
                print(f"   ├─ Outbound Links: {seo_details['outbound_score']} ({seo_details['outbound_links']} links)")
                print(f"   ├─ Readability: {seo_details['readability_score']}")
                print(f"   └─ Structure: {seo_details['structure_score']}\n")

                if current_score > best_score:
                    best_score = current_score
                    best_post = {**blog_data, 'seo_details': seo_details, 'keywords': keywords, 'focus_keyphrase': focus_keyphrase}
                    print(f"✅ New best score: {current_score}/100\n")

                if current_score >= request.target_score:
                    print(f"🎉 Target score {request.target_score} achieved!\n")
                    break

            except Exception as e:
                print(f"❌ Error in attempt {attempt + 1}: {str(e)}\n")
                if attempt == max_attempts - 1:
                    raise
                continue

        # Check if we got any valid content after all attempts
        if not best_post:
            raise HTTPException(status_code=500, detail="Failed to generate content")

        final_post = best_post
        final_score = final_post['seo_details']['total_score']

        # Step 11: Generate image with alt text
        print("🎨 Generating featured image...")
        image_url = image_gen.generate_image(
            prompt=final_post['title'],
            keywords=[focus_keyphrase] + keywords
        )

        # Step 12: Save to database with all SEO fields
        print("💾 Saving to database...")

        # Around line 380 in generate_blog.py
        post_id = await db.add_post(
            title=final_post['title'],
            slug=final_post.get('slug', ''),  # ← This should now always be the focus keyphrase
            content=final_post['content'],
            meta_description=final_post['meta_description'],
            keywords=','.join(keywords),
            category=request.category,
            focus_keyphrase=focus_keyphrase,  # ← This matches the slug
            seo_title=final_post['seo_title'],
            website_id=request.website_id,
            image_url=image_url,
            seo_score=final_score
        )

        # Verify slug matches focus keyphrase
        print(f"✅ Post saved with:")
        print(f"   - Focus Keyphrase: '{focus_keyphrase}'")
        print(f"   - Slug: '{final_post.get('slug', '')}'")
        print(f"   - Match: {final_post.get('slug', '').replace('-', ' ') == focus_keyphrase.lower()}")

        suggestions = suggest_improvements(final_post['seo_details'])
        ready_to_publish = final_score >= 80

        print(f"{'='*60}")
        print(f"✅ Blog Generation Complete!")
        print(f"📊 Final SEO Score: {final_score}/100")
        print(f"🎯 Focus Keyphrase: '{focus_keyphrase}'")
        print(f"{'='*60}\n")

        return {
            'success': True,
            'post_id': post_id,
            'title': final_post['title'],
            'seo_title': final_post['seo_title'],
            'slug': final_post['slug'],
            'content': final_post['content'],
            'meta_description': final_post['meta_description'],
            'keywords': keywords,
            'focus_keyphrase': focus_keyphrase,
            'seo_score': final_score,
            'seo_details': final_post['seo_details'],
            'suggestions': suggestions,
            'image_url': image_url,
            'ready_to_publish': ready_to_publish,
            'word_count': len(final_post['content'].split())
        }

    except Exception as e:
        print(f"\n❌ Fatal Error: {str(e)}\n")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending/{category}")
async def get_trending_topics(category: str, count: int = 5):
    """Get trending topics for a category"""
    try:
        topics = search_trending_topics(category, count)
        return {'success': True, 'topics': topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate/{post_id}")
async def regenerate_for_better_seo(post_id: int):
    """Regenerate a post to achieve better SEO score"""
    try:
        post = await db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        current_score = post.get('seo_score', 0)

        if current_score >= 80:
            return {
                'success': True,
                'message': 'Post already has good SEO score',
                'current_score': current_score
            }

        keywords_str = post.get('keywords', '')
        keywords = [k.strip() for k in keywords_str.split(',') if k.strip()] if keywords_str else []

        request = BlogGenerateRequest(
            category=post['category'],
            custom_topic=post['title'],
            target_score=80,
            website_id=post.get('website_id')
        )

        result = await generate_blog(request)

        return {
            'success': True,
            'old_score': current_score,
            'new_score': result['seo_score'],
            'improvement': result['seo_score'] - current_score,
            'new_post_id': result['post_id']
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))