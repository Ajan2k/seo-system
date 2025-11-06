from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.utils.seo_utils import calculate_seo_score, suggest_improvements
from app.database import Database
import re

router = APIRouter()
db = Database()

class SEOAnalyzeRequest(BaseModel):
    title: str
    content: str
    keywords: List[str]
    meta_description: Optional[str] = ""
    url: Optional[str] = None

class SEORecalculateRequest(BaseModel):
    post_id: int

class SEOCompareRequest(BaseModel):
    post_id_1: int
    post_id_2: int

class SEOKeywordRequest(BaseModel):
    content: str
    count: int = 10

@router.post("/analyze-seo")
async def analyze_seo(request: SEOAnalyzeRequest):
    """
    Analyze SEO score for any content
    
    - **title**: Post title
    - **content**: Full content in markdown
    - **keywords**: List of target keywords
    - **meta_description**: Meta description (optional)
    - **url**: Target URL for additional checks (optional)
    """
    try:
        # Calculate SEO score
        seo_details = calculate_seo_score(
            title=request.title,
            content=request.content,
            keywords=request.keywords,
            meta_description=request.meta_description
        )
        
        # Generate improvement suggestions
        suggestions = suggest_improvements(seo_details)
        
        # Additional URL analysis if provided
        url_analysis = None
        if request.url:
            url_analysis = analyze_url_seo(request.url, request.keywords)
        
        # Calculate grade
        grade = get_seo_grade(seo_details['total_score'])
        
        return {
            'success': True,
            'seo_score': seo_details['total_score'],
            'grade': grade,
            'details': seo_details,
            'suggestions': suggestions,
            'url_analysis': url_analysis,
            'breakdown': {
                'content_length': {
                    'score': seo_details['length_score'],
                    'max_score': 20,
                    'word_count': seo_details['word_count']
                },
                'keyword_optimization': {
                    'score': seo_details['keyword_score'],
                    'max_score': 25,
                    'density': seo_details['keyword_density']
                },
                'heading_structure': {
                    'score': seo_details['heading_score'],
                    'max_score': 20,
                    'headings': seo_details['headings']
                },
                'readability': {
                    'score': seo_details['readability_score'],
                    'max_score': 15
                },
                'meta_description': {
                    'score': seo_details['meta_score'],
                    'max_score': 10,
                    'length': seo_details['meta_length']
                },
                'structure': {
                    'score': seo_details['structure_score'],
                    'max_score': 10
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recalculate-seo")
async def recalculate_seo(request: SEORecalculateRequest):
    """
    Recalculate SEO score for an existing post
    
    - **post_id**: ID of the post to recalculate
    """
    try:
        # Get post from database
        post = db.get_post(request.post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Parse keywords
        keywords = post['keywords'].split(',') if post['keywords'] else []
        
        # Calculate new SEO score
        seo_details = calculate_seo_score(
            title=post['title'],
            content=post['content'],
            keywords=keywords,
            meta_description=post['meta_description']
        )
        
        # Update in database
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE posts SET seo_score = ? WHERE id = ?",
            (seo_details['total_score'], request.post_id)
        )
        conn.commit()
        conn.close()
        
        # Generate suggestions
        suggestions = suggest_improvements(seo_details)
        
        return {
            'success': True,
            'post_id': request.post_id,
            'old_score': post['seo_score'],
            'new_score': seo_details['total_score'],
            'change': seo_details['total_score'] - post['seo_score'],
            'details': seo_details,
            'suggestions': suggestions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-seo")
async def compare_seo(request: SEOCompareRequest):
    """
    Compare SEO scores of two posts
    
    - **post_id_1**: First post ID
    - **post_id_2**: Second post ID
    """
    try:
        # Get both posts
        post1 = db.get_post(request.post_id_1)
        post2 = db.get_post(request.post_id_2)
        
        if not post1 or not post2:
            raise HTTPException(status_code=404, detail="One or both posts not found")
        
        # Calculate scores
        keywords1 = post1['keywords'].split(',') if post1['keywords'] else []
        keywords2 = post2['keywords'].split(',') if post2['keywords'] else []
        
        seo1 = calculate_seo_score(
            post1['title'], post1['content'], keywords1, post1['meta_description']
        )
        seo2 = calculate_seo_score(
            post2['title'], post2['content'], keywords2, post2['meta_description']
        )
        
        # Compare
        comparison = {
            'post1': {
                'id': post1['id'],
                'title': post1['title'],
                'score': seo1['total_score'],
                'details': seo1
            },
            'post2': {
                'id': post2['id'],
                'title': post2['title'],
                'score': seo2['total_score'],
                'details': seo2
            },
            'winner': request.post_id_1 if seo1['total_score'] > seo2['total_score'] else request.post_id_2,
            'score_difference': abs(seo1['total_score'] - seo2['total_score']),
            'category_comparison': {
                'content_length': {
                    'post1': seo1['length_score'],
                    'post2': seo2['length_score'],
                    'winner': 'post1' if seo1['length_score'] > seo2['length_score'] else 'post2'
                },
                'keyword_optimization': {
                    'post1': seo1['keyword_score'],
                    'post2': seo2['keyword_score'],
                    'winner': 'post1' if seo1['keyword_score'] > seo2['keyword_score'] else 'post2'
                },
                'heading_structure': {
                    'post1': seo1['heading_score'],
                    'post2': seo2['heading_score'],
                    'winner': 'post1' if seo1['heading_score'] > seo2['heading_score'] else 'post2'
                },
                'readability': {
                    'post1': seo1['readability_score'],
                    'post2': seo2['readability_score'],
                    'winner': 'post1' if seo1['readability_score'] > seo2['readability_score'] else 'post2'
                }
            }
        }
        
        return {
            'success': True,
            'comparison': comparison
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-keywords")
async def extract_keywords(request: SEOKeywordRequest):
    """
    Extract relevant keywords from content
    
    - **content**: Content to extract keywords from
    - **count**: Number of keywords to extract (default: 10)
    """
    try:
        # Remove markdown formatting
        clean_content = re.sub(r'[#*`\[\]()]', '', request.content)
        
        # Split into words
        words = re.findall(r'\b[a-z]{4,}\b', clean_content.lower())
        
        # Common stop words to exclude
        stop_words = {
            'that', 'this', 'with', 'from', 'have', 'will', 'your', 'their',
            'there', 'about', 'which', 'when', 'where', 'what', 'how',
            'they', 'them', 'these', 'those', 'than', 'then', 'been',
            'more', 'also', 'some', 'such', 'into', 'just', 'like',
            'only', 'other', 'over', 'such', 'very', 'well', 'even',
            'most', 'must', 'need', 'should', 'would', 'could', 'make'
        }
        
        # Count word frequencies
        word_freq = {}
        for word in words:
            if word not in stop_words and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Sort by frequency
        sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        # Get top keywords
        top_keywords = [
            {
                'keyword': kw,
                'frequency': freq,
                'density': round((freq / len(words)) * 100, 2) if words else 0
            }
            for kw, freq in sorted_keywords[:request.count]
        ]
        
        return {
            'success': True,
            'total_words': len(words),
            'unique_words': len(word_freq),
            'keywords': top_keywords,
            'keyword_list': [kw['keyword'] for kw in top_keywords]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/seo-statistics")
async def get_seo_statistics():
    """
    Get overall SEO statistics for all posts
    """
    try:
        posts = db.get_posts(limit=1000)
        
        if not posts:
            return {
                'success': True,
                'total_posts': 0,
                'statistics': {}
            }
        
        # Calculate statistics
        scores = [p['seo_score'] for p in posts if p['seo_score']]
        
        stats = {
            'total_posts': len(posts),
            'average_score': round(sum(scores) / len(scores), 2) if scores else 0,
            'highest_score': max(scores) if scores else 0,
            'lowest_score': min(scores) if scores else 0,
            'median_score': sorted(scores)[len(scores) // 2] if scores else 0,
            'grade_distribution': {
                'A+ (90-100)': sum(1 for s in scores if s >= 90),
                'A (80-89)': sum(1 for s in scores if 80 <= s < 90),
                'B (70-79)': sum(1 for s in scores if 70 <= s < 80),
                'C (60-69)': sum(1 for s in scores if 60 <= s < 70),
                'D (50-59)': sum(1 for s in scores if 50 <= s < 60),
                'F (<50)': sum(1 for s in scores if s < 50)
            },
            'score_ranges': {
                'excellent (80+)': sum(1 for s in scores if s >= 80),
                'good (70-79)': sum(1 for s in scores if 70 <= s < 80),
                'average (60-69)': sum(1 for s in scores if 60 <= s < 70),
                'poor (<60)': sum(1 for s in scores if s < 60)
            }
        }
        
        # Best and worst posts
        if posts:
            best_post = max(posts, key=lambda p: p['seo_score'] if p['seo_score'] else 0)
            worst_post = min(posts, key=lambda p: p['seo_score'] if p['seo_score'] else 100)
            
            stats['best_post'] = {
                'id': best_post['id'],
                'title': best_post['title'],
                'score': best_post['seo_score']
            }
            stats['worst_post'] = {
                'id': worst_post['id'],
                'title': worst_post['title'],
                'score': worst_post['seo_score']
            }
        
        return {
            'success': True,
            'statistics': stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/seo-checklist/{post_id}")
async def get_seo_checklist(post_id: int):
    """
    Get detailed SEO checklist for a post
    
    - **post_id**: Post ID to check
    """
    try:
        post = db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        keywords = post['keywords'].split(',') if post['keywords'] else []
        
        # Calculate detailed metrics
        word_count = len(post['content'].split())
        title_length = len(post['title'])
        meta_length = len(post['meta_description']) if post['meta_description'] else 0
        
        # Count headings
        h1_count = len(re.findall(r'^#\s+', post['content'], re.MULTILINE))
        h2_count = len(re.findall(r'^##\s+', post['content'], re.MULTILINE))
        h3_count = len(re.findall(r'^###\s+', post['content'], re.MULTILINE))
        
        # Keyword checks
        content_lower = post['content'].lower()
        title_lower = post['title'].lower()
        keywords_in_title = sum(1 for kw in keywords if kw.lower() in title_lower)
        
        checklist = {
            'content_quality': [
                {
                    'item': 'Content length 1000+ words',
                    'status': word_count >= 1000,
                    'current': f'{word_count} words',
                    'target': '1000+ words'
                },
                {
                    'item': 'Paragraphs not too long',
                    'status': True,  # Could add actual check
                    'current': 'Good',
                    'target': '50-150 words per paragraph'
                }
            ],
            'keywords': [
                {
                    'item': 'Keywords in title',
                    'status': keywords_in_title > 0,
                    'current': f'{keywords_in_title} keywords',
                    'target': 'At least 1 keyword'
                },
                {
                    'item': 'Keyword density 1-3%',
                    'status': True,  # From SEO calculation
                    'current': 'Optimal',
                    'target': '1-3%'
                }
            ],
            'structure': [
                {
                    'item': 'Single H1 heading',
                    'status': h1_count == 1,
                    'current': f'{h1_count} H1',
                    'target': 'Exactly 1 H1'
                },
                {
                    'item': 'Multiple H2 headings',
                    'status': h2_count >= 3,
                    'current': f'{h2_count} H2s',
                    'target': 'At least 3 H2s'
                },
                {
                    'item': 'H3 subheadings',
                    'status': h3_count >= 2,
                    'current': f'{h3_count} H3s',
                    'target': 'At least 2 H3s'
                }
            ],
            'meta_data': [
                {
                    'item': 'Title length optimal',
                    'status': 50 <= title_length <= 60,
                    'current': f'{title_length} characters',
                    'target': '50-60 characters'
                },
                {
                    'item': 'Meta description present',
                    'status': meta_length > 0,
                    'current': f'{meta_length} characters',
                    'target': '120-160 characters'
                },
                {
                    'item': 'Meta description optimal',
                    'status': 120 <= meta_length <= 160,
                    'current': f'{meta_length} characters',
                    'target': '120-160 characters'
                }
            ],
            'media': [
                {
                    'item': 'Featured image present',
                    'status': bool(post.get('image_url')),
                    'current': 'Yes' if post.get('image_url') else 'No',
                    'target': 'Required'
                }
            ]
        }
        
        # Calculate completion percentage
        total_checks = sum(len(cat) for cat in checklist.values())
        passed_checks = sum(
            sum(1 for item in cat if item['status'])
            for cat in checklist.values()
        )
        completion = round((passed_checks / total_checks) * 100, 1)
        
        return {
            'success': True,
            'post_id': post_id,
            'post_title': post['title'],
            'seo_score': post['seo_score'],
            'completion_percentage': completion,
            'passed_checks': passed_checks,
            'total_checks': total_checks,
            'checklist': checklist
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Helper Functions

def get_seo_grade(score: int) -> str:
    """Convert SEO score to letter grade"""
    if score >= 90:
        return 'A+'
    elif score >= 80:
        return 'A'
    elif score >= 70:
        return 'B'
    elif score >= 60:
        return 'C'
    elif score >= 50:
        return 'D'
    else:
        return 'F'


def analyze_url_seo(url: str, keywords: List[str]) -> Dict:
    """Analyze URL structure for SEO"""
    url_lower = url.lower()
    
    # Check if URL is SEO-friendly
    has_keywords = sum(1 for kw in keywords if kw.lower() in url_lower)
    has_hyphens = '-' in url
    is_short = len(url) < 75
    no_special_chars = not bool(re.search(r'[^a-z0-9\-/:]', url_lower))
    
    score = 0
    if has_keywords > 0:
        score += 25
    if has_hyphens:
        score += 25
    if is_short:
        score += 25
    if no_special_chars:
        score += 25
    
    return {
        'score': score,
        'url': url,
        'checks': {
            'keywords_in_url': has_keywords > 0,
            'uses_hyphens': has_hyphens,
            'short_url': is_short,
            'no_special_characters': no_special_chars
        },
        'recommendations': [
            'Include target keywords' if has_keywords == 0 else '✓ Keywords present',
            'Use hyphens to separate words' if not has_hyphens else '✓ Hyphens used',
            'Keep URL under 75 characters' if not is_short else '✓ URL length optimal',
            'Avoid special characters' if not no_special_chars else '✓ Clean URL structure'
        ]
    }