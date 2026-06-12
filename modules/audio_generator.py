"""Audio generation: edge-tts (primary) + pyttsx3 (offline fallback),
per-paragraph narration for tight image/audio sync, and background music."""
import asyncio
import os
import numpy as np
from pathlib import Path
from config import VOICES


# ── Narration helpers ─────────────────────────────────────────

def _make_silence(duration: float = 0.22, fps: int = 44100):
    """Return a short stereo silence AudioArrayClip to pad between paragraphs."""
    from moviepy.audio.AudioClip import AudioArrayClip
    n = max(1, int(fps * duration))
    arr = np.zeros((n, 2), dtype=np.float32)
    return AudioArrayClip(arr, fps=fps)


async def _tts_edge(text: str, voice: str, output_path: str, rate: str = "+0%") -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


async def _tts_edge_with_timings(text: str, voice: str, output_path: str, rate: str = "+0%") -> list[dict]:
    """Synthesize audio AND capture per-word timings via WordBoundary events."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    word_timings: list[dict] = []
    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            ctype = chunk.get("type")
            if ctype == "audio":
                f.write(chunk["data"])
            elif ctype == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                duration = chunk["duration"] / 10_000_000
                word_timings.append({
                    "text": chunk["text"],
                    "start": round(start, 4),
                    "end": round(start + duration, 4),
                })
    return word_timings


def _tts_pyttsx3(text: str, output_path: str) -> None:
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty("rate", 165)
    engine.save_to_file(text, output_path)
    engine.runAndWait()


def _synthesize_to_mp3(text: str, voice_id: str, output_path: str, rate: str = "+0%") -> list[dict]:
    """Single-paragraph synthesis with edge-tts → pyttsx3 fallback.
    Returns list of word timing dicts (empty list if fallback was used)."""
    try:
        word_timings = asyncio.run(_tts_edge_with_timings(text, voice_id, output_path, rate=rate))
        if os.path.exists(output_path) and os.path.getsize(output_path) > 800:
            return word_timings
    except Exception as e:
        print(f"edge-tts failed ({e}), trying pyttsx3 fallback")

    wav_path = output_path.replace(".mp3", "_fb.wav")
    _tts_pyttsx3(text, wav_path)
    from moviepy.editor import AudioFileClip
    clip = AudioFileClip(wav_path)
    clip.write_audiofile(output_path, verbose=False, logger=None)
    clip.close()
    try: os.remove(wav_path)
    except Exception: pass
    return []  # pyttsx3 has no word boundaries; subtitle renderer will fall back to even split


# ── Per-paragraph narration (NEW — primary entry point) ───────

_SILENCE_BETWEEN_PARAS = 0.22   # seconds — prevents hard cutoff between paragraphs


def generate_narration_per_paragraph(
    paragraphs: list[str],
    voice_label: str,
    project_dir: str,
    progress_cb=None,
    voice_rate: str = "+0%",
    voice_rates: list[str] | None = None,
) -> tuple[str, list[str], list[float], list[list[dict]]]:
    """Synthesise each paragraph separately, capture word timings, and produce a
    concatenated narration MP3.

    voice_rates : optional per-paragraph rate list from content_analyzer.
                  When provided, overrides voice_rate for each paragraph.

    Returns (combined_mp3_path, per_paragraph_paths, per_paragraph_durations,
             per_paragraph_word_timings) — word timings are LOCAL to each
             paragraph (start=0 when the paragraph begins).
    """
    voice_id = VOICES.get(voice_label, "en-US-GuyNeural")

    paths: list[str] = []
    durations: list[float] = []
    all_word_timings: list[list[dict]] = []

    from moviepy.editor import AudioFileClip, concatenate_audioclips

    total = len(paragraphs)
    for i, para in enumerate(paragraphs):
        if progress_cb:
            progress_cb(i, total, f"Voicing paragraph {i + 1} of {total}...")

        # Per-paragraph rate: use per-para list when available, else global rate
        rate = (voice_rates[i] if voice_rates and i < len(voice_rates)
                else voice_rate)

        out = os.path.join(project_dir, f"audio_{i:02d}.mp3")
        word_timings = _synthesize_to_mp3(para, voice_id, out, rate=rate)

        if not os.path.exists(out) or os.path.getsize(out) < 800:
            raise RuntimeError(f"Audio synthesis failed for paragraph {i}")

        clip = AudioFileClip(out)
        dur = clip.duration
        clip.close()
        if dur <= 0.1:
            raise RuntimeError(f"Paragraph {i} audio has zero duration")
        paths.append(out)
        durations.append(dur)
        all_word_timings.append(word_timings)

    # Save global word timings (accounting for silence gaps between paragraphs)
    try:
        import json
        offset = 0.0
        global_timings = []
        for dur, wts in zip(durations, all_word_timings):
            for w in wts:
                global_timings.append({
                    "text":  w["text"],
                    "start": round(w["start"] + offset, 4),
                    "end":   round(w["end"]   + offset, 4),
                })
            offset += dur + _SILENCE_BETWEEN_PARAS
        with open(os.path.join(project_dir, "word_timings.json"), "w", encoding="utf-8") as f:
            json.dump(global_timings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    # Concatenate with a short silence gap between each paragraph to prevent
    # the hard audio cutoff / jarring jump between lines.
    combined = os.path.join(project_dir, "audio_narration.mp3")
    clips = [AudioFileClip(p) for p in paths]
    silence = _make_silence(_SILENCE_BETWEEN_PARAS)
    interleaved = []
    for idx, clip in enumerate(clips):
        interleaved.append(clip)
        if idx < len(clips) - 1:
            interleaved.append(silence)
    merged = concatenate_audioclips(interleaved)
    merged.write_audiofile(combined, verbose=False, logger=None)
    merged.close()
    for c in clips:
        c.close()

    # Adjust durations to include the silence so image/audio sync stays correct
    padded_durations = []
    for i, dur in enumerate(durations):
        padded_durations.append(
            dur + (_SILENCE_BETWEEN_PARAS if i < len(durations) - 1 else 0.0)
        )

    return combined, paths, padded_durations, all_word_timings


# ── Cloned voice narration (commercial-safe Chatterbox) ───────

def generate_cloned_narration_per_paragraph(
    paragraphs: list[str],
    reference_wav: str,
    project_dir: str,
    progress_cb=None,
    **gen_params,
) -> tuple[str, list[str], list[float], list[list[dict]]]:
    """Narrate each paragraph in the user's cloned voice (Chatterbox).

    Same 4-tuple shape as generate_narration_per_paragraph(). No word timings, so
    subtitles fall back to an even split (the cloner gives no word boundaries).
    """
    from modules import voice_clone
    from moviepy.editor import AudioFileClip, concatenate_audioclips

    paths: list[str] = []
    durations: list[float] = []
    total = len(paragraphs)
    for i, para in enumerate(paragraphs):
        if progress_cb:
            progress_cb(i, total, f"Cloning your voice — paragraph {i + 1} of {total}...")
        wav_tmp = os.path.join(project_dir, f"audio_{i:02d}.wav")
        voice_clone.synthesize(para, reference_wav, wav_tmp, **gen_params)
        out_mp3 = os.path.join(project_dir, f"audio_{i:02d}.mp3")
        clip = AudioFileClip(wav_tmp)
        dur = clip.duration
        clip.write_audiofile(out_mp3, verbose=False, logger=None)
        clip.close()
        try:
            os.remove(wav_tmp)
        except Exception:
            pass
        if dur <= 0.05:
            raise RuntimeError(f"Cloned audio for paragraph {i} is empty")
        paths.append(out_mp3)
        durations.append(dur)

    combined = os.path.join(project_dir, "audio_narration.mp3")
    clips = [AudioFileClip(p) for p in paths]
    merged = concatenate_audioclips(clips)
    merged.write_audiofile(combined, verbose=False, logger=None)
    merged.close()
    for c in clips:
        c.close()

    word_timings: list[list[dict]] = [[] for _ in paragraphs]
    return combined, paths, durations, word_timings


# ── Human voiceover (user-supplied narration replaces TTS) ────

def prepare_human_voiceover(
    voiceover_path: str,
    paragraphs: list[str],
    project_dir: str,
    progress_cb=None,
) -> tuple[str, list[str], list[float], list[list[dict]]]:
    """Use a user-supplied recording instead of TTS — the strongest human-input signal.

    The single track is sliced into one segment per paragraph (weighted by word
    count) so the existing per-scene assembler/sync keeps working untouched.
    No word timings are produced, so subtitles fall back to an even split.

    Returns the same 4-tuple shape as generate_narration_per_paragraph().
    """
    from moviepy.editor import AudioFileClip

    src = AudioFileClip(voiceover_path)
    total = src.duration or 0.0
    if total <= 0.2:
        src.close()
        raise RuntimeError("Uploaded voiceover has no usable audio")

    n = max(1, len(paragraphs))
    counts = [max(1, len(p.split())) for p in paragraphs] or [1]
    wsum = sum(counts)

    paths: list[str] = []
    durations: list[float] = []
    t0 = 0.0
    for i in range(n):
        if progress_cb:
            progress_cb(i, n, f"Slicing your voiceover — part {i + 1} of {n}...")
        seg = total * counts[i] / wsum
        t1 = total if i == n - 1 else min(total, t0 + seg)
        if t1 - t0 < 0.05:                      # guarantee a non-empty slice
            t1 = min(total, t0 + 0.05)
        out = os.path.join(project_dir, f"audio_{i:02d}.mp3")
        sub = src.subclip(t0, t1)
        sub.write_audiofile(out, verbose=False, logger=None)
        sub.close()
        clip = AudioFileClip(out)
        dur = clip.duration
        clip.close()
        paths.append(out)
        durations.append(dur)
        t0 = t1
    src.close()

    # Canonical narration track = a normalised copy of the original recording.
    combined = os.path.join(project_dir, "audio_narration.mp3")
    full = AudioFileClip(voiceover_path)
    full.write_audiofile(combined, verbose=False, logger=None)
    full.close()

    word_timings: list[list[dict]] = [[] for _ in paragraphs]
    return combined, paths, durations, word_timings


# ── Legacy single-shot narration (kept for compatibility) ─────

def generate_narration(text: str, voice_label: str, output_path: str) -> float:
    voice_id = VOICES.get(voice_label, "en-US-GuyNeural")
    _synthesize_to_mp3(text, voice_id, output_path)
    from moviepy.editor import AudioFileClip
    clip = AudioFileClip(output_path)
    duration = clip.duration
    clip.close()
    if duration <= 0:
        raise RuntimeError("Generated audio has zero duration")
    return duration


# ── Background music via NumPy sine synthesis ─────────────────

def generate_music(mood: str, duration: float, output_path: str) -> str:
    if mood == "None":
        return ""

    sr = 44100
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    if mood == "Epic/Dramatic":
        wave = (0.10 * np.sin(2 * np.pi * 40 * t)
                + 0.08 * np.sin(2 * np.pi * 80 * t)
                + 0.06 * np.sin(2 * np.pi * 120 * t)
                + 0.04 * np.sin(2 * np.pi * 160 * t))

    elif mood == "Calm/Peaceful":
        wave = (0.12 * np.sin(2 * np.pi * 432 * t)
                + 0.04 * np.sin(2 * np.pi * 288 * t))

    elif mood == "Dark/Suspense":
        wave = (0.09 * np.sin(2 * np.pi * 55 * t)
                + 0.07 * np.sin(2 * np.pi * 82.4 * t)
                + 0.05 * np.sin(2 * np.pi * 110 * t))
        wave *= (0.7 + 0.3 * np.sin(2 * np.pi * 0.4 * t))

    elif mood == "Uplifting":
        freqs = [261.63, 329.63, 392.0, 523.25, 659.25]
        wave = np.zeros(n)
        step = int(sr * 60 / 120)
        for i, freq in enumerate(freqs):
            phase_start = (i * step) % n
            idxs = np.arange(n)
            mask = ((idxs - phase_start) % (step * len(freqs))) < step
            wave[mask] += 0.07 * np.sin(2 * np.pi * freq * idxs[mask] / sr)

    elif mood == "Mystery":
        wave = (0.10 * np.sin(2 * np.pi * 180 * t)
                * np.sin(2 * np.pi * 0.25 * t)
                + 0.05 * np.sin(2 * np.pi * 270 * t)
                * np.sin(2 * np.pi * 0.4 * t))

    else:
        wave = np.zeros(n)

    fade = min(int(sr * 2), n // 4)
    if fade > 0:
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)

    mx = np.max(np.abs(wave))
    if mx > 0:
        wave = wave / mx * 0.4

    import scipy.io.wavfile as wav
    wav_path = output_path.replace(".mp3", "_music.wav")
    wav.write(wav_path, sr, (wave * 32767).astype(np.int16))
    from moviepy.editor import AudioFileClip
    clip = AudioFileClip(wav_path)
    clip.write_audiofile(output_path, fps=sr, verbose=False, logger=None)
    clip.close()
    try:
        os.remove(wav_path)
    except Exception:
        pass
    return output_path
