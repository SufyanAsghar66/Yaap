"""
Audio Processing Utilities
Used by the voice training Celery task to prepare WAV files
before sending to the XTTS embedding service.

Pipeline per sample:
  1. Decode WAV / convert to 16 kHz mono PCM
  2. Measure noise floor (reject if too loud)
  3. Apply Silero VAD to trim leading/trailing silence
  4. Peak-normalize to –3 dBFS
  5. Re-encode as WAV 16 kHz mono 16-bit PCM

All processing is done in-memory where possible.
Writes temp files to /tmp only when required by external tools.
"""

import logging
import os
import struct
import tempfile
import wave
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE    = 16_000   # Hz — required by XTTS
TARGET_CHANNELS       = 1        # mono
TARGET_SAMPLE_WIDTH   = 2        # 16-bit
MIN_DURATION_SECS     = 3.0
MAX_DURATION_SECS     = 30.0
NOISE_FLOOR_THRESHOLD = -40.0    # dBFS — warn if ambient noise louder than this
PEAK_TARGET_DBFS      = -3.0     # normalize to this peak level


# ─── Public API ───────────────────────────────────────────────────────────────

def validate_and_process_wav(raw_bytes: bytes, filename: str = "audio.wav") -> dict:
    """
    Full validation + processing pipeline.

    Returns:
        {
            "ok":              bool,
            "error":           str | None,     # human-readable error if not ok
            "processed_bytes": bytes | None,   # processed WAV bytes
            "duration":        float,          # seconds
            "noise_floor_db":  float,
            "sample_rate":     int,
        }
    """
    result = {
        "ok":              False,
        "error":           None,
        "processed_bytes": None,
        "duration":        0.0,
        "noise_floor_db":  0.0,
        "sample_rate":     TARGET_SAMPLE_RATE,
    }

    # ── 1. Convert to standard format ─────────────────────────────────────────
    try:
        pcm_bytes, sample_rate = _to_16khz_mono_pcm(raw_bytes, filename)
    except Exception as e:
        result["error"] = f"Could not decode audio file: {e}"
        return result

    # ── 2. Duration check ─────────────────────────────────────────────────────
    num_samples = len(pcm_bytes) // TARGET_SAMPLE_WIDTH
    duration    = num_samples / TARGET_SAMPLE_RATE
    result["duration"]    = duration
    result["sample_rate"] = TARGET_SAMPLE_RATE

    if duration < MIN_DURATION_SECS:
        result["error"] = f"Recording too short ({duration:.1f}s). Minimum is {MIN_DURATION_SECS}s."
        return result
    if duration > MAX_DURATION_SECS:
        result["error"] = f"Recording too long ({duration:.1f}s). Maximum is {MAX_DURATION_SECS}s."
        return result

    # ── 3. Noise floor measurement ────────────────────────────────────────────
    noise_floor = _measure_noise_floor(pcm_bytes)
    result["noise_floor_db"] = noise_floor
    if noise_floor > NOISE_FLOOR_THRESHOLD:
        logger.warning(
            "High ambient noise floor: %.1f dBFS (threshold %.1f)",
            noise_floor, NOISE_FLOOR_THRESHOLD,
        )
        # Warn but do not reject — user is warned in the UI

    # ── 4. VAD trimming ───────────────────────────────────────────────────────
    try:
        pcm_bytes = _apply_vad(pcm_bytes)
        # Recompute duration after VAD
        duration  = len(pcm_bytes) / TARGET_SAMPLE_WIDTH / TARGET_SAMPLE_RATE
        result["duration"] = duration
        if duration < MIN_DURATION_SECS:
            result["error"] = "Too much silence detected. Please speak clearly and try again."
            return result
    except Exception as e:
        logger.warning("VAD trimming failed (continuing without trim): %s", e)

    # ── 5. Peak normalization ─────────────────────────────────────────────────
    try:
        pcm_bytes = _peak_normalize(pcm_bytes)
    except Exception as e:
        logger.warning("Peak normalization failed (continuing): %s", e)

    # ── 6. Re-encode as standard WAV ──────────────────────────────────────────
    result["processed_bytes"] = _encode_wav(pcm_bytes)
    result["ok"]              = True
    return result


def get_wav_duration(wav_bytes: bytes) -> float:
    """Quick duration check without full processing."""
    try:
        buf = BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 0.0


# ─── Internal Helpers ─────────────────────────────────────────────────────────

def _to_16khz_mono_pcm(raw_bytes: bytes, filename: str) -> tuple[bytes, int]:
    """
    Convert any audio format to 16 kHz mono 16-bit PCM using pydub (ffmpeg backend).
    Falls back to raw wave reading if the input is already a valid WAV.
    """
    try:
        from pydub import AudioSegment

        # Determine format from filename extension
        ext = Path(filename).suffix.lower().lstrip(".") or "wav"
        audio = AudioSegment.from_file(BytesIO(raw_bytes), format=ext)

        # Convert to target spec
        audio = (
            audio
            .set_frame_rate(TARGET_SAMPLE_RATE)
            .set_channels(TARGET_CHANNELS)
            .set_sample_width(TARGET_SAMPLE_WIDTH)
        )
        pcm = audio.raw_data
        return pcm, TARGET_SAMPLE_RATE

    except ImportError:
        # pydub/ffmpeg not available — try raw wave parse
        logger.warning("pydub not available; attempting raw WAV parse")
        buf = BytesIO(raw_bytes)
        with wave.open(buf, "rb") as wf:
            sr = wf.getframerate()
            pcm = wf.readframes(wf.getnframes())
            return pcm, sr


def _measure_noise_floor(pcm_bytes: bytes) -> float:
    """
    Return the RMS level of the quietest 500 ms window in dBFS.
    This estimates the ambient noise floor.
    """
    import math
    window_size = TARGET_SAMPLE_RATE // 2  # 500 ms in samples
    samples     = [
        struct.unpack_from("<h", pcm_bytes, i)[0]
        for i in range(0, len(pcm_bytes) - 1, TARGET_SAMPLE_WIDTH)
    ]

    if len(samples) < window_size:
        return _rms_dbfs(samples)

    min_rms = float("inf")
    for start in range(0, len(samples) - window_size, window_size):
        window  = samples[start:start + window_size]
        rms     = _rms_dbfs(window)
        if rms < min_rms:
            min_rms = rms

    return min_rms if min_rms != float("inf") else -96.0


def _rms_dbfs(samples: list[int]) -> float:
    import math
    if not samples:
        return -96.0
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    if rms == 0:
        return -96.0
    return 20 * math.log10(rms / 32768.0)


def _apply_vad(pcm_bytes: bytes) -> bytes:
    """
    Apply Silero VAD to remove leading/trailing silence.
    Requires: torch, torchaudio (installed with XTTS dependencies).
    Falls back to a simple energy-based trimmer if torch is unavailable.
    """
    try:
        import torch
        import torchaudio

        # Convert PCM bytes to float tensor
        pcm_np = _pcm_bytes_to_float_tensor(pcm_bytes)

        # Load Silero VAD (cached after first load)
        model, utils = torch.hub.load(
            repo_or_dir = "snakers4/silero-vad",
            model       = "silero_vad",
            force_reload = False,
            trust_repo  = True,
        )
        get_speech_timestamps = utils[0]

        timestamps = get_speech_timestamps(
            pcm_np,
            model,
            sampling_rate    = TARGET_SAMPLE_RATE,
            min_speech_duration_ms = 250,
            min_silence_duration_ms = 100,
        )

        if not timestamps:
            logger.warning("VAD found no speech segments")
            return pcm_bytes

        # Trim to speech region [first_start : last_end]
        start_sample = timestamps[0]["start"]
        end_sample   = timestamps[-1]["end"]
        trimmed      = pcm_np[start_sample:end_sample]

        return _float_tensor_to_pcm_bytes(trimmed)

    except Exception as e:
        logger.warning("Silero VAD failed, using energy-based trimmer: %s", e)
        return _energy_trim(pcm_bytes)


def _energy_trim(pcm_bytes: bytes, threshold_dbfs: float = -50.0) -> bytes:
    """
    Simple energy-based silence trimmer — fallback when torch is unavailable.
    Removes frames below threshold from start and end.
    """
    frame_size = TARGET_SAMPLE_RATE // 100  # 10 ms frames
    samples    = [
        struct.unpack_from("<h", pcm_bytes, i)[0]
        for i in range(0, len(pcm_bytes) - 1, TARGET_SAMPLE_WIDTH)
    ]
    frames  = [samples[i:i + frame_size] for i in range(0, len(samples), frame_size)]
    is_loud = [_rms_dbfs(f) > threshold_dbfs for f in frames]

    if not any(is_loud):
        return pcm_bytes

    first = next(i for i, v in enumerate(is_loud) if v)
    last  = len(is_loud) - next(i for i, v in enumerate(reversed(is_loud)) if v)

    trimmed_samples = []
    for frame in frames[first:last]:
        trimmed_samples.extend(frame)

    return struct.pack(f"<{len(trimmed_samples)}h", *trimmed_samples)


def _peak_normalize(pcm_bytes: bytes, target_dbfs: float = PEAK_TARGET_DBFS) -> bytes:
    """Scale PCM so peak amplitude equals target_dbfs."""
    import math
    samples  = [struct.unpack_from("<h", pcm_bytes, i)[0] for i in range(0, len(pcm_bytes) - 1, TARGET_SAMPLE_WIDTH)]
    peak     = max(abs(s) for s in samples) if samples else 0
    if peak == 0:
        return pcm_bytes
    target_peak = int(32767 * (10 ** (target_dbfs / 20)))
    scale       = target_peak / peak
    normalized  = [max(-32768, min(32767, int(s * scale))) for s in samples]
    return struct.pack(f"<{len(normalized)}h", *normalized)


def _encode_wav(pcm_bytes: bytes) -> bytes:
    """Wrap raw PCM bytes in a WAV container."""
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(TARGET_CHANNELS)
        wf.setsampwidth(TARGET_SAMPLE_WIDTH)
        wf.setframerate(TARGET_SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _pcm_bytes_to_float_tensor(pcm_bytes: bytes):
    import torch
    samples = [struct.unpack_from("<h", pcm_bytes, i)[0] for i in range(0, len(pcm_bytes) - 1, TARGET_SAMPLE_WIDTH)]
    return torch.tensor(samples, dtype=torch.float32) / 32768.0


def _float_tensor_to_pcm_bytes(tensor) -> bytes:
    samples = (tensor.numpy() * 32768.0).clip(-32768, 32767).astype("int16")
    return samples.tobytes()
