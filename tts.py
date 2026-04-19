"""
TTS via Kokoro-ONNX (PT-BR).

Downloads model and voice files on first use.
Exposes a single function: synthesize(text, voice) -> bytes (WAV).
Long texts are split into sentences and concatenated automatically.
"""
import io
import os
import re
import numpy as np
import onnxruntime as rt
import soundfile as sf
from kokoro_onnx import Tokenizer, SAMPLE_RATE, MAX_PHONEME_LENGTH
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


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on punctuation, keeping delimiter attached."""
    parts = re.split(r'(?<=[.!?;:\n])\s*', text.strip())
    return [p.strip() for p in parts if p.strip()]


def _synth_chunk(sess, tok, voice_arr, chunk: str, speed: float) -> np.ndarray | None:
    """Synthesize a single chunk. Returns None if chunk produces no tokens."""
    phonemes = tok.phonemize(chunk, lang="pt-br")
    tokens_raw = tok.tokenize(phonemes)
    if not tokens_raw:
        return None
    # Limit to MAX_PHONEME_LENGTH - 2 (pad tokens)
    tokens_raw = tokens_raw[: MAX_PHONEME_LENGTH - 2]
    style_idx = min(len(tokens_raw), len(voice_arr) - 1)
    style = voice_arr[style_idx][np.newaxis, :]        # (1, 256)
    tokens = np.array([[0, *tokens_raw, 0]], dtype=np.int64)
    speed_arr = np.array([speed], dtype=np.float32)
    return sess.run(None, {"input_ids": tokens, "style": style, "speed": speed_arr})[0][0]


def synthesize(text: str, voice: str = "pf_dora", speed: float = 1.0) -> bytes:
    """Returns WAV audio as bytes. Long texts are split into sentences."""
    sess = _get_session()
    tok = _get_tokenizer()
    voice_arr = _load_voice(voice)

    sentences = _split_sentences(text)
    if not sentences:
        return _to_wav_bytes(np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.float32))

    # Group sentences into chunks whose phoneme string fits within MAX_PHONEME_LENGTH
    # tokenize() checks len(phoneme_string), so we compare string length
    LIMIT = MAX_PHONEME_LENGTH - 2
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        candidate = (current + " " + sent).strip() if current else sent
        ph = tok.phonemize(candidate, lang="pt-br")
        if len(ph) > LIMIT:
            if current:
                chunks.append(current)
            # If even the single sentence is too long, split by words
            if len(tok.phonemize(sent, lang="pt-br")) > LIMIT:
                words = sent.split()
                sub = ""
                for w in words:
                    cand2 = (sub + " " + w).strip() if sub else w
                    if len(tok.phonemize(cand2, lang="pt-br")) > LIMIT:
                        if sub:
                            chunks.append(sub)
                        sub = w
                    else:
                        sub = cand2
                if sub:
                    chunks.append(sub)
                current = ""
            else:
                current = sent
        else:
            current = candidate
    if current:
        chunks.append(current)

    # Synthesize each chunk and concatenate with a short silence between
    silence_gap = np.zeros(int(SAMPLE_RATE * 0.15), dtype=np.float32)
    parts: list[np.ndarray] = []
    for chunk in chunks:
        audio = _synth_chunk(sess, tok, voice_arr, chunk, speed)
        if audio is not None:
            if parts:
                parts.append(silence_gap)
            parts.append(audio)

    if not parts:
        return _to_wav_bytes(np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.float32))

    return _to_wav_bytes(np.concatenate(parts))


def _to_wav_bytes(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf.read()
