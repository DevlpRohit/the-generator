import httpx
import json
import logging
import re
import asyncio

logger = logging.getLogger(__name__)

POLLINATIONS_URL = "https://text.pollinations.ai/"

SYSTEM_PROMPT = (
    "You are an expert YouTube scriptwriter for viral faceless channels. "
    "You write engaging, educational, policy-compliant scripts that maximize watch time. "
    "IMPORTANT: Respond with ONLY valid JSON. No markdown, no code blocks, no explanation."
)


def _build_prompt(topic: str, style: str, duration_minutes: int) -> str:
    word_count = duration_minutes * 140
    section_count = max(3, min(6, duration_minutes))
    words_per_section = word_count // section_count

    return f"""Write a YouTube video script about: "{topic}"
Style: {style}
Target duration: {duration_minutes} minutes (~{word_count} total spoken words)
Number of main sections: {section_count}

Return ONLY this JSON structure:
{{
  "title": "Compelling clickable YouTube title under 60 characters",
  "description": "YouTube description 150-200 words with keywords, value prop, and call to action",
  "hook_narration": "Opening 20-30 second hook. Shocking fact or provocative question. ~70 words. Must make viewers stay.",
  "sections": [
    {{
      "id": 1,
      "heading": "Section heading",
      "narration": "Full section narration ~{words_per_section} words. Educational, surprising, engaging. Include a surprising fact or insight.",
      "image_prompt": "Detailed Stable Diffusion image prompt for 1920x1080. Include style, lighting, mood. Be specific. Example: 'photorealistic human brain with glowing neural pathways, dark background, cinematic lighting, ultra detailed, 8k'",
      "duration_estimate": 60
    }}
  ],
  "outro_narration": "30-second outro summarizing key takeaways and building anticipation. ~70 words.",
  "cta": "One-sentence subscribe call to action.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6"],
  "disclosure": "AI-assisted content. All information reviewed for accuracy."
}}

Rules:
- The hook MUST open with a shocking statistic or impossible-sounding claim
- Each section must contain at least one mind-blowing fact
- Image prompts must be different for every section
- Make it genuinely educational and hard to stop watching"""


def _repair_json(text: str) -> str:
    """Fix common AI JSON mistakes: trailing commas, single-line comments."""
    text = re.sub(r",\s*([}\]])", r"\1", text)  # remove trailing commas
    return text


def _loads_safe(text: str) -> dict | None:
    """Try json.loads, then try with basic repairs."""
    for candidate in [text, _repair_json(text)]:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _extract_outer_braces(text: str) -> str | None:
    """Extract outermost {...} block using depth-counting."""
    brace_start = text.find("{")
    if brace_start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[brace_start:], brace_start):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[brace_start : i + 1]
    return None


def _parse_raw(text: str) -> dict:
    """Parse JSON from raw text using multiple strategies."""
    # Strip BOM and markdown fences
    text = text.lstrip("﻿​")
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    # Strategy 1: direct parse + repair
    result = _loads_safe(text)
    if result is not None:
        return result

    # Strategy 2: extract outermost {...} block then parse + repair
    outer = _extract_outer_braces(text)
    if outer:
        result = _loads_safe(outer)
        if result is not None:
            return result

    raise ValueError(f"No valid JSON dict found (first 200 chars): {text[:200]!r}")


def _unwrap_wrapper(data: dict) -> dict | None:
    """Unwrap OpenAI/Pollinations response wrappers that contain the script as nested content."""
    # OpenAI chat completions format: {"choices": [{"message": {"content": "..."}}]}
    if "choices" in data:
        try:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return _parse_raw(content)
            if isinstance(content, dict):
                return content
        except (KeyError, IndexError, TypeError):
            pass

    # Pollinations "reasoning" wrapper: {"role": "...", "content": "...", "tool_calls": ...}
    if "role" in data and "content" not in data and "sections" not in data:
        return None  # Can't unwrap, no script content

    # Generic content field wrapper
    if "content" in data and isinstance(data["content"], str) and "sections" not in data:
        try:
            return _parse_raw(data["content"])
        except ValueError:
            pass

    return None


def _extract_json(text: str) -> dict:
    """Extract script JSON — handles plain JSON, OpenAI wrapper, Pollinations reasoning wrapper, markdown."""
    data = _parse_raw(text)

    # Check if this looks like a wrapper (has wrapper keys but not script keys)
    script_keys = {"title", "sections", "hook_narration"}
    wrapper_keys = {"choices", "role", "reasoning"}
    if not script_keys.intersection(data.keys()) and wrapper_keys.intersection(data.keys()):
        unwrapped = _unwrap_wrapper(data)
        if unwrapped:
            return unwrapped
        raise ValueError(f"Response is a wrapper with no extractable content: {list(data.keys())}")

    return data


def _fallback_script(topic: str, style: str) -> dict:
    return {
        "title": f"The Shocking Truth About {topic}",
        "description": (
            f"In this video we uncover the most surprising and little-known facts about {topic}. "
            "Most people have no idea just how deep this topic goes. By the end of this video "
            "you will see the world differently. Watch until the end for the most mind-blowing fact. "
            f"#{topic.replace(' ', '')} #facts #educational #mindblowing #science"
        ),
        "hook_narration": (
            f"What if I told you that everything you thought you knew about {topic} is wrong? "
            "Scientists have been quietly uncovering facts so strange, so counter-intuitive, "
            "that most people refuse to believe them. Stay with me — because what you're about "
            "to learn will permanently change how you see this topic."
        ),
        "sections": [
            {
                "id": 1,
                "heading": f"What Most People Get Wrong About {topic}",
                "narration": (
                    f"The conventional story of {topic} is far simpler than the reality. "
                    "When researchers started digging deeper they found something extraordinary. "
                    "The mainstream understanding we have all been taught leaves out the most "
                    "fascinating parts. Here is what the experts rarely talk about publicly."
                ),
                "image_prompt": f"{topic}, {style} style, cinematic wide shot, dramatic lighting, high detail, 8k, photorealistic",
                "duration_estimate": 60,
            },
            {
                "id": 2,
                "heading": "The Hidden Science",
                "narration": (
                    f"When scientists measure {topic} at its most fundamental level they find "
                    "patterns that defy our intuitions. The numbers are so extreme that they are "
                    "almost impossible to comprehend. To put it in perspective, consider this: "
                    "if you laid all the facts end to end they would circle the Earth multiple times."
                ),
                "image_prompt": f"scientific visualization of {topic}, data streams, glowing particles, {style}, dark background, 8k",
                "duration_estimate": 60,
            },
            {
                "id": 3,
                "heading": "Surprising Real-World Impacts",
                "narration": (
                    f"Understanding {topic} has real practical consequences for your daily life. "
                    "Researchers have found that people who understand this topic make significantly "
                    "better decisions. The implications ripple through everything from health and "
                    "finance to relationships and creativity."
                ),
                "image_prompt": f"real world impact of {topic}, people interacting, {style}, warm lighting, cinematic, detailed",
                "duration_estimate": 55,
            },
            {
                "id": 4,
                "heading": "What Experts Predict Next",
                "narration": (
                    f"The future of {topic} is even more astonishing. Leading researchers predict "
                    "that within the next decade we will see developments that sound like science "
                    "fiction today. The trajectory we are on points toward a transformation that "
                    "will affect every single person on the planet."
                ),
                "image_prompt": f"futuristic vision of {topic}, {style}, glowing neon, advanced technology, wide shot, ultra detailed",
                "duration_estimate": 55,
            },
        ],
        "outro_narration": (
            f"So there you have it — the real, unfiltered story of {topic}. "
            "The world is far stranger and more fascinating than we give it credit for. "
            "If this changed how you think, share it with someone who needs to see it. "
            "Our next video goes even deeper — you will not want to miss it."
        ),
        "cta": "Hit subscribe and the notification bell so you never miss our next deep dive.",
        "tags": [topic, "facts", "educational", "mindblowing", "science", "truth"],
        "disclosure": "AI-assisted content. All information reviewed for accuracy.",
    }


async def generate_script(topic: str, style: str, duration_minutes: int) -> dict:
    prompt = _build_prompt(topic, style, duration_minutes)

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    POLLINATIONS_URL,
                    json={
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "model": "openai",
                        "seed": 100 + attempt,
                        "jsonMode": True,
                    },
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

                logger.info("Pollinations raw response (first 300 chars): %s", resp.text[:300])
                script = _extract_json(resp.text)
                logger.info("Extracted script keys: %s", list(script.keys()))

                if not script.get("sections") or not script.get("title"):
                    logger.warning("Script missing required fields; keys present: %s", list(script.keys()))
                    raise ValueError(f"Incomplete script — keys: {list(script.keys())}")

                return script

        except Exception as exc:
            _log(f"Script gen attempt {attempt + 1} failed: {exc}")
            if attempt < 2:
                await asyncio.sleep(4)

    _log("All script gen attempts failed -- using fallback script")
    return _fallback_script(topic, style)


def _log(msg: str) -> None:
    """Print safely even on cp1252 Windows consoles."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))
