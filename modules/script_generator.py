"""Script generator — Gemini-powered (primary) with template fallback.
Returns a list of scene paragraphs in HOOK → INTRO → BODY → OUTRO order."""
import logging
import random
import re

logger = logging.getLogger(__name__)


# ── Gemini prompt ─────────────────────────────────────────────

_PROMPT_TMPL = """You are a viral faceless-YouTube scriptwriter AND visual director.

Write a {content_type} script about: "{topic}"

LENGTH IS A HARD REQUIREMENT: write {target_words} words (±10%). The narration must run
about {seconds} seconds, so do NOT come up short — a too-short script ruins the video. If in
doubt, add another vivid body beat rather than ending early.

RETENTION ARC (this is the whole point — follow it exactly, in order):
    1. HOOK (paragraph 1, 1-2 sentences) — open a CURIOSITY GAP in the first 3 seconds:
       a bold, specific claim or question the viewer NEEDS answered. Do NOT answer it yet.
       (e.g. "Your body makes a decision 7 seconds before you do — and you never notice.")
    {intro_block}
    {body_block}
    FINAL. PAYOFF + ENGAGE (last paragraph) — close the curiosity gap with the satisfying
       answer, THEN end on a direct question to the viewer to spark comments
       (e.g. "So would you have guessed it? Tell me below.") + a soft subscribe if 60s or longer.

RETENTION RULES (what makes it engaging, not "newbie"):
- Every paragraph must END by pulling the viewer into the next one — an open loop, a "but
  here's the strange part", a cliffhanger. Never let a paragraph feel finished.
- Be SPECIFIC, not generic: real numbers, names, vivid concrete details. Specificity is what
  separates a pro script from a vague AI one. Avoid filler like "in this video" or "let's dive in".
- Write in second person ("you", "your"), short punchy sentences, spoken rhythm.
- One clear idea per paragraph, each a standalone visual scene.

STYLE:
- Voice: confident, curious, a little mysterious — Mr Beast pacing meets Netflix-documentary weight.
- Plain narration only — NO scene labels, headings, lists, or markdown.
- Each paragraph must work as BOTH spoken audio AND the on-screen subtitle.

For EACH paragraph also give a DISTINCT 5-7 word cinematic visual description (vary subject,
shot, and setting scene-to-scene so the video never looks like one repeated image).
Examples: "glowing neuron network dark blue void", "ancient ruins jungle golden sunset mist", "lone astronaut drifting above earth".

Return STRICT JSON in exactly this shape (no markdown, no commentary):
{{
  "paragraphs": [
    "First paragraph (the hook)...",
    "Second paragraph...",
    "..."
  ],
  "visual_plan": [
    "5-7 word cinematic image description for scene 1",
    "5-7 word cinematic image description for scene 2",
    "..."
  ]
}}

Topic: {topic}
Content type: {content_type}
Duration: {duration}
{viral_block}"""


def _build_prompt(topic: str, content_type: str, target_words: int, total_seconds: int,
                  duration_label: str, viral_context: dict | None = None) -> str:
    seconds = total_seconds

    if target_words <= 80:
        intro_block = ""
        body_block = "    2. BODY (1 paragraph, 2-3 sentences) — the single most surprising fact, twist, or insight"
    elif target_words <= 160:
        intro_block = "    2. INTRO (1 paragraph, 1-2 sentences) — preview what's coming, raise the stakes"
        body_block = ("    3. BODY (2 paragraphs, 2-3 sentences each) — "
                      "two key beats that build tension and pay off the hook")
    elif target_words <= 320:
        intro_block = "    2. INTRO (1 paragraph, 2 sentences) — preview what's coming"
        body_block = ("    3-7. BODY (4-5 paragraphs, 2-3 sentences each) — "
                      "key beats: setup, twist, revelation, escalation, climax")
    else:
        intro_block = "    2. INTRO (1 paragraph, 2-3 sentences) — preview + stakes"
        body_block = ("    3-8. BODY (6-7 paragraphs, 3-4 sentences each) — "
                      "deep narrative arc: setup, mystery, evidence, twist, revelation, climax, resolution")

    viral_block = ""
    if viral_context and isinstance(viral_context, dict):
        trigger   = viral_context.get("trigger", "")
        opening   = viral_context.get("opening", "")
        lead_fact = viral_context.get("lead_fact", "")
        if trigger or opening or lead_fact:
            viral_block = (
                f"\nVIRAL HOOK GUIDANCE (use this to inform your opening):\n"
                f"- Emotional trigger: {trigger}\n"
                f"- Proven opening pattern: {opening}\n"
                f"- Lead with this fact: {lead_fact}\n"
            )

    return _PROMPT_TMPL.format(
        topic=topic,
        content_type=content_type,
        target_words=target_words,
        seconds=seconds,
        duration=duration_label,
        intro_block=intro_block,
        body_block=body_block,
        viral_block=viral_block,
    )


# ── Topic normalisation (avoids "the truth about The truth about ...") ──

def _clean_subject(topic: str) -> str:
    """Turn a raw topic/title into a clean noun phrase for mid-sentence use.
    Drops a leading article so templates can add their own framing without
    producing duplicated words."""
    t = (topic or "").strip().rstrip(".!?").strip()
    t = re.sub(r"^(the|a|an)\s+", "", t, flags=re.IGNORECASE)
    return t or (topic or "this topic").strip()


def _subj_forms(topic: str) -> tuple[str, str]:
    """Return (lowercase-mid-sentence, Capitalised-sentence-start) subject forms."""
    subj = _clean_subject(topic)
    # lowercase the first letter for natural mid-sentence use, unless it's an acronym
    low = subj if subj[:3].isupper() else subj[:1].lower() + subj[1:]
    cap = subj[:1].upper() + subj[1:]
    return low, cap


# ── Template fallback (used only when Gemini is unavailable) ──
# Phrased so they read naturally for ANY topic, including full-sentence titles,
# and never wrap the subject in framing that could duplicate it.

_FALLBACK_STRUCTURE = {
    "Educational": {
        "hook": "Most people get {subj} completely wrong — and the real story is stranger than the myth.",
        "body": [
            "Start with the basics: there's far more to {subj} than almost anyone realizes at first.",
            "Here's what surprises people — the same underlying pattern shows up again and again, in places you'd never expect.",
            "And once it clicks, you start noticing {subj} everywhere. You can't switch that awareness back off.",
        ],
        "outro": "If this shifted how you see things, subscribe — there's a lot more where this came from.",
    },
    "Storytelling": {
        "hook": "Everything you've been told about {subj} leaves out the part that actually matters.",
        "body": [
            "It started with one question that didn't have a comfortable answer — and the closer anyone looked, the stranger it got.",
            "There was pushback. People wanted the simple version. But the real account was far too important to quietly bury.",
            "Put the pieces together and a clear pattern emerges — the kind you can't unsee once you've noticed it.",
        ],
        "outro": "Subscribe for the stories most channels won't touch.",
    },
}


def _template_fallback(topic: str, content_type: str, target_words: int) -> list[str]:
    subj, Subj = _subj_forms(topic)
    block = _FALLBACK_STRUCTURE.get(content_type, _FALLBACK_STRUCTURE["Educational"])

    def fmt(s: str) -> str:
        # sentence-start vs mid-sentence subject; supports {subj} and {Subj}
        return s.format(subj=subj, Subj=Subj)

    paragraphs = [fmt(block["hook"])]
    n_body = 1 if target_words <= 80 else (2 if target_words <= 160 else 3)
    for body in block["body"][:n_body]:
        paragraphs.append(fmt(body))
    paragraphs.append(fmt(block["outro"]))
    return paragraphs


# ── Public API ────────────────────────────────────────────────

_EXPAND_TMPL = """This faceless-YouTube script is TOO SHORT: it has {have} words but needs ~{target} words.
Expand it to about {target} words by adding more vivid, SPECIFIC detail and inserting 1-3 NEW body
paragraphs that deepen the story. Keep the existing strong lines, the same topic and voice, and the
hook -> escalating beats -> payoff -> viewer-question arc. Each paragraph must still pull into the next.

Return STRICT JSON (no markdown): {{"paragraphs": [...], "visual_plan": [...]}}
with one DISTINCT 5-7 word cinematic visual description per paragraph.

Topic: {topic}
Current paragraphs:
{joined}
"""


def _expand_script(paragraphs, visual_plan, topic, target_words, have):
    """Ask Gemini to lengthen a too-short script. Returns (paragraphs, visual_plan);
    keeps the original if expansion doesn't actually grow it."""
    from modules.gemini_client import generate_json
    prompt = _EXPAND_TMPL.format(have=have, target=target_words, topic=topic,
                                 joined="\n".join(f"- {p}" for p in paragraphs))
    data = generate_json(prompt)
    if isinstance(data, dict):
        paras = [p.strip() for p in data.get("paragraphs", [])
                 if isinstance(p, str) and len(p.strip()) > 10]
        vis = [v.strip() for v in data.get("visual_plan", [])
               if isinstance(v, str) and len(v.strip()) > 3]
        if paras and sum(len(p.split()) for p in paras) > have:
            return paras, (vis or visual_plan)
    return paragraphs, visual_plan


def generate_script(topic: str, content_type: str, total_seconds: int, target_words: int,
                    duration_label: str = "", viral_context: dict | None = None,
                    ) -> tuple[str, list[str], list[str]]:
    """Return (full_script_text, list_of_scene_paragraphs, visual_plan).
    viral_context: optional dict from trend_researcher with trigger/opening/lead_fact.
    """
    from modules.gemini_client import is_available, generate_json

    paragraphs: list[str] = []
    visual_plan: list[str] = []

    if is_available():
        try:
            prompt = _build_prompt(topic, content_type, target_words, total_seconds,
                                   duration_label, viral_context=viral_context)
            data = generate_json(prompt)
            if isinstance(data, dict):
                paras = data.get("paragraphs", [])
                vis   = data.get("visual_plan", [])
                paragraphs  = [p.strip() for p in paras if isinstance(p, str) and len(p.strip()) > 10]
                visual_plan = [v.strip() for v in vis  if isinstance(v, str) and len(v.strip()) > 3]
            if paragraphs:
                logger.info("Gemini script: %d paragraphs, %d visual descriptions",
                            len(paragraphs), len(visual_plan))
                # Enforce length — LLMs under-produce on longer targets. Expand once if short.
                have = sum(len(p.split()) for p in paragraphs)
                if have < target_words * 0.85:
                    logger.info("Script short (%d/%d words) — expanding", have, target_words)
                    paragraphs, visual_plan = _expand_script(
                        paragraphs, visual_plan, topic, target_words, have)
        except Exception as e:
            logger.warning("Gemini script generation failed, using template: %s", e)

    if not paragraphs:
        paragraphs  = _template_fallback(topic, content_type, target_words)
        visual_plan = []
        logger.info("Template-fallback script: %d paragraphs", len(paragraphs))

    full_text = "\n\n".join(paragraphs)
    return full_text, paragraphs, visual_plan
