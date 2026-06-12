"""Scene image generator: AI image (Pollinations) + subtitle caption overlay,
with text-only fallback. Includes animation helpers for the video assembler."""
import logging
import os
import re
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import PALETTES, RESOLUTIONS

logger = logging.getLogger(__name__)


# ── Style → visual modifier for image prompt ──────────────────
_STYLE_VISUALS = {
    "Cinematic":        "cinematic film still, dramatic moody lighting, shallow depth of field, anamorphic, professional photography",
    "Ghibli-Inspired":  "studio ghibli anime style, hand-drawn, soft watercolor, dreamy atmospheric landscape, miyazaki",
    "Minimalist":       "minimalist composition, clean lines, lots of negative space, geometric, editorial photography",
    "Cyberpunk/Neon":   "cyberpunk aesthetic, neon lights, blade runner, futuristic city, rain reflections, cinematic",
    "Vintage":          "vintage 1970s film photography, sepia tones, faded colors, kodachrome, grainy",
    "Comic Book":       "comic book illustration, bold inked lines, vibrant flat colors, halftone shading, dynamic action",
    "Nature & Calm":    "serene nature photography, golden hour light, lush landscape, peaceful, high detail",
}

# Camera/composition variation per scene index so each image feels different
_SHOT_TYPES = [
    "wide establishing shot",
    "atmospheric close-up",
    "dramatic perspective",
    "epic wide angle",
    "intimate detail shot",
    "panoramic vista",
    "low angle hero shot",
    "ethereal symbolic composition",
    "powerful final shot",
]


# ── Helpers ───────────────────────────────────────────────────

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _get_font(size: int):
    for path in ("C:/Windows/Fonts/segoeuib.ttf",
                 "C:/Windows/Fonts/arialbd.ttf",
                 "C:/Windows/Fonts/arial.ttf",
                 "arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _extract_visual_subject(paragraph: str, topic: str) -> str:
    """Pull a short visual phrase from the paragraph. Falls back to topic."""
    # Strip common narrative clutter
    text = re.sub(r"\b(you|your|we|us|they|them|i|me|my|the|a|an|is|are|was|were|"
                  r"and|but|or|of|to|in|on|at|for|with|that|this|it|its|"
                  r"will|would|could|should|have|has|had|been|being|"
                  r"about|because|then|than|so|just|like|do|does|did|"
                  r"video|subscribe|like|share|channel|click)\b",
                  "", paragraph, flags=re.IGNORECASE)
    words = [w for w in re.findall(r"[A-Za-z]{4,}", text) if w]
    # Take the first 4 meaningful words for visual context
    visual = " ".join(words[:4]).lower()
    if not visual:
        visual = topic
    return f"{topic} — {visual}"


def _build_image_prompt(paragraph: str, topic: str, style: str, scene_idx: int,
                        visual_hint: str = "") -> str:
    style_mod = _STYLE_VISUALS.get(style, _STYLE_VISUALS["Cinematic"])
    shot = _SHOT_TYPES[scene_idx % len(_SHOT_TYPES)]
    # Use Gemini visual_plan hint if available; fall back to generic extraction
    subject = visual_hint.strip() if visual_hint and len(visual_hint) > 4 else _extract_visual_subject(paragraph, topic)
    return (f"{subject}, {shot}, {style_mod}, "
            f"highly detailed, 4k, photorealistic, no text, no words, no letters, no captions")


# ── Pollinations fetch ────────────────────────────────────────

def _fetch_gemini_image(prompt: str, output_path: str) -> bool:
    """Generate image via Gemini (Nano Banana). Returns True on success.
    Requires billing-enabled Google Cloud project for the image models."""
    try:
        from modules.gemini_client import is_available, _client
    except Exception:
        return False
    if not is_available():
        return False

    # Try models in quality order
    models = ["gemini-2.5-flash-image", "gemini-3-pro-image"]
    for model in models:
        try:
            c = _client()
            resp = c.models.generate_content(model=model, contents=prompt[:1500])
            for cand in resp.candidates:
                for part in cand.content.parts:
                    if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                        with open(output_path, "wb") as f:
                            f.write(part.inline_data.data)
                        try:
                            Image.open(output_path).verify()
                            logger.info("Gemini image OK model=%s bytes=%d",
                                        model, len(part.inline_data.data))
                            return True
                        except Exception:
                            try: os.remove(output_path)
                            except Exception: pass
        except Exception as e:
            msg = str(e)[:140]
            logger.warning("Gemini image %s failed: %s", model, msg)
    return False


def _fetch_pollinations_image(prompt: str, width: int, height: int,
                              output_path: str, seed: int = 0) -> bool:
    """Try turbo → flux, each with one retry. Returns True on success."""
    encoded = quote(prompt[:480], safe="")
    attempts = [
        ("turbo", 35),  # fast model, short timeout
        ("turbo", 60),  # turbo retry, longer timeout
        ("flux",  90),  # flux fallback, longest timeout
    ]
    for model, timeout in attempts:
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width={width}&height={height}&nologo=true"
               f"&model={model}&seed={seed}")
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 8000:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                try:
                    Image.open(output_path).verify()
                    logger.info("Pollinations OK seed=%d model=%s bytes=%d",
                                seed, model, len(r.content))
                    return True
                except Exception:
                    try: os.remove(output_path)
                    except Exception: pass
            else:
                logger.warning("Pollinations bad response seed=%d model=%s status=%d bytes=%d",
                               seed, model, r.status_code, len(r.content))
        except Exception as e:
            logger.warning("Pollinations error seed=%d model=%s: %s", seed, model, e)
    return False


# ── Caption overlay ───────────────────────────────────────────

def _apply_cinematic_finish(base_path: str, style: str, output_path: str) -> str:
    """Open the AI image and apply a cinematic vignette + faint top/bottom dim
    so karaoke subtitles read cleanly later. No baked-in caption text."""
    img = Image.open(base_path).convert("RGB")
    w, h = img.size

    # Soft vignette using radial alpha
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)

    # Top dim (top 12%) — strengthens contrast for any UI in upper area
    top_h = int(h * 0.12)
    for y in range(top_h):
        a = int(110 * (1 - y / top_h))
        ov_draw.line([(0, y), (w, y)], fill=(0, 0, 0, a))

    # Bottom dim (bottom 32%) — under subtitle zone, but gentle (subtitle has its own stroke)
    bot_top = int(h * 0.68)
    for y in range(bot_top, h):
        a = int(150 * ((y - bot_top) / max(1, h - bot_top)) ** 1.4)
        ov_draw.line([(0, y), (w, y)], fill=(0, 0, 0, a))

    # Edge vignette
    edge = max(8, w // 80)
    for i in range(edge):
        a = int(70 * (1 - i / edge))
        ov_draw.rectangle([(i, i), (w - i, h - i)], outline=(0, 0, 0, a))

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img.save(output_path, "PNG")
    return output_path


# ── Animated gradient fallback (when image fetch fails) ────────

def _animated_gradient_scene(style: str, w: int, h: int,
                              scene_number: int, output_path: str) -> str:
    """Generate a cinematic animated-gradient PNG — better than plain text card.
    Uses phase offset from scene_number so each scene looks different."""
    palette = PALETTES.get(style, PALETTES["Cinematic"])
    bg  = _hex_to_rgb(palette["bg"])
    acc = _hex_to_rgb(palette["accent"])

    import math
    phase = (scene_number * 137) % 360  # golden-angle spread
    img_arr = np.zeros((h, w, 3), dtype=np.uint8)

    for y in range(h):
        for x in range(w):
            # Base gradient: diagonal
            t = (x / w + y / h) / 2
            # Wave overlay
            wave = 0.5 + 0.5 * math.sin(math.radians(phase + t * 360 * 2))
            # Radial vignette
            cx, cy = w / 2, h / 2
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / math.sqrt(cx ** 2 + cy ** 2)
            vignette = max(0.0, 1.0 - dist * 0.7)

            r = int((bg[0] * (1 - wave * 0.4) + acc[0] * wave * 0.25) * vignette)
            g = int((bg[1] * (1 - wave * 0.4) + acc[1] * wave * 0.25) * vignette)
            b = int((bg[2] * (1 - wave * 0.4) + acc[2] * wave * 0.25) * vignette)
            img_arr[y, x] = [min(255, r), min(255, g), min(255, b)]

    # Diagonal light beam
    beam_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bm = ImageDraw.Draw(beam_img)
    bw = max(w // 6, 80)
    bx = int((phase / 360) * w * 1.5) - bw
    pts = [(bx, 0), (bx + bw, 0), (bx + bw + h // 3, h), (bx + h // 3, h)]
    bm.polygon(pts, fill=(*acc, 18))
    beam = np.array(beam_img)

    base = Image.fromarray(img_arr)
    beam_layer = Image.fromarray(beam)
    result = Image.alpha_composite(base.convert("RGBA"), beam_layer).convert("RGB")

    # Soft vignette edge
    vign = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vign)
    edge = max(8, w // 50)
    for i in range(edge):
        a = int(90 * (1 - i / edge))
        vd.rectangle([(i, i), (w - i, h - i)], outline=(0, 0, 0, a))
    result = Image.alpha_composite(result.convert("RGBA"), vign).convert("RGB")

    result.save(output_path, "PNG")
    return output_path


def _text_only_scene(text: str, style: str, w: int, h: int,
                     scene_number: int, output_path: str, topic: str) -> str:
    """Final fallback: animated gradient with minimal text label."""
    # Always try animated gradient first — far better than a text card
    try:
        _animated_gradient_scene(style, w, h, scene_number, output_path)
        return output_path
    except Exception:
        pass

    # True last resort: plain colour card
    palette = PALETTES.get(style, PALETTES["Cinematic"])
    bg = _hex_to_rgb(palette["bg"])
    acc = _hex_to_rgb(palette["accent"])
    txt = _hex_to_rgb(palette["text"])
    sub = _hex_to_rgb(palette["sub"])

    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img, "RGBA")

    dark = tuple(max(0, c - 50) for c in bg)
    for y in range(h):
        t = y / h
        r = int(bg[0] * (1 - t) + dark[0] * t)
        g = int(bg[1] * (1 - t) + dark[1] * t)
        b = int(bg[2] * (1 - t) + dark[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    draw.rectangle([(0, 0), (w, max(4, h // 120))], fill=acc)
    if topic:
        draw.text((20, 22), topic.upper()[:50], font=_get_font(max(16, w // 60)), fill=sub)

    max_chars = max(28, w // 38)
    lines = textwrap.wrap(text, width=max_chars)
    fs = max(26, w // 32)
    font = _get_font(fs)
    line_h = fs + int(fs * 0.4)
    total = len(lines) * line_h
    start_y = (h - total) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (w - lw) // 2
        y = start_y + i * line_h
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=txt)

    img.save(output_path, "PNG")
    return output_path


# ── Public API ────────────────────────────────────────────────

def _fetch_pexels_image(query: str, width: int, height: int, output_path: str) -> bool:
    """Try Pexels photo search as a high-quality fallback.

    Saves the resized image to ``output_path`` (the caller's ai_raw path) so the
    caller can find it. Previously this saved to a doubly-suffixed ``_ai_ai.png``
    that the caller never read — so every downloaded Pexels photo was discarded
    and the scene fell through to a blank gradient.
    """
    try:
        from modules.pexels_client import is_available, search_photo, download_photo
    except Exception:
        return False
    if not is_available():
        return False

    orientation = "portrait" if height > width else "landscape"
    photos = search_photo(query[:80], orientation=orientation)
    tmp = output_path + ".pexels.jpg"
    for photo in photos:
        if download_photo(photo, tmp):
            try:
                img = Image.open(tmp).convert("RGB").resize((width, height), Image.LANCZOS)
                img.save(output_path, "PNG")
                logger.info("Pexels image OK: %s", os.path.basename(output_path))
                return True
            except Exception as e:
                logger.warning("Pexels resize failed: %s", e)
            finally:
                try: os.remove(tmp)
                except Exception: pass
    return False


def generate_scene(text: str, style: str, width: int, height: int,
                   scene_number: int, output_path: str, topic: str = "",
                   image_provider: str = "pollinations",
                   visual_hint: str = "") -> str:
    """Generate one scene image.

    image_provider:
      "pollinations" — free, no key needed (default)
      "gemini"       — Gemini Nano Banana (requires billing-enabled Gemini key);
                       falls back to Pollinations on failure
      "pexels"       — Pexels stock photos (free, needs PEXELS_API_KEY in .env)
    visual_hint: Gemini-generated 5-7 word image description for this scene.
    All paths fall back to a text-only scene if every image source fails.
    """
    ai_raw = output_path.replace(".png", "_ai.png")
    prompt = _build_image_prompt(text, topic, style, scene_number - 1, visual_hint=visual_hint)
    seed = (scene_number * 1009 + abs(hash(topic)) % 9973) % 100000
    # Use visual_hint as pexels search query if available, otherwise use topic
    pexels_query = visual_hint if visual_hint and len(visual_hint) > 4 else topic

    fetched = False
    if image_provider == "gemini":
        fetched = _fetch_gemini_image(prompt, ai_raw)
        if not fetched:
            logger.info("Gemini image unavailable, falling back to Pollinations")

    if not fetched and image_provider == "pexels":
        fetched = _fetch_pexels_image(pexels_query, width, height, ai_raw)
        if not fetched:
            logger.info("Pexels unavailable, falling back to Pollinations")

    if not fetched:
        fetched = _fetch_pollinations_image(prompt, width, height, ai_raw, seed=seed)

    if not fetched:
        # Try Pexels as additional fallback for any provider
        fetched = _fetch_pexels_image(pexels_query, width, height, ai_raw)

    if fetched:
        try:
            _apply_cinematic_finish(ai_raw, style, output_path)
            try: os.remove(ai_raw)
            except Exception: pass
            return output_path
        except Exception as e:
            logger.warning("Cinematic finish failed: %s", e)

    # Last resort: text-only scene
    return _text_only_scene(text, style, width, height, scene_number, output_path, topic)


def generate_scenes(paragraphs: list[str], style: str, aspect_ratio: str,
                    quality: str, topic: str, project_dir: str,
                    image_provider: str = "pollinations",
                    visual_plan: list[str] | None = None,
                    progress_cb=None) -> list[str]:
    """Generate one image per paragraph sequentially.

    image_provider: 'pollinations' (free, default) or 'gemini' (Nano Banana).
    visual_plan: Gemini-generated image descriptions (one per paragraph).
    progress_cb(done, total, label): optional callback fired after each scene completes."""
    res = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["16:9"])
    w, h = res.get(quality, res["720p"])

    # Cap fetch dimensions to avoid Pollinations 4K timeouts
    fetch_w = min(w, 1920)
    fetch_h = min(h, 1080)

    total = len(paragraphs)
    out_paths: list[str] = [
        os.path.join(project_dir, f"scene_{i:02d}.png")
        for i, _ in enumerate(paragraphs, 1)
    ]
    plan = visual_plan or []

    def task(idx: int, para: str, out: str):
        hint = plan[idx] if idx < len(plan) else ""
        generate_scene(para, style, fetch_w, fetch_h, idx + 1, out, topic,
                       image_provider=image_provider, visual_hint=hint)
        # Pollinations often returns smaller than requested — force-resize to target
        try:
            img = Image.open(out)
            if img.size != (w, h):
                img.resize((w, h), Image.LANCZOS).save(out, "PNG")
        except Exception:
            pass

    # Sequential — Pollinations is unstable under parallel load
    for i, (p, out) in enumerate(zip(paragraphs, out_paths)):
        if progress_cb:
            # Callback may legitimately raise (e.g. user cancellation) — let it bubble.
            progress_cb(i, total, f"Creating scene {i + 1} of {total}...")
        try:
            task(i, p, out)
        except Exception as e:
            logger.warning("Scene %d failed: %s", i + 1, e)

    if progress_cb:
        progress_cb(total, total, f"All {total} scenes ready")

    return out_paths


# ── Hybrid visual engine: real video B-roll + AI image fallback ──

# Words to drop when turning a cinematic image prompt into a stock-footage search.
_BROLL_STOP = set((
    "a an the of and or to in on at by for is are was were be this that these those it its "
    "your you with as from glowing dark light cinematic abstract void deep close up closeup "
    "shot macro scene background style colorful vibrant epic moody dramatic surreal ultra hd 4k "
    "view angle wide depth field bokeh"
).split())


def _broll_query(hint: str, paragraph: str, topic: str) -> str:
    """Derive 2-3 concrete search keywords for Pexels video from the visual hint."""
    src = (hint or paragraph or topic or "").lower()
    words = re.findall(r"[a-z]+", src)
    keep = [w for w in words if w not in _BROLL_STOP and len(w) > 2]
    q = " ".join(keep[:3]).strip()
    if not q:
        q = " ".join((topic or "abstract motion").split()[:2])
    return q


def _pick_video(vids: list[dict]) -> dict:
    """Prefer a clip 3-30s long (good loop length), else the first result."""
    good = [v for v in vids if 3 <= (v.get("duration") or 0) <= 30]
    return (good or vids)[0]


def generate_scene_assets(paragraphs: list[str], style: str, aspect_ratio: str,
                          quality: str, topic: str, project_dir: str,
                          image_provider: str = "pollinations",
                          visual_plan: list[str] | None = None,
                          progress_cb=None, use_broll: bool = True) -> list[str]:
    """Hybrid visuals: real Pexels VIDEO B-roll where it matches the narration,
    else a cinematic AI image. Returns asset paths (mix of .mp4 and .png), one per
    paragraph. The assembler tells them apart by extension."""
    res = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["16:9"])
    w, h = res.get(quality, res["720p"])
    fetch_w, fetch_h = min(w, 1920), min(h, 1080)
    orientation = "portrait" if h > w else ("square" if h == w else "landscape")
    plan = visual_plan or []
    total = len(paragraphs)

    from modules import pexels_client
    broll_ok = use_broll and pexels_client.is_available()

    assets: list[str] = []
    for i, para in enumerate(paragraphs):
        if progress_cb:
            progress_cb(i, total, f"Finding footage for scene {i + 1} of {total}...")
        hint = plan[i] if i < len(plan) else ""
        asset = ""

        # 1) Real motion B-roll (the "alive" look)
        if broll_ok:
            try:
                query = _broll_query(hint, para, topic)
                vids = pexels_client.search_video(query, orientation=orientation, per_page=6)
                if vids:
                    vpath = os.path.join(project_dir, f"scene_{i:02d}.mp4")
                    if pexels_client.download_video_clip(_pick_video(vids), vpath,
                                                         preferred_w=fetch_w, preferred_h=fetch_h):
                        asset = vpath
                        logger.info("Scene %d: B-roll '%s'", i + 1, query)
            except Exception as e:
                logger.warning("B-roll fetch failed scene %d: %s", i + 1, e)

        # 2) Cinematic AI image fallback (any topic)
        if not asset:
            ipath = os.path.join(project_dir, f"scene_{i:02d}.png")
            try:
                generate_scene(para, style, fetch_w, fetch_h, i + 1, ipath, topic,
                               image_provider=image_provider, visual_hint=hint)
                try:
                    img = Image.open(ipath)
                    if img.size != (w, h):
                        img.resize((w, h), Image.LANCZOS).save(ipath, "PNG")
                except Exception:
                    pass
                asset = ipath
            except Exception as e:
                logger.warning("Image scene %d failed (%s) — text fallback", i + 1, e)
                _text_only_scene(para, style, w, h, i + 1, ipath, topic)
                asset = ipath
        assets.append(asset)

    if progress_cb:
        progress_cb(total, total, f"All {total} scenes ready")
    return assets


# ── Animation helpers (used by video_assembler) ───────────────

def apply_animation(clip, animation: str, duration: float, scene_idx: int = 0):
    """Apply animation to a MoviePy ImageClip. Returns the modified clip.

    scene_idx lets motion vary scene-to-scene so consecutive clips don't look
    identical (a common 'AI slideshow' tell).
    """
    d = max(duration, 0.1)

    # "Auto" rotates motion styles so the video never feels like one static recipe.
    if animation in ("Auto", "Auto (Varied Motion)"):
        animation = ["Ken Burns", "Slide In", "Ken Burns", "Fade Transitions"][scene_idx % 4]

    if animation == "Ken Burns":
        # Alternate slow zoom-in / zoom-out per scene for constant, varied motion.
        if scene_idx % 2 == 0:
            return clip.resize(lambda t: 1.0 + 0.09 * t / d)     # zoom in
        return clip.resize(lambda t: 1.10 - 0.09 * t / d)        # zoom out (stays >1)

    if animation == "Fade Transitions":
        fade = min(0.4, duration * 0.15)
        # Pair the fade with a gentle drift zoom so it isn't fully static.
        drift = clip.resize(lambda t: 1.0 + 0.05 * t / d)
        return drift.fadein(fade).fadeout(fade)

    if animation == "Glitch Effect":
        def glitch(frame):
            if np.random.random() < 0.04:
                shift = np.random.randint(-12, 12)
                return np.roll(frame, shift, axis=1)
            return frame
        return clip.fl_image(glitch)

    if animation == "Slide In":
        w = clip.w
        slide_t = min(0.4, duration * 0.2)
        return clip.set_position(
            lambda t: (int(-w + w * min(1.0, t / slide_t)), "center")
        )

    if animation == "Typewriter Text":
        # Subtle slow zoom — typewriter is in the burned-in caption already
        return clip.resize(lambda t: 1 + 0.03 * t / max(duration, 0.1))

    return clip
