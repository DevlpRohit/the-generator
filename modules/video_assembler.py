"""Video assembler — binds each scene image to its own paragraph audio clip
so the image stays on screen exactly while that line is being spoken, and
burns word-timed karaoke subtitles onto the final composition."""
import logging
import os
from pathlib import Path

# Use bundled ffmpeg before MoviePy imports
try:
    import imageio_ffmpeg
    os.environ.setdefault("FFMPEG_BINARY", imageio_ffmpeg.get_ffmpeg_exe())
except Exception:
    pass

from moviepy.editor import (
    ImageClip, AudioFileClip,
    concatenate_videoclips, CompositeAudioClip, CompositeVideoClip,
)
from moviepy.video.fx.crop import crop
from modules.subtitle_renderer import (
    build_subtitle_groups, build_even_split_groups, make_subtitle_transform,
)

logger = logging.getLogger(__name__)


_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".m4v")


def _cover_crop(clip, tw: int, th: int):
    """Scale a clip to COVER tw×th (preserve aspect, crop overflow) → exact tw×th."""
    cover = max(tw / clip.w, th / clip.h)
    clip = clip.resize(cover)
    return crop(clip, width=tw, height=th, x_center=clip.w / 2, y_center=clip.h / 2)


def _build_video_scene(path: str, dur: float, tw: int, th: int):
    """Real B-roll footage scene: muted, looped/trimmed to dur, cover-cropped to fill."""
    from moviepy.editor import VideoFileClip, vfx
    v = VideoFileClip(path, audio=False)
    if v.duration and v.duration < dur:
        v = v.fx(vfx.loop, duration=dur)          # loop short clips to fill the line
    else:
        v = v.subclip(0, min(dur, v.duration or dur))
    v = _cover_crop(v, tw, th).set_duration(dur)
    return CompositeVideoClip([v], size=(tw, th)).set_duration(dur)


def _build_scene_clip(asset_path: str, dur: float, tw: int, th: int,
                      animation: str, scene_idx: int):
    """One scene that FILLS the tw×th frame. Real video B-roll plays as motion;
    a still image gets a Ken Burns zoom. Output is exactly tw×th either way."""
    if asset_path.lower().endswith(_VIDEO_EXTS):
        try:
            return _build_video_scene(asset_path, dur, tw, th)
        except Exception as e:
            logger.warning("B-roll clip failed (%s), treating as image: %s", asset_path, e)

    base = ImageClip(asset_path)
    base = _cover_crop(base, tw, th).set_duration(dur)

    d = max(dur, 0.1)
    if animation in ("Glitch Effect", "Slide In"):
        moving = base.resize(lambda t: 1.0 + 0.04 * t / d)   # subtle for these
    elif scene_idx % 2 == 0:
        moving = base.resize(lambda t: 1.0 + 0.12 * t / d)   # slow zoom IN
    else:
        moving = base.resize(lambda t: 1.12 - 0.12 * t / d)  # slow zoom OUT
    moving = moving.set_position("center")

    scene = CompositeVideoClip([moving], size=(tw, th)).set_duration(dur)
    if animation in ("Fade Transitions", "Auto", "Auto (Varied Motion)"):
        fade = min(0.4, dur * 0.18)
        scene = scene.fadein(fade).fadeout(fade)
    return scene


def _make_grader(tw: int, th: int):
    """Cinematic grade: gentle contrast + saturation + warmth + vignette (cached mask)."""
    import numpy as np
    yy, xx = np.mgrid[0:th, 0:tw]
    r = np.sqrt(((xx - tw / 2) / (tw / 2)) ** 2 + ((yy - th / 2) / (th / 2)) ** 2)
    vig = np.clip(1.0 - 0.32 * np.clip(r - 0.55, 0, 1), 0.62, 1.0).astype(np.float32)[..., None]

    def grade(frame):
        f = frame.astype(np.float32) / 255.0
        f = (f - 0.5) * 1.10 + 0.5                 # contrast
        g = f.mean(axis=2, keepdims=True)
        f = g + (f - g) * 1.16                     # saturation
        f = f * vig                                # vignette
        f[..., 0] *= 1.02                          # subtle warm lift
        return (np.clip(f, 0, 1) * 255).astype(np.uint8)
    return grade


def assemble_video(
    scene_paths: list[str],
    scene_audio_paths: list[str],
    music_path: str,
    animation: str,
    output_path: str,
    fps: int = 30,
    word_timings: list[list[dict]] | None = None,
    style: str = "Cinematic",
    subtitle_preset: str = "Clean White",
    paragraphs: list[str] | None = None,
    target_size: tuple[int, int] | None = None,
) -> str:
    """Build the final video.

    scene_paths        : list of PNG paths (one per paragraph)
    scene_audio_paths  : list of MP3 paths (one per paragraph)
    word_timings       : list of per-paragraph word-timing lists (optional)
    style              : palette key used for subtitle accent color
    """
    if len(scene_paths) != len(scene_audio_paths):
        raise ValueError(
            f"scene/audio length mismatch: {len(scene_paths)} vs {len(scene_audio_paths)}"
        )
    if not scene_paths:
        raise ValueError("No scene images provided")

    # Target frame size: passed in (preferred) or inferred from the first image.
    if target_size:
        tw, th = int(target_size[0]), int(target_size[1])
    else:
        probe = ImageClip(scene_paths[0])
        tw, th = probe.w, probe.h
        probe.close()

    audio_clips: list[AudioFileClip] = []
    video_clips = []
    durations: list[float] = []

    for i, (img_path, audio_path) in enumerate(zip(scene_paths, scene_audio_paths)):
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"Scene image missing: {img_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Scene audio missing: {audio_path}")

        audio = AudioFileClip(audio_path)
        audio_clips.append(audio)
        dur = audio.duration
        durations.append(dur)

        # Fill the frame (no black bars) + visible Ken Burns motion.
        scene_clip = _build_scene_clip(img_path, dur, tw, th, animation, scene_idx=i)
        scene_clip = scene_clip.set_audio(audio)
        video_clips.append(scene_clip)

    # ── Concatenate scene clips ───────────────────────────────
    video = concatenate_videoclips(video_clips, method="compose")
    total_duration = video.duration
    vw, vh = video.w, video.h

    # ── Cinematic color grade (contrast + saturation + warmth + vignette) ──
    try:
        video = video.fl_image(_make_grader(vw, vh))
    except Exception as e:
        logger.warning("Color grade skipped: %s", e)

    # ── Burn subtitles — word-timed if available, else even-split from text ──
    try:
        subtitle_groups = []
        if word_timings:
            subtitle_groups = build_subtitle_groups(word_timings, durations,
                                                    words_per_group=3)
        # No real word timings (cloned voice / uploaded voiceover / pyttsx3) →
        # build evenly-timed captions from the paragraph text so subtitles ALWAYS show.
        if not subtitle_groups and paragraphs:
            subtitle_groups = build_even_split_groups(paragraphs, durations,
                                                      words_per_group=3)
        transform = make_subtitle_transform(subtitle_groups, style, vw, vh,
                                            subtitle_preset=subtitle_preset)
        if transform is not None:
            video = video.fl(transform)
            logger.info("Subtitle track: %d groups", len(subtitle_groups))
        else:
            logger.warning("No subtitles rendered (no timings and no paragraph text)")
    except Exception as e:
        logger.warning("Subtitle render failed (continuing without): %s", e)

    # ── Optional background music ─────────────────────────────
    music_clip = None
    if music_path and os.path.exists(music_path):
        try:
            music_clip = (AudioFileClip(music_path)
                          .volumex(0.12)
                          .audio_fadeout(min(2.0, total_duration * 0.1)))
            if music_clip.duration > total_duration:
                music_clip = music_clip.subclip(0, total_duration)
            final_audio = CompositeAudioClip([video.audio, music_clip])
            video = video.set_audio(final_audio)
        except Exception as e:
            logger.warning("Music mix failed, dropping music: %s", e)

    assert video.audio is not None, "AUDIO NOT ATTACHED — aborting export"

    # ── Export (higher bitrate + slow preset for crisp output) ──
    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        bitrate="8M",
        preset="medium",
        threads=4,
        temp_audiofile=output_path.replace(".mp4", "_tmp.m4a"),
        remove_temp=True,
        verbose=False,
        logger=None,
    )

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 50_000:
        raise RuntimeError("Video export produced no/tiny file")

    logger.info("Video exported: %s  (%.0f KB)",
                output_path, os.path.getsize(output_path) / 1024)

    # ── Cleanup ───────────────────────────────────────────────
    for c in audio_clips:
        try: c.close()
        except Exception: pass
    if music_clip is not None:
        try: music_clip.close()
        except Exception: pass
    for c in video_clips:
        try: c.close()
        except Exception: pass
    try: video.close()
    except Exception: pass

    return output_path
