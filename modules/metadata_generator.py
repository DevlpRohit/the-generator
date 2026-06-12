"""YouTube metadata generator — Gemini-powered (primary) with template fallback.

Also handles YouTube monetization-compliance metadata:
  - AI-disclosure line in the description (when visuals are photorealistic)
  - a ``requires_ai_disclosure`` flag for the Studio "altered content" toggle
  - de-templated, rotated fallback titles so uploads don't look mass-produced
"""
import json
import random
from datetime import datetime
from pathlib import Path


# ── AI disclosure (YouTube "altered or synthetic content" rule) ─

# Clearly stylized art generally does NOT need the disclosure; realistic/photoreal
# visuals that could be mistaken for real people or events DO. Unknown style → True (safe).
_STYLIZED_STYLES = {
    "Ghibli-Inspired", "Comic Book", "Cyberpunk/Neon",
    "Vintage", "Minimalist", "Nature & Calm",
}

_AI_DISCLOSURE_LINE = (
    "Disclosure: This video was made with AI-assisted tools. Some visuals and the "
    "narration voice were generated or enhanced with AI, under human direction and review."
)


def requires_ai_disclosure(style: str) -> bool:
    """Whether YouTube's 'altered or synthetic content' disclosure is recommended.

    Required for realistic/photorealistic AI visuals that a viewer could mistake for real
    people or events; not required for clearly stylized art. Unknown style → True (safe).
    """
    if not style:
        return True
    return style not in _STYLIZED_STYLES


def _with_disclosure(description: str, needs: bool) -> str:
    """Append the AI-disclosure line once, if disclosure is recommended."""
    if not needs or not description:
        return description
    if "ai-assisted" in description.lower() or "made with ai" in description.lower():
        return description
    return description.rstrip() + "\n\n" + _AI_DISCLOSURE_LINE


# ── Template fallback ─────────────────────────────────────────

_BROAD_TAGS = [
    "facts", "educational", "top 10", "explained",
    "documentary", "interesting", "must watch", "learn",
]

# Varied, advertiser-friendly patterns. Misleading clickbait ("you won't believe
# number 7") also hurts monetization, so these read straight. Rotated across uploads
# (see _pick_patterns / _remember_pattern) so videos don't look templated.
_TITLE_PATTERNS = [
    "{topic}: The {adj} Story Most People Never Hear",
    "What Really Happens With {topic}",
    "{topic}, Explained Clearly",
    "The Truth About {topic} (and Why It Matters)",
    "{num} Things About {topic} Worth Knowing",
    "How {topic} Actually Works",
    "{topic} — A Closer Look",
    "Understanding {topic} in {year}",
    "The {adj} Side of {topic}",
    "{topic}: What the Evidence Shows",
]

_ADJS  = ["Surprising", "Hidden", "Overlooked", "Untold", "Fascinating", "Lesser-Known"]
_TIMES = ["30 Days", "6 Months", "2 Years", "an Entire Decade"]
_NUMS  = ["5", "7", "10", "3", "9"]

# Rotation state so consecutive videos don't reuse the same title pattern.
_PATTERN_HISTORY = Path(__file__).parent.parent / "projects" / ".title_pattern_history.json"


def _recent_patterns(limit: int = 4) -> list[str]:
    try:
        data = json.loads(_PATTERN_HISTORY.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[-limit:]
    except Exception:
        pass
    return []


def _remember_pattern(pattern: str) -> None:
    try:
        hist = _recent_patterns(limit=20)
        hist.append(pattern)
        _PATTERN_HISTORY.parent.mkdir(exist_ok=True)
        _PATTERN_HISTORY.write_text(json.dumps(hist[-20:]), encoding="utf-8")
    except Exception:
        pass


def _pick_patterns() -> list[str]:
    """Order patterns so recently-used ones fall to the back (anti-templating)."""
    recent = _recent_patterns()
    fresh = [p for p in _TITLE_PATTERNS if p not in recent]
    stale = [p for p in _TITLE_PATTERNS if p in recent]
    random.shuffle(fresh)
    random.shuffle(stale)
    return fresh + stale


def _template_titles(topic: str) -> list[str]:
    adj  = random.choice(_ADJS)
    time = random.choice(_TIMES)
    num  = random.choice(_NUMS)
    year = datetime.now().year
    patterns = _pick_patterns()
    titles = [p.format(topic=topic, adj=adj, time=time, num=num, year=year)
              for p in patterns][:5]
    if patterns:
        _remember_pattern(patterns[0])
    return titles


def _template_description(topic: str, script_paragraphs: list[str],
                           total_seconds: int, titles: list[str]) -> str:
    dur_s = total_seconds
    year  = datetime.now().year
    best_title = titles[0]

    timestamps = ""
    if dur_s > 120 and script_paragraphs:
        secs_per_para = dur_s // len(script_paragraphs)
        stamps = []
        for i, para in enumerate(script_paragraphs[:6]):
            t = i * secs_per_para
            mm, ss = divmod(t, 60)
            heading = " ".join(para.split()[:4]) + "..."
            stamps.append(f"{mm:02d}:{ss:02d} — {heading}")
        timestamps = "\n\nTimestamps:\n" + "\n".join(stamps)

    summary_paras = script_paragraphs[1:4] if len(script_paragraphs) > 2 else script_paragraphs
    summary = "\n".join(" ".join(p.split()[:30]) + "..." for p in summary_paras[:3])

    related = [
        f"The History of {topic}", f"{topic} Explained Simply",
        f"Top 10 Facts About {topic}", f"Why {topic} Matters in {year}",
        f"The Future of {topic}",
    ]

    hashtags = " ".join(
        "#" + w.strip().replace(" ", "").lower()
        for w in (topic.split()[:3] + ["facts", "educational", "viral",
                                        "mindblowing", "truth", "subscribe"])
    )

    desc = f"""{best_title}

In this video, we dive deep into {topic} — revealing facts, insights, and discoveries that most people have never heard before.{timestamps}

What You'll Learn:
{summary}

Related Topics You'll Love:
{chr(10).join('→ ' + r for r in related)}

🔔 SUBSCRIBE & hit the bell icon for new videos every week
👍 LIKE this video if it expanded your mind
💬 COMMENT below — what was the most surprising fact?
📤 SHARE with someone who needs to see this

{hashtags}
"""
    return desc.strip()


def _template_tags(topic: str) -> list[str]:
    topic_words = [w.lower() for w in topic.split() if len(w) > 3]
    specific = list(dict.fromkeys(
        [f"{topic.lower()} facts", f"about {topic.lower()}",
         f"{topic.lower()} explained", f"{topic.lower()} truth",
         f"{topic.lower()} documentary"] + topic_words
    ))[:10]
    year = datetime.now().year
    pattern_tags = [
        f"{topic} {year}", f"{topic} explained", f"{topic} facts",
        f"{topic} viral", f"{topic} mind blowing",
        f"top 10 {topic.lower()}", f"best {topic.lower()}", f"why {topic.lower()}",
        f"{topic.lower()} story", f"incredible {topic.lower()}",
    ]
    all_tags = _BROAD_TAGS + specific + pattern_tags[:10]
    return list(dict.fromkeys(all_tags))[:30]


# ── Gemini-powered metadata ───────────────────────────────────

_META_PROMPT = """You are a YouTube SEO expert. Given this video script, generate optimized metadata.

Topic: {topic}
Duration: {duration}
Script excerpt:
{excerpt}

Return STRICT JSON (no markdown, no commentary):
{{
  "title_options": [
    "Title option 1 (under 70 chars, high CTR)",
    "Title option 2",
    "Title option 3",
    "Title option 4",
    "Title option 5"
  ],
  "description": "Full YouTube description (300-500 words). Include:\\n- Hook sentence\\n- What viewers will learn (3-5 bullet points)\\n- Timestamps if > 2 min\\n- Clear CTA (subscribe, like, comment)\\n- 3-5 relevant hashtags at end",
  "tags": ["tag1", "tag2", "tag3", "...30 tags total, most relevant first"]
}}
"""


def _gemini_metadata(topic: str, script_paragraphs: list[str], duration_label: str) -> dict | None:
    try:
        from modules.gemini_client import is_available, generate_json
        if not is_available():
            return None
        excerpt = "\n\n".join(script_paragraphs[:5])[:2000]
        prompt = _META_PROMPT.format(topic=topic, duration=duration_label, excerpt=excerpt)
        data = generate_json(prompt)
        if not isinstance(data, dict):
            return None
        titles = [t for t in data.get("title_options", []) if isinstance(t, str) and t.strip()]
        tags   = [t for t in data.get("tags", []) if isinstance(t, str) and t.strip()]
        desc   = data.get("description", "")
        if titles and desc and len(desc) > 100:
            return {
                "title_options": titles[:5],
                "best_title":    titles[0],
                "description":   desc.strip(),
                "tags":          tags[:30],
            }
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Gemini metadata failed: %s", e)
    return None


# ── Public API ────────────────────────────────────────────────

def generate_metadata(
    topic: str,
    script_paragraphs: list[str],
    output_path: str,
    total_seconds: int = 120,
    duration_label: str = "2m00s",
    style: str = "",
    synthetic_voice: bool = False,
) -> dict:
    result = _gemini_metadata(topic, script_paragraphs, duration_label)

    if not result:
        titles      = _template_titles(topic)
        description = _template_description(topic, script_paragraphs, total_seconds, titles)
        tags        = _template_tags(topic)
        result = {
            "title_options": titles,
            "best_title":    titles[0],
            "description":   description,
            "tags":          tags,
        }

    # AI-disclosure: add a description line for realistic styles OR a synthetic (cloned)
    # voice, and record whether the Studio "altered/synthetic content" toggle is needed.
    needs_disclosure = requires_ai_disclosure(style) or synthetic_voice
    result["description"] = _with_disclosure(result["description"], needs_disclosure)

    metadata = {
        **result,
        "topic":                  topic,
        "style":                  style,
        "duration":               duration_label,
        "requires_ai_disclosure": needs_disclosure,
        "generated_at":           datetime.now().isoformat(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata
