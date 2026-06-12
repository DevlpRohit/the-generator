"""Trend research — Gemini-powered (primary) with pytrends+YouTube scrape fallback."""
import logging
import random

logger = logging.getLogger(__name__)


_FALLBACK_TOPICS = [
    "The hidden science of sleep", "Why the economy is changing fast",
    "The truth about social media algorithms", "Ancient mysteries still unsolved",
    "How AI is replacing jobs", "The psychology of decision making",
    "Lost civilizations discovered", "The future of money and crypto",
    "Why people are leaving cities", "The science of longevity",
    "Mind-blowing space discoveries", "The dark side of fast fashion",
    "Why willpower is a myth", "The real story behind famous brands",
]


# ── Gemini-powered research ───────────────────────────────────

_GEMINI_PROMPT = """You are a YouTube trend researcher specializing in faceless video channels.

{niche_line}For the keyword: "{keyword}"

Return 8 SPECIFIC, currently-trending faceless-YouTube video topic ideas
related to this {scope}. These should be the kind of topics that are getting
millions of views right now on channels like Veritasium, Kurzgesagt,
Mr Beast, Lemmino, Joe Scott, etc.

Also return 8 viral CLICKABLE title suggestions in different proven styles:
- shocking truth / hidden truth
- numbered list ("7 things", "10 facts")
- question hook ("Why X?", "What if Y?")
- contrarian ("Everything you know about X is wrong")
- mystery ("The strange case of X")
- I-tried format ("I studied X for 30 days")

Finally, for each topic, analyse what kind of HOOK structure makes it go viral:
- The emotional trigger (curiosity / fear / awe / inspiration / controversy)
- The best opening line pattern
- The key surprising fact to lead with

Return STRICT JSON in this exact shape, no markdown:
{{
  "trending_topics": ["topic 1", "topic 2", ..., "topic 8"],
  "title_suggestions": ["title 1", "title 2", ..., "title 8"],
  "viral_hooks": [
    {{"topic": "topic 1", "trigger": "curiosity", "opening": "What if I told you...", "lead_fact": "The surprising fact"}},
    ...
  ]
}}
"""


def _gemini_research(keyword: str, niche: str = "") -> dict | None:
    from modules.gemini_client import is_available, generate_json
    if not is_available():
        return None
    try:
        niche_line = f"Niche: {niche}\n" if niche and niche != keyword else ""
        scope = "niche" if niche else "topic"
        prompt = _GEMINI_PROMPT.format(keyword=keyword, niche_line=niche_line, scope=scope)
        data = generate_json(prompt)
        if not isinstance(data, dict):
            return None
        topics      = [t for t in data.get("trending_topics", []) if isinstance(t, str)]
        titles      = [t for t in data.get("title_suggestions", []) if isinstance(t, str)]
        viral_hooks = data.get("viral_hooks", [])
        if not isinstance(viral_hooks, list):
            viral_hooks = []
        if topics:
            logger.info("Gemini trends: %d topics, %d titles, %d hooks",
                        len(topics), len(titles), len(viral_hooks))
            return {"trending_topics": topics[:10], "title_suggestions": titles[:10],
                    "viral_hooks": viral_hooks[:10]}
    except Exception as e:
        logger.warning("Gemini trend research failed: %s", e)
    return None


# ── Fallback: pytrends + YouTube scrape ───────────────────────

def _pytrends_results(keyword: str) -> list[str]:
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="en-US", tz=360, timeout=(5, 15))
        pt.build_payload([keyword], timeframe="today 1-m", geo="US")
        related = pt.related_queries()
        if keyword in related and related[keyword].get("top") is not None:
            rows = related[keyword]["top"]["query"].tolist()
            return [f"{keyword}: {r}" for r in rows[:10]]
    except Exception as e:
        logger.warning("pytrends error: %s", e)
    return []


def _youtube_titles() -> list[str]:
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
        r = requests.get("https://www.youtube.com/feed/trending", headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        titles = [el.get_text(strip=True) for el in soup.select("a#video-title")]
        return titles[:10]
    except Exception as e:
        logger.warning("YouTube scrape error: %s", e)
    return []


# ── Public API ────────────────────────────────────────────────

def research_topic(keyword: str, niche: str = "") -> dict:
    # Try Gemini first
    gemini = _gemini_research(keyword, niche=niche)
    if gemini:
        return {"keyword": keyword, "niche": niche, **gemini}

    # Fallback chain
    topics = _pytrends_results(keyword) + _youtube_titles()
    topics = list(dict.fromkeys(topics))
    if not topics:
        topics = random.sample(_FALLBACK_TOPICS, min(8, len(_FALLBACK_TOPICS)))

    import datetime
    year = datetime.datetime.now().year
    rewrites: list[str] = []
    for t in topics[:5]:
        rewrites += [
            f"The Shocking Truth About {t}",
            f"Why {t} Is Changing Everything in {year}",
        ]

    return {
        "keyword": keyword,
        "trending_topics": topics[:10],
        "title_suggestions": rewrites[:10],
    }
