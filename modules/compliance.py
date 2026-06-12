"""Pre-publish monetization compliance gate.

Reads a finished project folder and returns a checklist verdict used to gate the
YouTube upload. Critical failures block upload (overridable with an explicit force);
warnings are advisory. Ties together the signals added across Milestone 3:
edited_by_human, requires_ai_disclosure, word count, image variety, niche risk.
"""
import hashlib
import json
import re
from pathlib import Path

from config import PROJECTS_DIR, DURATION_SECONDS, RISKY_NICHES
from modules.metadata_generator import requires_ai_disclosure


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _total_seconds(settings: dict, meta: dict) -> int:
    """Best-effort target duration in seconds across old/new settings formats."""
    if "duration_min" in settings or "duration_sec" in settings:
        try:
            return max(10, int(settings.get("duration_min", 0) or 0) * 60
                            + int(settings.get("duration_sec", 0) or 0))
        except Exception:
            pass
    label = str(settings.get("duration") or meta.get("duration") or "")
    if label in DURATION_SECONDS:
        return DURATION_SECONDS[label]
    m = re.match(r"(?:(\d+)m)?(\d+)s", label)          # e.g. "2m00s" / "30s"
    if m:
        return max(10, int(m.group(1) or 0) * 60 + int(m.group(2) or 0))
    return 120


def _unique_image_count(folder: Path) -> tuple[int, int]:
    """(total scene assets, distinct-by-content) — catches repeated fallback frames.

    Counts final scene assets — images (scene_01.png) AND B-roll clips (scene_01.mp4) —
    not the generator's intermediate artifacts (scene_01_ai_ai.png, *_px.jpg, …).
    """
    files = sorted(p for p in folder.glob("scene_*")
                   if re.fullmatch(r"scene_\d+\.(png|mp4)", p.name))
    hashes = set()
    for f in files:
        try:
            hashes.add(hashlib.md5(f.read_bytes()).hexdigest())
        except Exception:
            pass
    return len(files), len(hashes)


def _trigram_uniqueness(text: str) -> float:
    words = re.findall(r"\w+", text.lower())
    if len(words) < 6:
        return 1.0
    grams = [tuple(words[i:i + 3]) for i in range(len(words) - 2)]
    return len(set(grams)) / len(grams)


def _recent_titles(exclude: str) -> list[str]:
    out = []
    try:
        for d in PROJECTS_DIR.iterdir():
            if not d.is_dir() or d.name == exclude:
                continue
            t = (_load_json(d / "metadata.json").get("best_title") or "").strip().lower()
            if t:
                out.append(t)
    except Exception:
        pass
    return out


def evaluate(folder_name: str) -> dict:
    """Return a compliance report for a finished project folder."""
    folder   = PROJECTS_DIR / folder_name
    meta     = _load_json(folder / "metadata.json")
    settings = _load_json(folder / "settings.json")
    try:
        script = (folder / "script.txt").read_text(encoding="utf-8")
    except Exception:
        script = ""

    style  = settings.get("style") or meta.get("style") or ""
    checks: list[dict] = []

    def add(cid, label, ok, detail, critical=False):
        checks.append({
            "id": cid, "label": label, "pass": bool(ok),
            "detail": detail, "severity": "critical" if critical else "warn",
        })

    # 1 ── Human input (the #1 anti-"AI slop" signal) — CRITICAL
    # Any of: edited the script, added an original-commentary scene, or used a
    # real recorded voiceover.
    edited      = bool(settings.get("edited_by_human"))
    commentary  = bool((settings.get("commentary") or "").strip())
    voiceover   = bool(settings.get("human_voiceover"))
    has_human   = edited or commentary or voiceover
    if voiceover:
        h_detail = "Human voiceover supplied (real recorded narration)."
    elif commentary:
        h_detail = "Original commentary added by the creator."
    elif edited:
        h_detail = "Script was reviewed and edited by a human."
    else:
        h_detail = ("No human input detected — edit the script, add commentary, or upload a "
                    "voiceover (Monetization-Safe Mode).")
    add("human_input", "Human input on the video", has_human, h_detail, critical=True)

    # 2 ── Substantial length (thin content gets demonetized) — CRITICAL
    secs      = _total_seconds(settings, meta)
    target    = int(secs * 2.5)
    min_words = max(40, int(target * 0.55))
    words     = len(script.split())
    add("length", "Substantial length", words >= min_words,
        f"{words} words (need ≥ {min_words} for ~{secs}s).",
        critical=True)

    # 3 ── Valid metadata — CRITICAL
    title = (meta.get("best_title") or "").strip()
    desc  = (meta.get("description") or "").strip()
    tags  = meta.get("tags") or []
    meta_ok = bool(title) and len(title) <= 100 and len(desc) >= 50 and len(tags) <= 500
    add("metadata", "Valid title / description / tags", meta_ok,
        f"title {len(title)}/100 chars, description {len(desc)} chars, {len(tags)}/500 tags.",
        critical=True)

    # 4 ── Visual variety — warn
    n_files, n_unique = _unique_image_count(folder)
    detail = f"{n_unique} distinct scene images"
    if n_files != n_unique:
        detail += f" ({n_files} files, some identical)"
    add("visual_variety", "Visual variety (≥ 4 distinct images)", n_unique >= 4, detail + ".")

    # 5 ── Script originality — warn
    uniq = _trigram_uniqueness(script)
    add("originality", "Script originality", uniq >= 0.85,
        f"{uniq * 100:.0f}% unique 3-word sequences"
        + ("." if uniq >= 0.85 else " — looks repetitive."))

    # 6 ── AI disclosure resolved — warn
    needs = meta.get("requires_ai_disclosure")
    if needs is None:
        needs = requires_ai_disclosure(style)
    if not needs:
        add("disclosure", "AI disclosure", True,
            f"Stylized visuals ({style or 'n/a'}) — Studio label not required.")
    else:
        d_low = desc.lower()
        has_line = any(k in d_low for k in ("disclosure", "made with ai", "ai-assisted"))
        add("disclosure", "AI disclosure", has_line,
            "Realistic visuals — disclosure line present; set the Studio 'Altered content' toggle."
            if has_line else
            "Realistic visuals — add an AI-disclosure line and set the Studio 'Altered content' toggle.")

    # 7 ── Title not a near-duplicate of a recent upload — warn
    dup = title.strip().lower() in _recent_titles(folder_name)
    add("not_templated", "Title not a duplicate", not dup,
        "Title matches another upload — vary it." if dup
        else "Title is distinct from recent uploads.")

    # 8 ── Advertiser-safe niche — warn
    niche = settings.get("niche") or ""
    risk  = RISKY_NICHES.get(niche, "")
    add("niche_safety", "Advertiser-safe niche", not risk,
        f"'{niche}': {risk}" if risk else "Niche has no known monetization risk.")

    critical_failed = sum(1 for c in checks if c["severity"] == "critical" and not c["pass"])
    warn_failed     = sum(1 for c in checks if c["severity"] == "warn" and not c["pass"])
    passed          = sum(1 for c in checks if c["pass"])

    return {
        "folder":          folder_name,
        "checks":          checks,
        "passed":          passed,
        "total":           len(checks),
        "critical_failed": critical_failed,
        "warn_failed":     warn_failed,
        "ok_to_publish":   critical_failed == 0,
    }
