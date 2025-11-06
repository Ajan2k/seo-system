# app/utils/seo_utils.py
import re
from typing import List, Dict, Optional, Tuple
import textstat
from slugify import slugify

# ----------------------------
# Transition words (Yoast-style)
# ----------------------------
DEFAULT_H2S = [
    "What Is {topic}?",
    "Key Benefits of {topic}",
    "How {topic} Works",
    "Best Practices for {topic}",
    "Common Mistakes to Avoid",
    "Use Cases and Examples",
    "Conclusion and Next Steps"
]
TRANSITION_WORDS = {
    # Agreement/addition/likewise
    "additionally", "also", "and", "as well", "besides", "further", "furthermore",
    "in addition", "moreover",
    # Contrast
    "however", "nevertheless", "nonetheless", "on the other hand", "instead", "still", "though", "conversely",
    # Cause/effect
    "therefore", "thus", "hence", "as a result", "consequently", "so",
    # Examples
    "for example", "for instance", "in fact", "notably", "specifically",
    # Time/order
    "first", "second", "third", "next", "then", "afterward", "finally", "meanwhile",
    # Emphasis/clarification
    "indeed", "in other words", "similarly", "in contrast"
}

# Some irregular past participles to help passive voice detection
IRREGULAR_PPART = {
    "known", "given", "built", "sold", "made", "found", "taken", "seen", "born",
    "shown", "driven", "grown", "bought", "caught", "taught", "thought", "brought",
    "fought", "written", "cut", "put", "read", "set", "sent", "held", "left", "kept",
    "led", "felt", "met", "paid", "said", "told", "won"
}

# Simpler vocabulary replacements
SIMPLE_WORD_MAP = {
    "utilize": "use",
    "leverage": "use",
    "commence": "start",
    "subsequently": "then",
    "consequently": "so",
    "approximately": "about",
    "demonstrate": "show",
    "implement": "use",
    "methodology": "method",
    "facilitate": "help",
    "optimize": "improve",
    "prioritize": "focus on",
    "streamline": "simplify",
    "endeavor": "try",
    "numerous": "many",
    "individuals": "people",
    "utilization": "use",
    "capabilities": "abilities",
    "objective": "goal",
    "subsequent": "later",
    "endeavour": "try",
}


def _split_paragraphs(text: str) -> List[str]:
    # Split on blank lines; keep non-empty
    paras = [p.strip() for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]
    return paras


def _words(s: str) -> List[str]:
    return re.findall(r"\b[\w'-]+\b", s)


def _is_heading(line: str) -> bool:
    return line.strip().startswith('#')


def _split_sentences(text: str) -> List[str]:
    # Remove headings for sentence checks
    lines = [ln for ln in text.splitlines() if not _is_heading(ln)]
    joined = ' '.join(lines)
    joined = re.sub(r'\s+', ' ', joined).strip()
    if not joined:
        return []

    # Naive sentence split on punctuation + space
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(])', joined)
    # Fallback split if above fails miserably
    if len(parts) == 1:
        parts = re.split(r'(?<=[.!?])\s+', joined)

    # Clean and keep non-empty
    sentences = [p.strip() for p in parts if _words(p)]
    return sentences

def _insert_h2_subheadings(paragraphs: List[str], title: str, focus: str, gap: int = 250) -> List[str]:
    """
    Insert an H2 roughly every `gap` words to satisfy Yoast 'subheading distribution'.
    Uses keyword-aware defaults and respects existing headings.
    """
    topic = (focus or title or "").strip()
    headings = [h.format(topic=topic) for h in DEFAULT_H2S]
    h_ptr = 0

    out = []
    since_last_h2 = 0

    for p in paragraphs:
        if p.strip().startswith("## "):  # already an H2
            out.append(p)
            since_last_h2 = 0
            continue

        words = len(_words(p))
        if since_last_h2 >= gap and h_ptr < len(headings):
            out.append(f"## {headings[h_ptr]}")
            h_ptr += 1
            since_last_h2 = 0

        out.append(p)
        since_last_h2 += words

    # If content is long but still has no H2, inject 1-2 at top
    total_words = sum(len(_words(p)) for p in paragraphs if not _is_heading(p))
    if total_words > 400 and not any(par.strip().startswith("## ") for par in out):
        out.insert(1, f"## {headings[0] if headings else 'Overview'}")
        if len(headings) > 1:
            out.insert(3, f"## {headings[1]}")

    return out

def _first_word(sentence: str) -> str:
    m = re.match(r'^[^A-Za-z0-9]*([A-Za-z0-9]+)', sentence)
    return (m.group(1) if m else '').lower()


def _contains_transition(sentence: str) -> bool:
    low = sentence.lower()
    # Check sentence start transitions and inline transitions
    starts = [
        "however", "moreover", "furthermore", "additionally", "therefore", "thus",
        "for example", "for instance", "meanwhile", "in addition", "consequently",
        "in contrast", "similarly", "indeed", "in other words", "finally", "next", "then"
    ]
    if any(low.startswith(tw + ' ') or low.startswith(tw + ',') for tw in starts):
        return True
    return any(f" {tw} " in low for tw in TRANSITION_WORDS)


def _is_passive(sentence: str) -> bool:
    """
    Heuristic passive voice check.
    Looks for 'be' verb + past participle (+ optional 'by ...').
    """
    low = sentence.lower()
    # Quick exit for questions or very short
    if len(_words(low)) < 5:
        return False

    be_forms = r"(?:am|is|are|was|were|be|been|being)"
    # past participle: regular -ed or irregular list
    ppart = r"(?:\w+ed|" + "|".join(IRREGULAR_PPART) + r")"
    pattern = re.compile(rf"\b{be_forms}\b\s+\b{ppart}\b(?:\s+by\b)?")
    return bool(pattern.search(low))


def readability_metrics(content: str) -> Dict:
    paragraphs = _split_paragraphs(content)
    non_heading_paras = [p for p in paragraphs if not _is_heading(p)]
    sentences = _split_sentences(content)
    total_sentences = len(sentences)
    total_words = len(_words(content))

    # Long sentences (> 20 words)
    long_sentences = [s for s in sentences if len(_words(s)) > 20]
    long_sentence_ratio = (len(long_sentences) / total_sentences) if total_sentences else 0.0

    # Passive voice
    passive_flags = [1 for s in sentences if _is_passive(s)]
    passive_pct = (len(passive_flags) / total_sentences * 100.0) if total_sentences else 0.0

    # Transition words
    transition_flags = [1 for s in sentences if _contains_transition(s)]
    transition_pct = (len(transition_flags) / total_sentences * 100.0) if total_sentences else 0.0

    # Consecutive sentence starters (3+)
    first_words = [_first_word(s) for s in sentences]
    consecutive_runs = 0
    run_len = 1
    for i in range(1, len(first_words)):
        if first_words[i] and first_words[i] == first_words[i - 1]:
            run_len += 1
        else:
            if run_len >= 3:
                consecutive_runs += 1
            run_len = 1
    if run_len >= 3:
        consecutive_runs += 1

    # Paragraphs over 150 words
    paras_over_150 = sum(1 for p in non_heading_paras if len(_words(p)) > 150)

    # Flesch Reading Ease
    try:
        flesch = textstat.flesch_reading_ease(content)
    except Exception:
        flesch = 0.0

    # Difficult words ratio
    try:
        difficult = textstat.difficult_words(content)
    except Exception:
        difficult = 0
    difficult_ratio = (difficult / total_words) if total_words else 0.0

    return {
        "word_count": total_words,
        "sentence_count": total_sentences,
        "long_sentence_ratio": round(long_sentence_ratio, 4),
        "passive_voice_percent": round(passive_pct, 1),
        "transition_word_percent": round(transition_pct, 1),
        "consecutive_sentence_runs": consecutive_runs,
        "paragraphs_over_150_words": paras_over_150,
        "flesch_reading_ease": round(flesch, 1),
        "difficult_words_ratio": round(difficult_ratio, 4),
    }


def optimize_readability(
    content: str,
    min_transition_percent: float = 30.0,
    max_long_sentence_ratio: float = 0.25,
    max_paragraph_words: int = 150,
    title: str = "",
    focus_keyphrase: str = "",
    max_sentence_words: int = 20,
    subheading_gap: int = 250
) -> str:
    """
    AGGRESSIVE readability optimizer to pass Yoast SEO:
    - Splits ALL sentences > max_sentence_words (20 words)
    - Keeps ALL paragraphs ≤ max_paragraph_words (150 words)
    - Ensures transition words in 30%+ of sentences
    - Simplifies vocabulary
    - Reduces passive voice
    """
    if not content or not isinstance(content, str):
        return content

    # 1) Simplify vocabulary
    def simplify_vocab(text: str) -> str:
        def repl(m):
            w = m.group(0)
            low = w.lower()
            simple = SIMPLE_WORD_MAP.get(low)
            if not simple:
                return w
            return simple.capitalize() if w[0].isupper() else simple
        pat = re.compile(r'\b(' + '|'.join(map(re.escape, SIMPLE_WORD_MAP.keys())) + r')\b', re.IGNORECASE)
        return pat.sub(repl, text)

    text = simplify_vocab(content)

    # 2) Protect fenced code blocks
    code_blocks = []
    def _codeblock_repl(m):
        code_blocks.append(m.group(0))
        return f"[[[CODE_BLOCK_{len(code_blocks)-1}]]]"
    text = re.sub(r'```.*?```', _codeblock_repl, text, flags=re.DOTALL)

    # 3) AGGRESSIVE sentence splitting
    paragraphs = _split_paragraphs(text)
    processed: List[str] = []

    def split_sents(t: str) -> List[str]:
        """Split on sentence boundaries"""
        t = re.sub(r'\s+', ' ', t.strip())
        if not t:
            return []
        # Split on period, exclamation, question mark followed by space
        sents = re.split(r'(?<=[.!?])\s+(?=[A-Z])', t)
        return [s.strip() for s in sents if s.strip()]

    def split_long_sentence(sentence: str) -> List[str]:
        """AGGRESSIVELY split sentences over 20 words"""
        words = sentence.strip().split()
        if len(words) <= max_sentence_words:
            return [sentence.strip()]
        
        out = []
        breakers = {
            "and", "but", "because", "which", "that", "so", "while", 
            "when", "whereas", "although", "if", "unless", "since", "as"
        }
        
        idx = 0
        while idx < len(words):
            # Target chunk size
            target_end = min(idx + max_sentence_words, len(words))
            
            # Look for natural break points (conjunctions, relative pronouns)
            split_at = None
            for i in range(target_end - 1, idx + 10, -1):  # Don't make sentences too short
                if i < len(words) and words[i].lower().strip(",.;:") in breakers:
                    split_at = i
                    break
            
            # If no natural break, just split at max_sentence_words
            if split_at is None or split_at <= idx:
                split_at = target_end
            
            chunk = " ".join(words[idx:split_at]).strip()
            
            # Ensure proper punctuation
            if chunk and chunk[-1] not in ".!?":
                chunk += "."
            
            out.append(chunk)
            idx = split_at
        
        return out

    def add_transitions(sentences: List[str]) -> List[str]:
        """Add transition words to 30%+ of sentences"""
        if not sentences:
            return sentences
        
        result = []
        transitions = [
            "Additionally", "Moreover", "Furthermore", "However",
            "Therefore", "For example", "In addition", "Consequently",
            "Meanwhile", "Similarly", "In fact", "Notably",
            "First", "Second", "Finally", "Next", "Thus"
        ]
        t_idx = 0
        
        for i, s in enumerate(sentences):
            # Skip very short sentences and those already with transitions
            if i > 0 and len(_words(s)) > 8 and not _contains_transition(s):
                # Add transition to every 3rd sentence without one
                if i % 3 == 0:
                    trans = transitions[t_idx % len(transitions)]
                    # Make first letter lowercase if sentence started uppercase
                    if s and s[0].isupper():
                        s = f"{trans}, {s[0].lower()}{s[1:]}"
                    else:
                        s = f"{trans}, {s}"
                    t_idx += 1
            result.append(s)
        
        return result

    def rebuild_paragraphs(sentences: List[str]) -> List[str]:
        """Split into paragraphs with max 150 words each"""
        if not sentences:
            return []
        
        paras = []
        current_para = []
        current_word_count = 0
        
        for s in sentences:
            s_words = len(_words(s))
            
            # If adding this sentence exceeds limit, start new paragraph
            if current_word_count + s_words > max_paragraph_words and current_para:
                paras.append(" ".join(current_para).strip())
                current_para = [s]
                current_word_count = s_words
            else:
                current_para.append(s)
                current_word_count += s_words
        
        # Add remaining paragraph
        if current_para:
            paras.append(" ".join(current_para).strip())
        
        return paras

    # Process each paragraph
    for p in paragraphs:
        if _is_heading(p):
            processed.append(p)
            continue
        
        # Clean HTML for processing
        p_clean = re.sub(r'<[^>]+>', ' ', p)
        
        # Split into sentences
        sents = []
        for s in split_sents(p_clean):
            sents.extend(split_long_sentence(s))
        
        # Add transitions
        sents = add_transitions(sents)
        
        # Rebuild into paragraphs respecting word limit
        chunks = rebuild_paragraphs(sents)
        processed.extend(chunks)

    # 4) Insert subheadings
    with_h2 = _insert_h2_subheadings(processed, title=title, focus=focus_keyphrase, gap=subheading_gap)

    result = "\n\n".join(with_h2)

    # 5) FORCE minimum transition word percentage
    current_metrics = readability_metrics(result)
    if current_metrics["transition_word_percent"] < min_transition_percent:
        # More aggressive transition insertion
        all_sents = _split_sentences(result)
        needed_transitions = int((min_transition_percent / 100.0) * len(all_sents)) - int((current_metrics["transition_word_percent"] / 100.0) * len(all_sents))
        
        if needed_transitions > 0:
            transitions_cycle = [
                "Additionally", "Moreover", "Furthermore", "However",
                "Therefore", "For example", "In addition", "Consequently",
                "Meanwhile", "Similarly", "In fact", "Notably", "Thus"
            ]
            t_idx = 0
            added = 0
            
            for i in range(len(all_sents)):
                if added >= needed_transitions:
                    break
                
                if not _contains_transition(all_sents[i]) and len(_words(all_sents[i])) > 8:
                    trans = transitions_cycle[t_idx % len(transitions_cycle)]
                    s = all_sents[i]
                    if s and s[0].isupper():
                        all_sents[i] = f"{trans}, {s[0].lower()}{s[1:]}"
                    else:
                        all_sents[i] = f"{trans}, {s}"
                    t_idx += 1
                    added += 1
            
            result = " ".join(all_sents)

    # 6) Passive voice reduction
    def fix_simple_passives(text: str) -> str:
        irregular_map = {
            "written": "write", "given": "give", "taken": "take", "seen": "see",
            "shown": "show", "made": "make", "found": "find"
        }
        pat = re.compile(
            r'\b(?:was|were|is|are)\s+(\w+ed|' + '|'.join(irregular_map.keys()) + r')\b',
            flags=re.IGNORECASE
        )
        
        def repl(m):
            verb = m.group(1).lower()
            active = irregular_map.get(verb, verb.replace('ed', ''))
            return active
        
        return pat.sub(repl, text)

    result = fix_simple_passives(result)

    # 7) Restore code blocks
    for i, cb in enumerate(code_blocks):
        result = result.replace(f"[[[CODE_BLOCK_{i}]]]", cb)

    return result
def generate_focus_keyphrase(keywords: List[str], title: str) -> str:
    if not keywords:
        # Extract from title
        words = re.sub(r'[^\w\s]', '', title.lower()).split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
        meaningful = [w for w in words if w not in stop_words and len(w) > 3]
        return ' '.join(meaningful[:3]) if meaningful else title.lower()[:50]

    # Use first 2-3 keywords to create a phrase
    primary = keywords[0].strip()
    if len(primary.split()) >= 2:
        return primary.lower()
    if len(keywords) > 1:
        secondary = keywords[1].strip()
        keyphrase = f"{primary} {secondary}".lower()
        return keyphrase[:60]
    return primary.lower()


def generate_seo_title(title: str, keyphrase: str, max_length: int = 60) -> str:
    if title.lower().startswith(keyphrase.lower()):
        return title if len(title) <= max_length else title[:max_length - 3] + '...'

    keyphrase_title = keyphrase.title()
    remaining_length = max_length - len(keyphrase_title) - 3
    if remaining_length > 10:
        clean_title = re.sub(r'[^\w\s]', '', title).strip()
        words = clean_title.split()
        keyphrase_words = set(keyphrase.lower().split())
        unique_words = [w for w in words if w.lower() not in keyphrase_words]
        if unique_words:
            suffix = ' '.join(unique_words)[:remaining_length]
            return f"{keyphrase_title} - {suffix}"
    return keyphrase_title[:max_length]


def generate_meta_description(content: str, keyphrase: str, target_length: int = 155) -> str:
    paragraphs = content.split('\n\n')
    first_para = ""
    for para in paragraphs:
        clean = re.sub(r'[#*`[]', '', para).strip()
        if clean and len(clean) > 80 and not clean.startswith('http'):
            first_para = clean
            break

    if keyphrase and keyphrase.lower() in first_para.lower():
        meta = first_para
    else:
        meta = f"Discover {keyphrase}: {first_para}" if keyphrase else first_para

    meta = meta.strip()
    if len(meta) > target_length:
        # Prefer cutting at sentence or space boundary under limit
        trimmed = meta[:target_length]
        last_dot = trimmed.rfind('.')
        last_space = trimmed.rfind(' ')
        if last_dot >= target_length - 20:
            meta = trimmed[:last_dot + 1]
        elif last_space >= target_length - 20:
            meta = trimmed[:last_space] + '...'
        else:
            meta = trimmed.rstrip('. ') + '...'
    elif len(meta) < max(120, target_length - 35):
        extra = f" Learn more about {keyphrase}." if keyphrase else ""
        meta = (meta + extra).strip()
        if len(meta) > target_length:
            meta = meta[:target_length - 3].rstrip() + '...'
    return meta
def generate_slug(title: str, keyphrase: str) -> str:
    slug = slugify(keyphrase, max_length=50, separator='-')
    if len(slug) < 20:
        title_slug = slugify(title, max_length=60, separator='-')
        if slug not in title_slug:
            slug = f"{slug}-{title_slug}"[:60]
    return slug


def _count_occurrences(haystack: str, needle: str) -> int:
    if not needle:
        return 0
    pattern = re.compile(r'\b' + re.escape(needle.lower()) + r'\b')
    return len(pattern.findall(haystack.lower()))


def calculate_seo_score(
    title: str,
    content: str,
    keywords: List[str],
    meta_description: str = "",
    focus_keyphrase: str = ""
) -> Dict:
    # Basic counts
    metrics = readability_metrics(content)
    word_count = metrics["word_count"]
    sentences = metrics["sentence_count"]

    # Length score (10)
    if word_count >= 1600 and word_count <= 2200:
        length_score = 10
    elif word_count >= 1200:
        length_score = 8
    elif word_count >= 800:
        length_score = 6
    elif word_count > 500:
        length_score = 4
    else:
        length_score = 2

    # Title keyphrase (8)
    title_keyphrase_score = 8 if focus_keyphrase and focus_keyphrase.lower() in title.lower() else 0

    # Intro keyphrase (5)
    first_para = ""
    for p in _split_paragraphs(content):
        if not _is_heading(p):
            first_para = p
            break
    intro_keyphrase_score = 5 if focus_keyphrase and focus_keyphrase.lower() in first_para.lower() else 0

    # Keyword density (12) — sweet spot ~1.2% to 2.5%
    keyphrase_count = _count_occurrences(content, focus_keyphrase) if focus_keyphrase else 0
    keyword_density = (keyphrase_count / max(1, word_count)) * 100.0
    if 1.2 <= keyword_density <= 2.5:
        density_score = 12
    elif 0.8 <= keyword_density < 1.2 or 2.5 < keyword_density <= 3.2:
        density_score = 9
    elif 0.5 <= keyword_density < 0.8 or 3.2 < keyword_density <= 4.0:
        density_score = 6
    elif 0.2 <= keyword_density < 0.5 or 4.0 < keyword_density <= 5.0:
        density_score = 3
    else:
        density_score = 0

    # Meta description (8)
    meta_ok = False
    if meta_description:
        l = len(meta_description)
        meta_ok = (120 <= l <= 160) and (focus_keyphrase.lower() in meta_description.lower() if focus_keyphrase else True)
    meta_score = 8 if meta_ok else 0

    # Heading structure (8): at least 4 H2; 50% of H2 contain keyphrase or part of it
    h2s = re.findall(r'^\s*##\s+(.+)$', content, flags=re.MULTILINE)
    h2_count = len(h2s)
    if h2_count:
        h2_with_kw = 0
        if focus_keyphrase:
            for h in h2s:
                if focus_keyphrase.lower() in h.lower():
                    h2_with_kw += 1
        ratio = (h2_with_kw / h2_count) if h2_count else 0
    else:
        ratio = 0
    if h2_count >= 4 and ratio >= 0.5:
        heading_score = 8
    elif h2_count >= 3:
        heading_score = 6
    elif h2_count >= 2:
        heading_score = 4
    else:
        heading_score = 1 if h2_count >= 1 else 0

    # Outbound links (5)
    outbound_links = re.findall(r'\]\((https?://[^\s)]+)\)', content)
    outbound_count = len(outbound_links)
    if outbound_count >= 3:
        outbound_score = 5
    elif outbound_count == 2:
        outbound_score = 4
    elif outbound_count == 1:
        outbound_score = 3
    else:
        outbound_score = 0

    # Structure (8): bullets/numbered lists + subheadings
    list_lines = re.findall(r'^\s*[-*]\s+\w+', content, flags=re.MULTILINE)
    numbered = re.findall(r'^\s*\d+\.\s+\w+', content, flags=re.MULTILINE)
    h3s = re.findall(r'^\s*###\s+', content, flags=re.MULTILINE)
    structure_score = 0
    if h2_count >= 2:
        structure_score += 3
    if h3s:
        structure_score += 1
    if list_lines:
        structure_score += 2
    if numbered:
        structure_score += 2
    structure_score = min(structure_score, 8)

    # Readability (36) based on Yoast-like thresholds
    # Flesch (10)
    flesch = metrics["flesch_reading_ease"]
    if flesch >= 60:
        flesch_score = 10
    elif flesch >= 50:
        flesch_score = 8
    elif flesch >= 40:
        flesch_score = 5
    else:
        flesch_score = 2

    # Passive voice (6)
    pv = metrics["passive_voice_percent"]
    if pv <= 10:
        passive_score = 6
    elif pv <= 15:
        passive_score = 4
    elif pv <= 20:
        passive_score = 2
    else:
        passive_score = 0

    # Transition words (6)
    tw = metrics["transition_word_percent"]
    if tw >= 30:
        transition_score = 6
    elif tw >= 25:
        transition_score = 5
    elif tw >= 20:
        transition_score = 3
    else:
        transition_score = 1 if tw > 0 else 0

    # Long sentences (5)
    lsr = metrics["long_sentence_ratio"]
    if lsr <= 0.25:
        long_sentence_score = 5
    elif lsr <= 0.35:
        long_sentence_score = 3
    elif lsr <= 0.45:
        long_sentence_score = 2
    else:
        long_sentence_score = 0

    # Paragraph length (4)
    para_over = metrics["paragraphs_over_150_words"]
    if para_over == 0:
        paragraph_score = 4
    elif para_over == 1:
        paragraph_score = 2
    else:
        paragraph_score = 0

    # Consecutive sentence starters (2)
    runs = metrics["consecutive_sentence_runs"]
    if runs == 0:
        consecutive_score = 2
    elif runs == 1:
        consecutive_score = 1
    else:
        consecutive_score = 0

    # Word complexity (3)
    diff_ratio = metrics["difficult_words_ratio"]
    if diff_ratio <= 0.12:
        complexity_score = 3
    elif diff_ratio <= 0.18:
        complexity_score = 2
    else:
        complexity_score = 1

    readability_score = (
        flesch_score + passive_score + transition_score +
        long_sentence_score + paragraph_score + consecutive_score +
        complexity_score
    )  # max 36

    total_score = (
        length_score + title_keyphrase_score + intro_keyphrase_score +
        density_score + meta_score + heading_score + outbound_score +
        structure_score + readability_score
    )
    total_score = max(0, min(100, total_score))

    details = {
        "total_score": total_score,
        "length_score": length_score,
        "title_keyphrase_score": title_keyphrase_score,
        "intro_keyphrase_score": intro_keyphrase_score,
        "density_score": density_score,
        "keyword_density": round(keyword_density, 2),
        "meta_score": meta_score,
        "heading_score": heading_score,
        "outbound_score": outbound_score,
        "outbound_links": outbound_count,
        "structure_score": structure_score,
        "readability_score": readability_score,
        # Expose readability diagnostics (for your logs and suggestions)
        "readability": {
            **metrics
        },
    }
    return details


def suggest_improvements(details: Dict) -> List[str]:
    """Return actionable, prioritized suggestions based on scoring details."""
    sug = []
    rd = details.get("readability", {})

    # Passive voice
    pv = rd.get("passive_voice_percent", 0)
    if pv > 10:
        sug.append(f"Reduce passive voice to below 10% (currently {pv}%). Rewrite some sentences to active voice.")

    # Consecutive sentence starters
    runs = rd.get("consecutive_sentence_runs", 0)
    if runs >= 1:
        sug.append(f"Vary your sentence openings. Found {runs} run(s) where 3+ sentences start with the same word.")

    # Paragraph length
    para_over = rd.get("paragraphs_over_150_words", 0)
    if para_over > 0:
        sug.append(f"Split long paragraphs: {para_over} paragraph(s) exceed 150 words.")

    # Sentence length
    lsr = rd.get("long_sentence_ratio", 0.0) * 100
    if lsr > 25:
        sug.append(f"Shorten long sentences. {lsr:.1f}% of sentences exceed 20 words; aim for ≤ 25%.")

    # Transition words
    tw = rd.get("transition_word_percent", 0)
    if tw < 30:
        sug.append(f"Increase transition words to ≥ 30% of sentences (currently {tw}%). Add terms like 'Moreover', 'However', 'For example'.")

    # Flesch
    flesch = rd.get("flesch_reading_ease", 0)
    if flesch < 60:
        sug.append(f"Improve Flesch Reading Ease (currently {flesch}). Use shorter sentences and simpler words.")

    # Word complexity
    diff_ratio = rd.get("difficult_words_ratio", 0.0) * 100
    if diff_ratio > 12:
        sug.append(f"Simplify vocabulary. Difficult words make up {diff_ratio:.1f}% of words; aim for ≤ 12%.")

    # Headings
    if details.get("heading_score", 0) < 6:
        sug.append("Add more H2s and include the focus keyphrase in half of them if it fits naturally.")

    # Keyword density
    kd = details.get("keyword_density", 0.0)
    if kd < 1.0:
        sug.append(f"Increase focus keyphrase usage (density {kd:.2f}%). Aim for ~1.2–2.5% naturally.")
    elif kd > 3.2:
        sug.append(f"Lower focus keyphrase usage (density {kd:.2f}%). Avoid keyword stuffing; target ~1.2–2.5%.")

    # Outbound links
    if details.get("outbound_links", 0) < 2:
        sug.append("Add 1–2 outbound links to authoritative sources.")

    # Structure
    if details.get("structure_score", 0) < 6:
        sug.append("Use more bullet or numbered lists, and organize sections with H2/H3 subheadings.")

    return sug

def add_outbound_links(
    content: str,
    keywords: Optional[List[str]] = None,
    topic: Optional[str] = None,
    max_links: int = 3,
    sources: Optional[List[Tuple[str, str]]] = None,
    count: Optional[int] = None,
    limit: Optional[int] = None,
    avoid_anchor_terms: Optional[List[str]] = None,  # <-- NEW
    **kwargs,
) -> str:
    # existing compatibility
    if isinstance(count, int) and count > 0:
        max_links = count
    elif isinstance(limit, int) and limit > 0:
        max_links = limit
    elif isinstance(kwargs.get("n", None), int) and kwargs["n"] > 0:
        max_links = kwargs["n"]

    # Allow a single string for keywords
    if isinstance(keywords, str):
        keywords = [keywords]
    keywords = keywords or []
    avoid = {t.strip().lower() for t in (avoid_anchor_terms or []) if t and isinstance(t, str)}

    existing_links = re.findall(r'\]\((https?://[^\s)]+)\)', content)
    if len(existing_links) >= max_links:
        return content

    normalized_sources: List[Tuple[str, str]] = []
    if sources:
        for s in sources:
            if isinstance(s, tuple) and len(s) == 2:
                normalized_sources.append((s[0], s[1]))
            elif isinstance(s, dict) and "text" in s and "url" in s:
                normalized_sources.append((s["text"], s["url"]))

    # Build candidates
    lower_content = content.lower()
    predefined: List[Tuple[str, str]] = [
        ("machine learning", "https://en.wikipedia.org/wiki/Machine_learning"),
        ("deep learning", "https://en.wikipedia.org/wiki/Deep_learning"),
        ("neural network", "https://en.wikipedia.org/wiki/Artificial_neural_network"),
        ("natural language processing", "https://en.wikipedia.org/wiki/Natural_language_processing"),
        ("seo", "https://moz.com/learn/seo/what-is-seo"),
        ("keyword research", "https://moz.com/learn/seo/keyword-research"),
        ("python", "https://docs.python.org/3/"),
        ("pandas", "https://pandas.pydata.org/docs/"),
        ("numpy", "https://numpy.org/doc/"),
        ("tensorflow", "https://www.tensorflow.org/"),
        ("pytorch", "https://pytorch.org/"),
        ("docker", "https://docs.docker.com/"),
        ("kubernetes", "https://kubernetes.io/docs/home/"),
        ("aws", "https://docs.aws.amazon.com/"),
        ("azure", "https://learn.microsoft.com/azure/"),
        ("google cloud", "https://cloud.google.com/docs"),
        ("react", "https://react.dev/learn"),
        ("node.js", "https://nodejs.org/en/docs"),
    ]

    candidates: List[Tuple[str, str]] = []

    for kw in keywords[:4]:
        kw = kw.strip()
        if not kw or kw.lower() in avoid:
            continue
        wiki_url = f"https://en.wikipedia.org/wiki/{slugify(kw, separator='_')}"
        candidates.append((kw, wiki_url))

    for term, url in predefined:
        if term in lower_content and term.lower() not in avoid:
            candidates.append((term, url))

    if topic and isinstance(topic, str) and topic.strip() and topic.strip().lower() not in avoid:
        candidates.append((topic.strip(), f"https://en.wikipedia.org/wiki/{slugify(topic.strip(), separator='_')}"))

    candidates.extend(normalized_sources)

    # De-dupe and remove existing URLs
    existing_url_set = set(existing_links)
    seen_pairs = set()
    filtered: List[Tuple[str, str]] = []
    for term, url in candidates:
        key = (term.lower(), url)
        if url in existing_url_set or key in seen_pairs:
            continue
        seen_pairs.add(key)
        filtered.append((term, url))

    def _link_once_in_line(line: str, term: str, url: str) -> Tuple[str, bool]:
        if "[" in line or "](" in line:
            return line, False
        pat = re.compile(r'(?<!\w)(' + re.escape(term) + r')(?!\w)', flags=re.IGNORECASE)
        def repl(m):
            anchor = m.group(1)
            # FIXED: Clean markdown
            clean_anchor = re.sub(r'[*_~`]', '', anchor).strip().lower()
            if clean_anchor in avoid:  # avoid is set of lowercased terms
                return m.group(0)
            return f"[{anchor}]({url})"
        new_line, n = pat.subn(repl, line, count=1)
        return new_line, n > 0

    needed = max_links - len(existing_links)
    if needed <= 0 or not filtered:
        return content

    lines = content.splitlines()
    out_lines: List[str] = []
    code_fence = False
    links_added = 0
    remaining = filtered.copy()

    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("```"):
            code_fence = not code_fence
            out_lines.append(ln)
            continue
        if code_fence or stripped.startswith("#"):
            out_lines.append(ln)
            continue
        if links_added >= needed or not remaining:
            out_lines.append(ln)
            continue

        for i, (term, url) in enumerate(list(remaining)):
            new_ln, changed = _link_once_in_line(ln, term, url)
            if changed:
                ln = new_ln
                links_added += 1
                remaining.pop(i)
                break
        out_lines.append(ln)

    updated = "\n".join(out_lines)

    # Append "Further reading" if still short
    final_count = len(re.findall(r'\]\((https?://[^\s)]+)\)', updated))
    if final_count < max_links:
        if not re.search(r'^\s*##\s+Further\s+reading', updated, flags=re.IGNORECASE | re.MULTILINE):
            further: List[Tuple[str, str]] = []
            for term, url in remaining[: max_links - final_count]:
                further.append((f"{term.title()}", url))
            if further:
                updated = updated.rstrip() + "\n\n## Further reading\n" + "\n".join(
                    f"- [{t}]({u})" for t, u in further
                ) + "\n"

    return updated

def add_internal_links(
    content: str,
    pages=None,
    base_url: Optional[str] = None,
    max_links: int = 3,
    count: Optional[int] = None,
    limit: Optional[int] = None,
    avoid_anchor_terms: Optional[List[str]] = None,  # <-- NEW
    **kwargs,
) -> str:
    if isinstance(count, int) and count > 0:
        max_links = count
    elif isinstance(limit, int) and limit > 0:
        max_links = limit
    elif isinstance(kwargs.get("n", None), int) and kwargs["n"] > 0:
        max_links = kwargs["n"]
    if not content or max_links <= 0:
        return content
    
    def _is_http(u: str) -> bool:
        return isinstance(u, str) and (u.startswith("http://") or u.startswith("https://"))

    def _normalize_url(u: str) -> str:
        if not u:
            return ""
        u = str(u).strip()
        if _is_http(u):
            # If base_url is provided, keep only internal absolutes (but we won't strictly enforce)
            return u
        # relative path
        if base_url:
            b = base_url.rstrip("/")
            if not u.startswith("/"):
                u = "/" + u
            return b + u
        return u

    def _slug_to_title(sl: str) -> str:
        seg = sl.split("/")[-1]
        seg = seg.replace("-", " ").replace("_", " ").strip()
        seg = re.sub(r'\s+', ' ', seg)
        return seg.title() if seg else sl

    # Normalize pages → list of candidates with terms and urls
    candidates: List[Tuple[str, str]] = []  # (term, url)

    if pages:
        # Dict mapping {"Anchor": "/path"} → list
        if isinstance(pages, dict):
            pages = [(k, v) for k, v in pages.items()]

        if isinstance(pages, (list, tuple)):
            for item in pages:
                title = ""
                url = ""
                terms: List[str] = []

                if isinstance(item, dict):
                    url = item.get("url") or item.get("link") or item.get("href") or ""
                    title = item.get("title") or item.get("name") or item.get("text") or _slug_to_title(str(url))
                    kws = item.get("keywords") or item.get("tags") or []
                    if isinstance(kws, str):
                        kws = [kws]
                    terms.extend([k.strip() for k in kws if isinstance(k, str) and k.strip()])
                    if title:
                        terms.append(title)
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    title = str(item[0]) if item[0] else ""
                    url = str(item[1]) if item[1] else ""
                    terms.append(title or _slug_to_title(url))
                elif isinstance(item, str):
                    url = item
                    title = _slug_to_title(item)
                    terms.append(title)
                else:
                    continue

                url = _normalize_url(url)
                if not url:
                    continue

                # Clean and dedupe terms
                seen = set()
                clean_terms = []
                for t in terms:
                    t = re.sub(r'\s+', ' ', str(t)).strip()
                    low = t.lower()
                    if t and low not in seen and 2 <= len(low) <= 80:
                        seen.add(low)
                        clean_terms.append(t)

                for t in clean_terms:
                    candidates.append((t, url))

    if not candidates:
        return content
    avoid = {t.strip().lower() for t in (avoid_anchor_terms or []) if t and isinstance(t, str)}
    # Avoid lines that already contain links or headings / code fences
    def _link_once_in_line(line: str, term: str, url: str) -> Tuple[str, bool]:
        if "](" in line or "[" in line:
            return line, False
        pat = re.compile(r'(?<!\w)(' + re.escape(term) + r')(?!\w)', flags=re.IGNORECASE)
        def repl(m):
            anchor = m.group(1)
            # FIXED: Clean markdown
            clean_anchor = re.sub(r'[*_~`]', '', anchor).strip().lower()
            if clean_anchor in avoid:  # avoid is set of lowercased terms
                return m.group(0)
            return f"[{anchor}]({url})"
        new_line, n = pat.subn(repl, line, count=1)
        return new_line, n > 0

    lines = content.splitlines()
    out_lines: List[str] = []
    code_fence = False
    links_added = 0
    used_urls = set()

    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("```"):
            code_fence = not code_fence
            out_lines.append(ln)
            continue
        if code_fence or stripped.startswith("#"):
            out_lines.append(ln)
            continue
        if links_added >= max_links:
            out_lines.append(ln)
            continue

        changed = False
        for i, (term, url) in enumerate(list(candidates)):
            if url in used_urls:
                continue
            new_ln, ok = _link_once_in_line(ln, term, url)
            if ok:
                ln = new_ln
                links_added += 1
                used_urls.add(url)
                changed = True
                break
        out_lines.append(ln)

    updated = "\n".join(out_lines)

    # If nothing placed inline, append a small Related section
    if links_added == 0:
        remaining: List[Tuple[str, str]] = []
        seen = set()
        for term, url in candidates:
            if url in seen:
                continue
            seen.add(url)
            remaining.append((term if len(term.split()) <= 8 else term.split(" - ")[0], url))
            if len(remaining) >= max_links:
                break
        if remaining:
            updated = updated.rstrip() + "\n\n## Related articles\n" + "\n".join(
                f"- [{_slug_to_title(t)}]({u})" for t, u in remaining
            ) + "\n"

    return updated

def ensure_keyphrase_in_intro(
    content: str,
    focus_keyphrase: str,
    variants: Optional[List[str]] = None,
    bold: bool = False,
) -> str:
    """
    Ensure the first non-heading paragraph contains the exact `focus_keyphrase`.
    - If a variant (synonym) is present, replace one occurrence with the exact keyphrase.
    - Otherwise, append a short, natural sentence that includes the keyphrase.
    - Skips headings; preserves the rest of the content.
    """
    if not content or not isinstance(content, str):
        return content
    if not focus_keyphrase:
        return content

    fk = str(focus_keyphrase).strip()
    if not fk:
        return content

    # Find the first non-heading paragraph (same logic used in calculate_seo_score)
    first_para = None
    for p in _split_paragraphs(content):
        if not _is_heading(p):
            first_para = p
            break
    if not first_para:
        return content

    # Already present? Do nothing
    if fk.lower() in first_para.lower():
        return content

    # If variants are provided and present, replace one variant with the exact keyphrase
    if variants:
        for var in variants:
            v = str(var).strip()
            if not v:
                continue
            pat = re.compile(r'(?<!\w)(' + re.escape(v) + r')(?!\w)', flags=re.IGNORECASE)
            if pat.search(first_para):
                new_para = pat.sub(fk, first_para, count=1)
                return content.replace(first_para, new_para, 1)

    # Otherwise, append a natural sentence containing the keyphrase
    anchor = f"**{fk}**" if bold else fk
    new_para = first_para.rstrip()
    if not re.search(r'[.!?]"?\s*$', new_para):
        new_para += '.'
    new_para += f" In this guide, we focus on {anchor}."

    return content.replace(first_para, new_para, 1)

# --- NEW: Heading enforcement, density control, competing-link fix ---

def ensure_keyphrase_in_headings(
    content: str,
    keyphrase: str,
    synonyms: Optional[List[str]] = None,
    target_ratio: float = 0.6,      # 60% for Free
    max_changes: int = 5,           # Increased
    prefer_exact: bool = True
) -> str:
    """
    Ensure at least `target_ratio` of H2/H3 contain the keyphrase (or synonyms).
    We favor exact matches first to satisfy Yoast Free; then synonyms.
    """
    if not content or not keyphrase:
        return content

    lines = content.splitlines()
    h_idx = []  # indices of H2/H3 headings
    has_kp = []  # whether each H2/H3 contains keyphrase/syns
    syns = [s.strip() for s in (synonyms or []) if isinstance(s, str) and s.strip()]
    syns_l = {s.lower() for s in syns if s.lower() != keyphrase.lower()}

    for i, ln in enumerate(lines):
        m2 = re.match(r'^\s*##\s+(.+)$', ln)
        m3 = re.match(r'^\s*###\s+(.+)$', ln)
        if m2 or m3:
            txt = (m2 or m3).group(1).strip()
            incl = (keyphrase.lower() in txt.lower()) or any(s in txt.lower() for s in syns_l)
            h_idx.append(i)
            has_kp.append(incl)

    if not h_idx:
        return content

    need = int(len(h_idx) * target_ratio + 0.999)  # ceil
    have = sum(1 for x in has_kp if x)
    if have >= need:
        return content

    changes_left = max_changes
    # Add keyphrase/synonym to some headings that lack it
    for j, idx in enumerate(h_idx):
        if changes_left <= 0:
            break
        if has_kp[j]:
            continue
        if prefer_exact or not syns_l:
            lines[idx] = lines[idx].rstrip() + f" – {keyphrase}"
        else:
            # choose a synonym
            s = next(iter(syns_l))
            lines[idx] = lines[idx].rstrip() + f" – {s.title()}"
        changes_left -= 1
        have += 1
        if have >= need:
            break

    return "\n".join(lines)


def limit_keyphrase_density(
    content: str,
    keyphrase: str,
    target_min: float = 1.0,
    target_max: float = 1.5,  # Safe target (1.5% density)
    hard_cap: Optional[int] = None  # ← ADD THIS BACK!
) -> str:
    """
    Reduce keyphrase occurrences to stay within Yoast SEO limits.
    
    Args:
        content: The blog post content
        keyphrase: The focus keyphrase to limit
        target_min: Minimum target density percentage (default 1.0%)
        target_max: Maximum target density percentage (default 1.5%)
        hard_cap: Maximum allowed occurrences (auto-calculated if None)
    
    Returns:
        Content with reduced keyphrase density
    """
    if not content or not keyphrase:
        return content

    total_words = len(_words(content))
    if total_words == 0:
        return content

    # Auto-calculate hard cap based on Yoast's formula
    # Yoast uses ~1.5% as max for longer content
    if hard_cap is None:
        # Use 1.5% as absolute maximum
        hard_cap = int(total_words * 0.015)  # 1.5% of total words
        # Add small safety margin (reduce by 3 to stay safely under limit)
        hard_cap = max(1, hard_cap - 3)
    
    # Calculate allowed occurrences (use stricter of percentage or hard cap)
    allowed_by_percentage = int(total_words * (target_max / 100.0))
    allowed = min(hard_cap, allowed_by_percentage)
    
    # Count current occurrences
    current = _count_occurrences(content, keyphrase)
    
    # If within limits, no changes needed
    if current <= allowed:
        return content

    print(f"🔧 Keyphrase '{keyphrase}' appears {current} times (limit: {allowed} for {total_words} words). Reducing...")

    # Split content into lines for processing
    lines = content.splitlines()
    key_pat = re.compile(r'(?<!\w)(' + re.escape(keyphrase) + r')(?!\w)', flags=re.IGNORECASE)
    
    # Neutral replacement phrases (varied to maintain readability)
    replacements = [
        "this approach", 
        "this method", 
        "this solution", 
        "this technique",
        "it", 
        "the system",
        "the process",
        "this strategy",
        "the tool",
        "this concept"
    ]
    rep_idx = 0

    # Find index of first non-heading paragraph (we'll protect this)
    first_para_idx = None
    for i, ln in enumerate(lines):
        if ln.strip() and not ln.strip().startswith("#"):
            first_para_idx = i
            break

    # Calculate how many to remove
    extras = current - allowed
    removed_count = 0

    def repl(match):
        nonlocal rep_idx, extras, removed_count
        if extras <= 0:
            return match.group(0)
        
        # Get replacement phrase
        r = replacements[rep_idx % len(replacements)]
        rep_idx += 1
        
        # Preserve capitalization of original match
        text = r
        if match.group(0)[0].isupper():
            text = r[0].upper() + r[1:]
        
        extras -= 1
        removed_count += 1
        return text

    # Process each line
    out_lines = []
    code_fence = False
    
    for i, ln in enumerate(lines):
        s = ln.strip()
        
        # Track code fence state
        if s.startswith("```"):
            code_fence = not code_fence
            out_lines.append(ln)
            continue
        
        # Protect: code blocks, headings, and first paragraph
        if code_fence or s.startswith("#") or (first_para_idx is not None and i == first_para_idx):
            out_lines.append(ln)
            continue
        
        # Replace excess keyphrases in this line
        if extras > 0 and s:
            ln = key_pat.sub(repl, ln)
        
        out_lines.append(ln)

    result = "\n".join(out_lines)
    
    # Verify final count
    final_count = _count_occurrences(result, keyphrase)
    print(f"✅ Removed {removed_count} keyphrase occurrences. Final count: {final_count}/{allowed}")
    
    return result

def fix_competing_links(content: str, keyphrase: str, synonyms: Optional[List[str]] = None) -> str:
    if not content or not keyphrase:
        return content
    syns_l = {s.lower() for s in (synonyms or []) if s}
    
    avoid = {keyphrase.lower()}
    if synonyms:
        avoid.update(s.lower() for s in synonyms if isinstance(s, str))

    safe_anchors = ["this resource", "this guide", "learn more", "reference"]
    a_idx = 0

    def anchor_repl(m):
        nonlocal a_idx  # ← ADD THIS LINE TO FIX THE ERROR
        anchor = m.group(1)
        url = m.group(2)
        # FIXED: Clean markdown from anchor before checking
        clean_anchor = re.sub(r'[*_~`]', '', anchor).strip().lower()
        if (keyphrase.lower() in clean_anchor or 
            any(s in clean_anchor for s in syns_l)):
            rep = safe_anchors[a_idx % len(safe_anchors)]
            a_idx += 1
            if anchor[0].isupper():
                rep = rep[0].upper() + rep[1:]
            return f"[{rep}]({url})"
        return m.group(0)
    
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', anchor_repl, content)