import asyncio
import edge_tts


async def generate_tts(text: str, voice: str, output_path: str) -> float:
    """Generate TTS audio and return duration in seconds."""
    if not text or not text.strip():
        return 0.0

    communicate = edge_tts.Communicate(text.strip(), voice)
    await communicate.save(output_path)

    return _get_audio_duration(output_path, text)


def _get_audio_duration(path: str, text: str) -> float:
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        # Fallback: estimate from word count at ~145 wpm
        return len(text.split()) / 2.4
