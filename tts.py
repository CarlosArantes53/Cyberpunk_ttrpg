"""
TTS via Kokoro-ONNX (PT-BR).

Downloads model and voice files on first use.
Exposes a single function: synthesize(text, voice) -> bytes (WAV).
"""
import io
import os
import numpy as np
import onnxruntime as rt
import soundfile as sf
from kokoro_onnx import Tokenizer, SAMPLE_RATE
from huggingface_hub import hf_hub_download

REPO = "onnx-community/Kokoro-82M-v1.0-ONNX"
DATA_DIR = os.path.join("data", "kokoro")
MODEL_LOCAL = os.path.join(DATA_DIR, "onnx", "model_quantized.onnx")

VOICES = {
    "pf_dora": os.path.join(DATA_DIR, "voices", "pf_dora.bin"),
    "pm_alex": os.path.join(DATA_DIR, "voices", "pm_alex.bin"),
}

_sess: rt.InferenceSession | None = None
_tok: Tokenizer | None = None
_voice_cache: dict[str, np.ndarray] = {}


def _ensure_files() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(MODEL_LOCAL):
        hf_hub_download(repo_id=REPO, filename="onnx/model_quantized.onnx", local_dir=DATA_DIR)
    for name, local_path in VOICES.items():
        if not os.path.exists(local_path):
            hf_hub_download(repo_id=REPO, filename=f"voices/{name}.bin", local_dir=DATA_DIR)


def _get_session() -> rt.InferenceSession:
    global _sess
    if _sess is None:
        _ensure_files()
        _sess = rt.InferenceSession(MODEL_LOCAL, providers=["CPUExecutionProvider"])
    return _sess


def _get_tokenizer() -> Tokenizer:
    global _tok
    if _tok is None:
        _tok = Tokenizer()
    return _tok


def _load_voice(name: str) -> np.ndarray:
    if name not in _voice_cache:
        path = VOICES.get(name)
        if path is None or not os.path.exists(path):
            raise ValueError(f"Voz '{name}' não disponível.")
        _voice_cache[name] = np.fromfile(path, dtype=np.float32).reshape(-1, 256)
    return _voice_cache[name]


def synthesize(text: str, voice: str = "pf_dora", speed: float = 1.0) -> bytes:
    """Returns WAV audio as bytes."""
    sess = _get_session()
    tok = _get_tokenizer()
    voice_arr = _load_voice(voice)

    # Phonemize and tokenize
    phonemes = tok.phonemize(text, lang="pt-br")
    tokens_raw = tok.tokenize(phonemes)
    if not tokens_raw:
        # Silence fallback for empty phonemes
        silence = np.zeros(int(SAMPLE_RATE * 0.5), dtype=np.float32)
        return _to_wav_bytes(silence)

    # Clamp index so we never go out of bounds
    style_idx = min(len(tokens_raw), len(voice_arr) - 1)
    style = voice_arr[style_idx][np.newaxis, :]  # (1, 256)
    tokens = np.array([[0, *tokens_raw, 0]], dtype=np.int64)  # (1, seq+2)
    speed_arr = np.array([speed], dtype=np.float32)

    audio = sess.run(None, {"input_ids": tokens, "style": style, "speed": speed_arr})[0][0]
    return _to_wav_bytes(audio)


def _to_wav_bytes(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()
