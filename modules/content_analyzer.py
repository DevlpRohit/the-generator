"""Content analyzer — Gemini reads the topic + script and recommends optimal
production settings: per-paragraph voice rate, subtitle preset, and music mood.

Called once after script generation. Results are injected into the pipeline so
every video's audio pacing, subtitle style, and background music automatically
fit the emotional tone of its content — without the user having to choose."""
import logging
import re

logger = logging.getLogger(__name__)


# ── Rule-based fallback tables ────────────────────────────────
# Used when Gemini is unavailable. Keyed by content_type.

_CT_VOICE_RATE = {
    "Horror":       -15,   # slow, ominous
    "Mystery":      -10,   # deliberate, suspenseful
    "Documentary":  -8,
    "History":      -5,
    "Educational":  0,
    "Storytelling": 0,
    "Sci-Fi":       +5,
    "Motivational": +12,   # energetic, driving
    "Comedy":       +18,   # snappy, upbeat
}

_CT_SUBTITLE = {
    "Horror":       "Neon Glow",
    "Mystery":      "Neon Glow",
    "Sci-Fi":       "Neon Glow",
    "Motivational": "Bold Yellow",
    "Comedy":       "Bold Yellow",
    "Educational":  "Clean White",
    "Documentary":  "Minimal",
    "History":      "Minimal",
    "Storytelling": "Clean White",
}

_CT_MUSIC = {
    "Horror":       "Dark/Suspense",
    "Mystery":      "Mystery",
    "Sci-Fi":       "Epic/Dramatic",
    "Motivational": "Uplifting",
    "Comedy":       "Uplifting",
    "Educational":  "Calm/Peaceful",
    "Documentary":  "Calm/Peaceful",
    "History":      "Epic/Dramatic",
    "Storytelling": "Mystery",
}


# ── Gemini prompt ─────────────────────────────────────────────

_ANALYZE_PROMPT = """You are a professional video sound director and post-production expert.
Analyze this video's content and return STRICT optimal production settings.

Topic: {topic}
Content Type: {content_type}
Visual Style: {style}
Script ({n} paragraphs total — first 4 shown):
{excerpt}

Return STRICT JSON (absolutely no markdown, no commentary outside the JSON):
{{
  "voice_rate_per_paragraph": ["+0%", "-8%", "+5%"],
  "subtitle_preset": "Clean White",
  "music_mood": "Calm/Peaceful",
  "reasoning": "one concise sentence"
}}

=== RULES ===

voice_rate_per_paragraph — MUST have exactly {n} entries, one per paragraph:
- Values must be strings like "+0%", "-12%", "+8%". Range: -25% to +25%.
- Paragraph 1 (HOOK): slow down -8% to -15% so the opening lands with weight.
- High-tension / revelation lines: slow -5% to -12% for drama.
- Fast-paced / energetic / action lines: speed up +5% to +15%.
- Question paragraphs ("why?", "what if?"): slow slightly -3% to -8%.
- Outro / CTA paragraph: slow -5% to -8% for warmth and intimacy.
- Vary the values meaningfully — identical rates on every paragraph is wrong.

subtitle_preset — pick exactly one:
- "Neon Glow"    → dark / horror / mystery / sci-fi / cyberpunk topics
- "Bold Yellow"  → motivational / comedy / hype / action / high-energy topics
- "Minimal"      → documentary / history / calm / educational / academic topics
- "Clean White"  → general / storytelling / balanced topics

music_mood — pick exactly one:
- "None"           → only if content is explicitly silent/ambient
- "Dark/Suspense"  → horror, true crime, dark history
- "Mystery"        → mystery, conspiracy, unknown phenomena
- "Epic/Dramatic"  → sci-fi, space, history, revelations, big claims
- "Uplifting"      → motivational, success, self-improvement, comedy
- "Calm/Peaceful"  → meditation, nature, gentle education, wellness
- If current_music_mood is not "None", keep it (respect user choice): {current_mood}
"""


def _pct_str(n: int) -> str:
    return f"+{n}%" if n >= 0 else f"{n}%"


def _rule_based_rates(paragraphs: list[str], base_bps: int) -> list[str]:
    """Generate per-paragraph voice rates without Gemini."""
    rates = []
    total = len(paragraphs)
    for i, para in enumerate(paragraphs):
        words = para.split()
        wc = len(words)
        is_question = "?" in para
        is_exclamation = para.count("!") >= 2
        is_short = wc < 20         # punchy line — slow for impact
        is_long = wc > 55          # exposition — slight speed-up

        if i == 0:                          # hook — always slow for weight
            delta = -10
        elif i == total - 1:               # outro — slow for warmth
            delta = -6
        elif is_question and not is_exclamation:
            delta = -6
        elif is_exclamation:               # hype / reveal
            delta = +8
        elif is_short:                     # short punchy line
            delta = -5
        elif is_long:                      # long exposition
            delta = +4
        else:
            delta = 0

        final = max(-25, min(25, base_bps + delta))
        rates.append(_pct_str(final))
    return rates


def analyze_content(
    topic: str,
    content_type: str,
    style: str,
    paragraphs: list[str],
    current_music_mood: str = "None",
) -> dict:
    """Analyze topic + script and return optimal production settings.

    Returns:
        voice_rate_per_paragraph : list[str]  — one rate string per paragraph
        subtitle_preset          : str        — one of the four preset names
        music_mood               : str        — recommended music mood
    """
    n = len(paragraphs)
    base_bps = _CT_VOICE_RATE.get(content_type, 0)

    # ── Try Gemini first ──────────────────────────────────────
    try:
        from modules.gemini_client import is_available, generate_json
        if is_available():
            excerpt = "\n\n".join(
                f"[{i+1}] {p}" for i, p in enumerate(paragraphs[:4])
            )[:2000]
            prompt = _ANALYZE_PROMPT.format(
                topic=topic, content_type=content_type, style=style,
                excerpt=excerpt, n=n, current_mood=current_music_mood,
            )
            data = generate_json(prompt)
            if isinstance(data, dict):
                raw_rates = data.get("voice_rate_per_paragraph", [])
                rates = [r.strip() for r in raw_rates
                         if isinstance(r, str) and re.match(r"^[+-]?\d+%$", r.strip())]
                # Pad or trim to exactly n entries
                overall = _pct_str(base_bps)
                while len(rates) < n:
                    rates.append(overall)
                rates = rates[:n]

                preset = data.get("subtitle_preset", "Clean White")
                if preset not in ("Clean White", "Bold Yellow", "Neon Glow", "Minimal"):
                    preset = _CT_SUBTITLE.get(content_type, "Clean White")

                mood = data.get("music_mood", "None")
                # Respect user's explicit choice unless they selected "Auto"
                if current_music_mood and current_music_mood not in ("None", "Auto"):
                    mood = current_music_mood
                if mood not in ("None", "Epic/Dramatic", "Calm/Peaceful",
                                "Dark/Suspense", "Uplifting", "Mystery"):
                    mood = _CT_MUSIC.get(content_type, "Calm/Peaceful")

                logger.info(
                    "Content analysis complete — subtitle=%s, mood=%s, rates=%s",
                    preset, mood, rates,
                )
                return {
                    "voice_rate_per_paragraph": rates,
                    "subtitle_preset":          preset,
                    "music_mood":               mood,
                }
    except Exception as exc:
        logger.warning("Gemini content analysis failed (%s) — using rule-based fallback", exc)

    # ── Rule-based fallback ───────────────────────────────────
    rates  = _rule_based_rates(paragraphs, base_bps)
    preset = _CT_SUBTITLE.get(content_type, "Clean White")
    mood   = (current_music_mood
              if current_music_mood not in ("None", "Auto")
              else _CT_MUSIC.get(content_type, "Calm/Peaceful"))

    logger.info(
        "Rule-based content analysis — subtitle=%s, mood=%s, base_rate=%s%%",
        preset, mood, base_bps,
    )
    return {
        "voice_rate_per_paragraph": rates,
        "subtitle_preset":          preset,
        "music_mood":               mood,
    }
