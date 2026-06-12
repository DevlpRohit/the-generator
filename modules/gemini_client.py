"""Shared Gemini client — loads API key from .env, exposes generate_text and
generate_json helpers with retry + robust JSON extraction."""
import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Load .env once at import time
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except Exception:
    pass

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# Default model — fast, free-tier friendly, plenty smart for scripts/trends.
# Can be overridden per call. Tested working: gemini-2.0-flash, gemini-1.5-flash.
DEFAULT_MODEL = "gemini-flash-latest"

# When the primary model is overloaded (503, which happens a LOT on -latest),
# fall through to these so we keep real AI output instead of the template fallback.
FALLBACK_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash"]


def is_available() -> bool:
    return bool(API_KEY)


def _client():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in environment / .env")
    from google import genai
    return genai.Client(api_key=API_KEY)


def generate_text(prompt: str, model: str = DEFAULT_MODEL,
                  retries: int = 2, timeout: float = 60.0) -> str:
    """Send a single prompt to Gemini, return the text response.

    Tries the requested model first, then FALLBACK_MODELS, so a 503/overload on
    one model doesn't force the caller down to its template fallback.
    """
    models = [model] + [m for m in FALLBACK_MODELS if m != model]
    last_err = None
    for mdl in models:
        for attempt in range(retries + 1):
            try:
                c = _client()
                resp = c.models.generate_content(model=mdl, contents=prompt)
                text = (resp.text or "").strip()
                if text:
                    if mdl != model:
                        logger.info("Gemini succeeded on fallback model %s", mdl)
                    return text
                last_err = RuntimeError("Empty Gemini response")
            except Exception as e:
                last_err = e
                logger.warning("Gemini %s attempt %d failed: %s", mdl, attempt + 1, e)
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"Gemini failed after trying {models}: {last_err}")


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences if present."""
    t = text.strip()
    # ```json ... ```  or  ``` ... ```
    m = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", t, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _extract_json_payload(text: str) -> str:
    """Find the outermost JSON object/array in text."""
    t = _strip_json_fences(text)

    # Already pure JSON?
    if t.startswith("{") or t.startswith("["):
        return t

    # Else find first { ... } block by brace counting
    for start_char, end_char in (("{", "}"), ("[", "]")):
        i = t.find(start_char)
        if i == -1:
            continue
        depth = 0
        for j in range(i, len(t)):
            if t[j] == start_char:
                depth += 1
            elif t[j] == end_char:
                depth -= 1
                if depth == 0:
                    return t[i:j + 1]
    return t


def _repair_json(text: str) -> str:
    """Remove trailing commas before } and ]."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


def generate_json(prompt: str, model: str = DEFAULT_MODEL,
                  retries: int = 2) -> dict | list:
    """Send a prompt that should produce JSON. Returns parsed object."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            raw = generate_text(prompt, model=model, retries=0)
            payload = _extract_json_payload(raw)
            payload = _repair_json(payload)
            return json.loads(payload)
        except Exception as e:
            last_err = e
            logger.warning("Gemini JSON parse attempt %d failed: %s", attempt + 1, e)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Gemini JSON failed: {last_err}")
