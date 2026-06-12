"""YouTube thumbnail generator.

Primary: uses scene_01.png as background + bold title overlay + hook word badge.
Fallback: generates a stylised gradient card using the palette.
"""
import os
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import PALETTES, THUMB_SIZE_LANDSCAPE, THUMB_SIZE_PORTRAIT

# Hook words that get a large accent badge in the corner
_HOOK_WORDS = [
    "SECRET", "TRUTH", "EXPOSED", "SHOCKING", "HIDDEN", "WHY", "HOW",
    "REVEALED", "PROOF", "BANNED", "NEVER", "ALWAYS", "REAL", "DARK",
    "DANGER", "VIRAL", "INSANE", "CRAZY", "AMAZING", "IMPOSSIBLE",
]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["C:/Windows/Fonts/impact.ttf",
         "C:/Windows/Fonts/arialbd.ttf",
         "C:/Windows/Fonts/segoeuib.ttf",
         "C:/Windows/Fonts/calibrib.ttf",
         "C:/Windows/Fonts/arial.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf",
         "C:/Windows/Fonts/segoeuil.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _pick_hook_word(title: str) -> str:
    words = title.upper().split()
    for w in words:
        clean = "".join(c for c in w if c.isalpha())
        if clean in _HOOK_WORDS:
            return clean
    return ""


def _draw_title_overlay(draw: ImageDraw.Draw, title: str,
                        acc_rgb: tuple, txt_rgb: tuple,
                        w: int, h: int) -> None:
    """Draw semi-transparent dark bar + title text in lower portion."""
    # Dark gradient bar covering bottom 38%
    bar_top = int(h * 0.62)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    for y in range(bar_top, h):
        alpha = int(210 * ((y - bar_top) / (h - bar_top)) ** 0.6)
        ov.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    return overlay


def _draw_text_centered(draw: ImageDraw.Draw, text: str, font,
                        x_center: int, y: int,
                        fill: tuple, stroke_fill=(0, 0, 0), stroke_width: int = 3):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = x_center - tw // 2
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx * dx + dy * dy <= stroke_width * stroke_width:
                draw.text((tx + dx, y + dy), text, font=font, fill=stroke_fill)
    draw.text((tx, y), text, font=font, fill=fill)


def _thumbnail_from_scene(scene_path: str, title: str, style: str,
                           w: int, h: int, output_path: str) -> bool:
    """Build thumbnail using scene_01.png as background. Returns True on success."""
    if not os.path.exists(scene_path):
        return False
    try:
        img = Image.open(scene_path).convert("RGB")
        # Resize/crop to thumbnail dimensions
        img_w, img_h = img.size
        scale = max(w / img_w, h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top  = (new_h - h) // 2
        img  = img.crop((left, top, left + w, top + h))

        palette   = PALETTES.get(style, PALETTES["Cinematic"])
        acc_rgb   = _hex_to_rgb(palette["accent"])
        txt_rgb   = (255, 255, 255)

        # Dark overlay in lower portion
        overlay_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ov = ImageDraw.Draw(overlay_img)
        bar_top = int(h * 0.55)
        for y in range(bar_top, h):
            alpha = int(220 * ((y - bar_top) / (h - bar_top)) ** 0.5)
            ov.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        # Top dim for any badge
        for y in range(int(h * 0.18)):
            alpha = int(80 * (1 - y / (h * 0.18)))
            ov.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

        img = Image.alpha_composite(img.convert("RGBA"), overlay_img).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Accent left bar
        draw.rectangle([(0, 0), (max(6, w // 100), h)], fill=acc_rgb)

        # Hook word badge (top-right)
        hook = _pick_hook_word(title)
        if hook:
            hf_size = max(28, h // 10)
            hf = _get_font(hf_size)
            hb = draw.textbbox((0, 0), hook, font=hf)
            hw = hb[2] - hb[0] + 24
            hh = hb[3] - hb[1] + 16
            hx = w - hw - 16
            hy = 12
            draw.rectangle([(hx, hy), (hx + hw, hy + hh)], fill=acc_rgb)
            draw.text((hx + 12, hy + 8), hook, font=hf, fill=(255, 255, 255))

        # Title text — split 2 lines, bottom third
        title_font_size = max(42, w // 13)
        title_font = _get_font(title_font_size)
        max_chars = max(14, w // (title_font_size // 2))
        wrapped = textwrap.wrap(title, width=max_chars)[:3]

        line_h = title_font_size + 8
        total_text_h = len(wrapped) * line_h
        start_y = h - total_text_h - int(h * 0.06)

        for i, line in enumerate(wrapped):
            y = start_y + i * line_h
            _draw_text_centered(draw, line, title_font,
                                w // 2, y, txt_rgb,
                                stroke_fill=(0, 0, 0), stroke_width=max(2, title_font_size // 18))

        img.save(output_path, "PNG")
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Scene-based thumbnail failed: %s", e)
        return False


def _thumbnail_gradient(title: str, style: str, w: int, h: int, output_path: str) -> str:
    """Fallback: stylised gradient card."""
    palette = PALETTES.get(style, PALETTES["Cinematic"])
    bg_rgb  = _hex_to_rgb(palette["bg"])
    acc_rgb = _hex_to_rgb(palette["accent"])
    txt_rgb = _hex_to_rgb(palette["text"])
    sub_rgb = _hex_to_rgb(palette["sub"])

    img = Image.new("RGB", (w, h), bg_rgb)
    draw = ImageDraw.Draw(img)

    for y in range(h):
        ratio = abs(y / h - 0.5) * 2
        darken = int(40 * ratio)
        r = max(0, bg_rgb[0] - darken)
        g = max(0, bg_rgb[1] - darken)
        b = max(0, bg_rgb[2] - darken)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    draw.rectangle([(0, 0), (max(8, w // 80), h)], fill=acc_rgb)

    # Hook word badge
    hook = _pick_hook_word(title)
    if hook:
        hf_size = max(28, h // 9)
        hf = _get_font(hf_size)
        hb = draw.textbbox((0, 0), hook, font=hf)
        hw = hb[2] - hb[0] + 24
        hh = hb[3] - hb[1] + 16
        hx = w - hw - 20
        hy = 16
        draw.rectangle([(hx, hy), (hx + hw, hy + hh)], fill=acc_rgb)
        draw.text((hx + 12, hy + 8), hook, font=hf, fill=txt_rgb)

    title_font_size = max(48, w // 14)
    title_font = _get_font(title_font_size)
    max_chars = max(15, w // (title_font_size // 2))
    wrapped = textwrap.wrap(title, width=max_chars)[:2]

    line_h = title_font_size + 10
    total_h = len(wrapped) * line_h
    start_y = (h - total_h) // 2 - 20

    for i, line in enumerate(wrapped):
        bbox = draw.textbbox((0, 0), line, font=title_font)
        line_w = bbox[2] - bbox[0]
        x = (w - line_w) // 2
        y = start_y + i * line_h
        draw.text((x + 3, y + 3), line, font=title_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=title_font, fill=txt_rgb)

    # Bottom gradient fade
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    fade_h = h // 4
    for y in range(fade_h):
        alpha = int(160 * y / fade_h)
        ov.line([(0, h - fade_h + y), (w, h - fade_h + y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    img.save(output_path, "PNG")
    return output_path


def generate_thumbnail(
    title: str,
    style: str,
    aspect_ratio: str,
    output_path: str,
    channel_name: str = "AutoVideo",
    scene_image_path: str = "",
) -> str:
    w, h = THUMB_SIZE_LANDSCAPE if aspect_ratio != "9:16" else THUMB_SIZE_PORTRAIT

    # Try scene-based thumbnail first
    if scene_image_path and _thumbnail_from_scene(scene_image_path, title, style, w, h, output_path):
        return output_path

    # Fallback: gradient card
    return _thumbnail_gradient(title, style, w, h, output_path)
