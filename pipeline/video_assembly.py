import os
import re
import subprocess
import shutil
from typing import List, Dict, Optional, Callable


def prepare_image(img_path: str, target_w: int = 1920, target_h: int = 1080) -> str:
    """Center-crop / resize image to exact target dimensions."""
    from PIL import Image

    out = img_path.rsplit(".", 1)[0] + "_prep.jpg"
    if os.path.exists(out):
        return out

    with Image.open(img_path) as img:
        img = img.convert("RGB")
        src_r = img.width / img.height
        tgt_r = target_w / target_h

        if src_r > tgt_r:
            new_h, new_w = target_h, int(img.width * target_h / img.height)
        else:
            new_w, new_h = target_w, int(img.height * target_w / img.width)

        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))
        img.save(out, "JPEG", quality=95)

    return out


def assemble_video(
    sections: List[Dict],
    output_path: str,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """Build video from image+audio sections using MoviePy."""
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

    clips = []
    for i, sec in enumerate(sections):
        if progress_cb:
            progress_cb(f"Building clip {i + 1}/{len(sections)}")

        try:
            prepped = prepare_image(sec["image_path"])
            audio = AudioFileClip(sec["audio_path"])
            dur = audio.duration
            if dur <= 0:
                audio.close()
                continue

            clip = ImageClip(prepped).set_duration(dur).set_audio(audio)
            clips.append(clip)
        except Exception as exc:
            print(f"Skipping section {i}: {exc}")

    if not clips:
        raise RuntimeError("No valid clips were produced")

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
        temp_audiofile=output_path.replace(".mp4", "_tmp.m4a"),
        remove_temp=True,
        verbose=False,
        logger=None,
    )

    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    try:
        final.close()
    except Exception:
        pass

    return output_path


def _srt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(sections: List[Dict], output_path: str) -> str:
    """Generate an SRT file from section narrations + durations."""
    lines: List[str] = []
    counter = 1
    current = 0.0

    for sec in sections:
        text = sec.get("narration", "").strip()
        dur = sec.get("duration", 0)
        if not text or dur <= 0:
            current += dur
            continue

        words = text.split()
        wps = len(words) / dur

        chunk_size = 10
        chunks = [words[i : i + chunk_size] for i in range(0, len(words), chunk_size)]
        t = current
        for chunk in chunks:
            chunk_dur = len(chunk) / wps
            lines += [
                str(counter),
                f"{_srt_ts(t)} --> {_srt_ts(t + chunk_dur)}",
                " ".join(chunk),
                "",
            ]
            counter += 1
            t += chunk_dur

        current += dur

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> str:
    """Burn SRT subtitles into video via FFmpeg."""
    # FFmpeg on Windows needs the colon in drive letter escaped inside filter args
    srt_fwd = srt_path.replace("\\", "/")
    srt_esc = re.sub(r"^([A-Za-z]):", r"\1\\:", srt_fwd)

    style = (
        "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Shadow=1,Alignment=2,MarginV=40"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"subtitles='{srt_esc}':force_style='{style}'",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0 or not os.path.exists(output_path):
        print(f"Subtitle burn failed (FFmpeg rc={result.returncode}); copying raw video")
        print(result.stderr[-600:])
        shutil.copy2(video_path, output_path)

    return output_path
