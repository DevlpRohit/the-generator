"""Local voice cloning via Chatterbox (Resemble AI).

MIT-licensed — **code and model weights are free for commercial use**, so cloned
narration can be used in monetized videos (unlike XTTS-v2's non-commercial CPML).
Runs fully offline after a one-time model download. CPU-capable; GPU auto-used.

Chatterbox also embeds an inaudible Perth neural watermark in its output marking
it as AI-generated — which is fine (honest AI provenance, no audible effect).
"""
import logging
import os
import re

logger = logging.getLogger(__name__)

_model = None        # cached model (heavy — load once per process)
_load_error = ""

# Faithful/steady defaults: low exaggeration + higher cfg_weight keep the clone
# close to the reference; lower temperature reduces random drift.
_GEN_DEFAULTS = dict(exaggeration=0.35, cfg_weight=0.6, temperature=0.7)


def is_available() -> bool:
    try:
        import torch          # noqa: F401
        import chatterbox     # noqa: F401
        return True
    except Exception:
        return False


def status() -> dict:
    try:
        import torch
        torch_ok, device = True, ("cuda" if torch.cuda.is_available() else "cpu")
    except Exception:
        torch_ok, device = False, "none"
    try:
        import chatterbox     # noqa: F401
        cb_ok = True
    except Exception:
        cb_ok = False
    return {
        "engine": "chatterbox", "torch": torch_ok, "chatterbox": cb_ok,
        "device": device, "ready": torch_ok and cb_ok,
        "model_loaded": _model is not None, "last_error": _load_error,
    }


def _get_model():
    """Lazily load + cache the Chatterbox model. First call downloads the weights."""
    global _model, _load_error
    if _model is not None:
        return _model
    try:
        import torch
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading Chatterbox on %s (first run downloads the model)...", device)
        _model = ChatterboxTTS.from_pretrained(device=device)
        _load_error = ""
        return _model
    except Exception as e:
        _load_error = str(e)[:300]
        logger.error("Failed to load Chatterbox: %s", _load_error)
        raise


def _chunks(text: str, max_chars: int = 280) -> list[str]:
    """Split into sentence-sized chunks so each generate() stays in a stable range."""
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    out, cur = [], ""
    for s in sents:
        if not s:
            continue
        if len(cur) + len(s) + 1 <= max_chars:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                out.append(cur)
            cur = s
    if cur:
        out.append(cur)
    return out or [text.strip()]


def _trim_silence(wav, sr: int, thresh: float = 0.015, keep_ms: int = 55):
    """Trim leading/trailing near-silence from a (1,N) waveform, keeping a short
    pad so words aren't clipped. Removes Chatterbox's irregular end padding."""
    import torch
    w = wav.squeeze(0) if wav.dim() == 2 else wav
    idx = (w.abs() > thresh).nonzero(as_tuple=False)
    if idx.numel() == 0:
        return wav
    pad = int(sr * keep_ms / 1000)
    start = max(0, int(idx[0].item()) - pad)
    end = min(w.shape[-1], int(idx[-1].item()) + pad)
    return w[start:end].unsqueeze(0)


def synthesize(text: str, reference_wav, output_path: str, **overrides) -> str:
    """Speak `text` in the voice of `reference_wav`, writing a WAV to output_path.

    reference_wav may be a path or list (first is used — Chatterbox takes one clip).
    Extra kwargs override generation defaults (exaggeration, cfg_weight, temperature).
    """
    if not text or not text.strip():
        raise ValueError("Empty text for voice cloning")
    ref = reference_wav[0] if isinstance(reference_wav, (list, tuple)) else reference_wav
    if not os.path.exists(ref):
        raise FileNotFoundError(f"Reference voice sample not found: {ref}")

    import torch
    import torchaudio as ta
    model = _get_model()
    sr = model.sr
    params = {**_GEN_DEFAULTS, **overrides}

    # Even pacing: trim each chunk's silence, rejoin with ONE consistent gap so the
    # narration has uniform, natural pauses (no random long/short gaps).
    gap = torch.zeros(1, int(sr * 0.16))      # pause between sentences
    pieces = []
    for chunk in _chunks(text):
        wav = _trim_silence(model.generate(chunk, audio_prompt_path=ref, **params), sr)
        if pieces:
            pieces.append(gap)
        pieces.append(wav)
    audio = torch.cat(pieces, dim=-1) if len(pieces) > 1 else pieces[0]
    # Small consistent tail so paragraphs don't run into each other abruptly.
    audio = torch.cat([audio, torch.zeros(1, int(sr * 0.12))], dim=-1)
    # Save standard 16-bit PCM (not float) so downstream tools (moviepy, wave) read it.
    ta.save(output_path, audio, sr, encoding="PCM_S", bits_per_sample=16)

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        raise RuntimeError("Chatterbox produced no audio")
    return output_path
