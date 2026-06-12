"""Karaoke-style subtitle renderer.

Builds 2-3 word subtitle groups from real word timings, highlights power words
or the active word in the style accent color, and burns them onto video frames
via a MoviePy fl_image callback.
"""
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config import PALETTES


# ── Power-word list for keyword highlighting ──────────────────
POWER_WORDS = {
    "AI", "MONEY", "RICH", "WEALTH", "SECRET", "SECRETS", "TRUTH", "HIDDEN",
    "FUTURE", "TECH", "SCIENCE", "SHOCKING", "FACT", "FACTS", "WARNING",
    "MISTAKE", "MILLION", "BILLION", "LUXURY", "ELITE", "POWER", "VIRAL",
    "GROWTH", "PROFIT", "BRAIN", "SPACE", "SATURN", "MARS", "ROBOT", "DARK",
    "MYSTERY", "BREAKTHROUGH", "SUCCESS", "FAIL", "WIN", "HOW", "WHY", "WHAT",
    "NEVER", "ALWAYS", "EVERY", "NOTHING", "EVERYTHING", "FOREVER", "DEAD",
    "ALIVE", "REAL", "FAKE", "PROOF", "EVIDENCE", "DANGER", "DEADLY",
    "TERRIFYING", "INSANE", "CRAZY", "AMAZING", "INCREDIBLE", "IMPOSSIBLE",
    "BANNED", "ILLEGAL", "EXPOSED", "REVEALED", "DESTROYED",
}


# ── Word grouping ─────────────────────────────────────────────

def build_subtitle_groups(
    all_word_timings: list[list[dict]],
    paragraph_durations: list[float],
    words_per_group: int = 3,
) -> list[dict]:
    """Build the global subtitle track.

    all_word_timings    : list of per-paragraph word timing lists (start=0 each)
    paragraph_durations : matching list of paragraph audio durations
    Returns list of {"text", "start", "end", "words": [(text, start, end), ...]}
    """
    # Offset and flatten
    flat: list[dict] = []
    offset = 0.0
    for dur, wts in zip(paragraph_durations, all_word_timings):
        for w in wts:
            flat.append({
                "text":  w["text"],
                "start": w["start"] + offset,
                "end":   w["end"]   + offset,
            })
        offset += dur

    # If word timings missing (pyttsx3 fallback), bail with empty list
    if not flat:
        return []

    # Group into windows
    groups: list[dict] = []
    for i in range(0, len(flat), words_per_group):
        chunk = flat[i:i + words_per_group]
        if not chunk:
            continue
        groups.append({
            "text":  " ".join(w["text"] for w in chunk).upper(),
            "start": chunk[0]["start"],
            "end":   chunk[-1]["end"],
            "words": [(w["text"].upper(), w["start"], w["end"]) for w in chunk],
        })

    # Stretch last group to cover any trailing silence
    if groups:
        groups[-1]["end"] = max(groups[-1]["end"], sum(paragraph_durations))
    return groups


def build_even_split_groups(
    paragraphs: list[str],
    paragraph_durations: list[float],
    words_per_group: int = 3,
) -> list[dict]:
    """Fallback subtitle track when there are NO word timings (cloned voice,
    uploaded voiceover, pyttsx3). Splits each paragraph's words evenly across
    its audio duration so captions still appear in sync, group by group.
    """
    groups: list[dict] = []
    offset = 0.0
    for para, dur in zip(paragraphs, paragraph_durations):
        words = [w for w in re.split(r"\s+", str(para).strip()) if w]
        if not words or dur <= 0:
            offset += max(0.0, dur)
            continue
        per = dur / len(words)
        timed = [(w.upper(), offset + j * per, offset + (j + 1) * per)
                 for j, w in enumerate(words)]
        for i in range(0, len(timed), words_per_group):
            chunk = timed[i:i + words_per_group]
            groups.append({
                "text":  " ".join(c[0] for c in chunk),
                "start": chunk[0][1],
                "end":   chunk[-1][2],
                "words": [(c[0], c[1], c[2]) for c in chunk],
            })
        offset += dur
    return groups


# ── Renderer ──────────────────────────────────────────────────

def _load_bold_font(size: int):
    for path in ("C:/Windows/Fonts/impact.ttf",
                 "C:/Windows/Fonts/arialbd.ttf",
                 "C:/Windows/Fonts/segoeuib.ttf",
                 "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class SubtitleRenderer:
    """Renders the active subtitle group onto a frame. Designed to be wrapped
    in a closure passed to MoviePy's `fl` transform."""

    def __init__(self, subtitle_groups: list[dict], style: str,
                 video_w: int, video_h: int, subtitle_preset: str = "Clean White"):
        self.groups = subtitle_groups
        self.preset = subtitle_preset
        palette = PALETTES.get(style, PALETTES["Cinematic"])

        # Base colours vary by preset
        if subtitle_preset == "Bold Yellow":
            self.text_color   = (255, 230, 0)
            self.stroke_color = (0, 0, 0)
            self.highlight    = (255, 80, 0)   # orange for power words
        elif subtitle_preset == "Neon Glow":
            self.text_color   = (255, 255, 255)
            self.stroke_color = (0, 0, 0)
            self.highlight    = _hex_to_rgb(palette["accent"])
        elif subtitle_preset == "Minimal":
            self.text_color   = (220, 220, 220)
            self.stroke_color = (0, 0, 0)
            self.highlight    = _hex_to_rgb(palette["accent"])
        else:  # Clean White (default)
            self.text_color   = (255, 255, 255)
            self.stroke_color = (0, 0, 0)
            self.highlight    = _hex_to_rgb(palette["accent"])

        # Scale font with video height; Minimal uses a smaller size
        base_scale = 0.038 if subtitle_preset == "Minimal" else 0.055
        self.font_size    = max(28, int(video_h * base_scale))
        self.stroke_width = max(2, self.font_size // 18) if subtitle_preset == "Minimal" else max(3, self.font_size // 16)
        self.font         = _load_bold_font(self.font_size)
        self.video_w      = video_w
        self.video_h      = video_h

        # Bottom-positioned (lower third) with safe margin
        self.bottom_margin = int(video_h * 0.12)

    def active_group(self, t: float) -> dict | None:
        # Linear scan — fine for typical 20-200 groups per video
        for g in self.groups:
            if g["start"] <= t < g["end"]:
                return g
        return None

    def active_word_index(self, group: dict, t: float) -> int:
        for idx, (_, ws, we) in enumerate(group["words"]):
            if ws <= t < we:
                return idx
        # After last word in group → highlight last word
        if t >= group["words"][-1][1]:
            return len(group["words"]) - 1
        return 0

    def is_power_word(self, word: str) -> bool:
        cleaned = re.sub(r"[^A-Z0-9]", "", word.upper())
        return cleaned in POWER_WORDS or cleaned.isdigit()

    def render(self, frame, t: float):
        """frame: H×W×3 numpy uint8. Returns modified frame."""
        group = self.active_group(t)
        if not group:
            return frame

        img = Image.fromarray(frame)
        draw = ImageDraw.Draw(img)
        words = [w[0] for w in group["words"]]
        if not words:
            return frame

        # For Minimal preset, don't highlight — just show all white
        if self.preset == "Minimal":
            highlight_idx = -1
        else:
            # Pick which word to highlight: power word in this group, else current word
            highlight_idx = None
            for i, w in enumerate(words):
                if self.is_power_word(w):
                    highlight_idx = i
                    break
            if highlight_idx is None:
                highlight_idx = self.active_word_index(group, t)

        # Layout: measure widths, fit to one line (groups are short)
        widths = []
        max_h = 0
        for w in words:
            bbox = draw.textbbox((0, 0), w, font=self.font)
            widths.append(bbox[2] - bbox[0])
            max_h = max(max_h, bbox[3] - bbox[1])
        space_bbox = draw.textbbox((0, 0), " ", font=self.font)
        space_w = space_bbox[2] - space_bbox[0]
        total_w = sum(widths) + max(0, len(words) - 1) * space_w

        # Wrap to two lines if total width > 88% of frame
        max_line_w = int(self.video_w * 0.88)
        if total_w <= max_line_w:
            lines = [list(range(len(words)))]
            line_widths = [total_w]
        else:
            # Greedy wrap
            lines: list[list[int]] = [[]]
            current_w = 0
            for i, w_px in enumerate(widths):
                proj = current_w + w_px + (space_w if lines[-1] else 0)
                if lines[-1] and proj > max_line_w:
                    lines.append([i])
                    current_w = w_px
                else:
                    lines[-1].append(i)
                    current_w = proj
            line_widths = []
            for line in lines:
                lw = sum(widths[i] for i in line) + max(0, len(line) - 1) * space_w
                line_widths.append(lw)

        line_h = max_h
        line_gap = int(line_h * 0.25)
        total_h = len(lines) * line_h + max(0, len(lines) - 1) * line_gap
        y_start = self.video_h - self.bottom_margin - total_h

        if self.preset == "Neon Glow":
            # Draw glow layer on separate image, blur it, composite
            glow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            for li, line in enumerate(lines):
                line_x = (self.video_w - line_widths[li]) // 2
                y = y_start + li * (line_h + line_gap)
                cx = line_x
                for word_idx in line:
                    word = words[word_idx]
                    fill = self.highlight if word_idx == highlight_idx else self.text_color
                    glow_col = (*self.highlight, 160) if word_idx == highlight_idx else (180, 180, 255, 100)
                    glow_draw.text((cx, y), word, font=self.font, fill=glow_col)
                    cx += widths[word_idx] + space_w
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=max(2, self.font_size // 10)))
            img = Image.alpha_composite(img.convert("RGBA"), glow_img).convert("RGB")
            draw = ImageDraw.Draw(img)

        # Draw each line
        sw = self.stroke_width
        for li, line in enumerate(lines):
            line_x = (self.video_w - line_widths[li]) // 2
            y = y_start + li * (line_h + line_gap)
            cx = line_x
            for word_idx in line:
                word = words[word_idx]
                # Stroke (outline) — circular kernel for smoothness
                for dx in range(-sw, sw + 1):
                    for dy in range(-sw, sw + 1):
                        if dx * dx + dy * dy <= sw * sw:
                            draw.text((cx + dx, y + dy), word, font=self.font,
                                      fill=self.stroke_color)
                fill = self.highlight if word_idx == highlight_idx else self.text_color
                draw.text((cx, y), word, font=self.font, fill=fill)
                cx += widths[word_idx] + space_w

        return np.array(img)


def make_subtitle_transform(subtitle_groups: list[dict], style: str,
                            video_w: int, video_h: int,
                            subtitle_preset: str = "Clean White"):
    """Return a MoviePy-compatible callable: fn(get_frame, t) → frame."""
    if not subtitle_groups:
        return None
    renderer = SubtitleRenderer(subtitle_groups, style, video_w, video_h,
                                subtitle_preset=subtitle_preset)

    def transform(get_frame, t):
        return renderer.render(get_frame(t), t)

    return transform
