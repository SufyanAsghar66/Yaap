"""
Phase 7 — Translation Pipeline Tests
Covers: TranslationConsumer, audio buffering, pipeline steps,
silence detection, XTTS client, Whisper client.
"""

import io
import struct
import wave
import math
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from apps.calls.models import CallRoom


# ─── Audio Helpers ────────────────────────────────────────────────────────────

def make_pcm(duration_secs: float = 1.0, sample_rate: int = 16000, amplitude: int = 8000) -> bytes:
    """Generate sine wave PCM bytes."""
    num_samples = int(duration_secs * sample_rate)
    samples     = [int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(num_samples)]
    return struct.pack(f"<{num_samples}h", *samples)


def make_silence(duration_secs: float = 1.0, sample_rate: int = 16000) -> bytes:
    num_samples = int(duration_secs * sample_rate)
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


def make_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


# ─── Silence Detection ────────────────────────────────────────────────────────

class TestSilenceDetection:

    def test_silence_detected(self):
        from channels_consumers.translation_consumer import _is_silent
        silent = make_silence(0.04)
        assert _is_silent(silent) is True

    def test_speech_not_silent(self):
        from channels_consumers.translation_consumer import _is_silent
        loud = make_pcm(0.04, amplitude=5000)
        assert _is_silent(loud) is False

    def test_empty_bytes_is_silent(self):
        from channels_consumers.translation_consumer import _is_silent
        assert _is_silent(b"") is True

    def test_low_amplitude_is_silent(self):
        from channels_consumers.translation_consumer import _is_silent
        quiet = make_pcm(0.04, amplitude=50)   # below SILENCE_THRESHOLD=200
        assert _is_silent(quiet) is True


# ─── PCM to WAV conversion ────────────────────────────────────────────────────

class TestPcmToWav:

    def test_produces_valid_wav(self):
        from channels_consumers.translation_consumer import _pcm_to_wav
        pcm      = make_pcm(0.5)
        wav      = _pcm_to_wav(pcm)
        buf      = io.BytesIO(wav)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000

    def test_wav_contains_correct_audio_length(self):
        from channels_consumers.translation_consumer import _pcm_to_wav
        pcm        = make_pcm(1.0)   # 1 second
        wav        = _pcm_to_wav(pcm)
        buf        = io.BytesIO(wav)
        with wave.open(buf, "rb") as wf:
            duration = wf.getnframes() / wf.getframerate()
            assert abs(duration - 1.0) < 0.01


# ─── Pipeline Step Functions ──────────────────────────────────────────────────

class TestPipelineSteps:

    @patch("services.whisper_service.transcribe")
    def test_whisper_transcribe_returns_text(self, mock_transcribe):
        mock_transcribe.return_value = {"text": "Hello world", "language": "en", "duration": 1.0, "segments": []}
        from channels_consumers.translation_consumer import _whisper_transcribe
        result = _whisper_transcribe(make_wav(make_pcm(1.0)), "en")
        assert result == "Hello world"
        mock_transcribe.assert_called_once()

    @patch("services.whisper_service.transcribe")
    def test_whisper_returns_none_on_failure(self, mock_transcribe):
        mock_transcribe.return_value = None
        from channels_consumers.translation_consumer import _whisper_transcribe
        result = _whisper_transcribe(make_wav(make_pcm(1.0)), "en")
        assert result is None

    @patch("services.translation.translate")
    def test_translate_text_success(self, mock_translate):
        mock_translate.return_value = "مرحبا بالعالم"
        from channels_consumers.translation_consumer import _translate_text
        result = _translate_text("Hello world", "en", "ar")
        assert result == "مرحبا بالعالم"
        mock_translate.assert_called_once_with("Hello world", target_language="ar", source_language="en")

    @patch("services.translation.translate")
    def test_translate_returns_none_on_exception(self, mock_translate):
        mock_translate.side_effect = Exception("DeepL API error")
        from channels_consumers.translation_consumer import _translate_text
        result = _translate_text("Hello", "en", "ar")
        assert result is None

    @patch("services.xtts_client.synthesize_speech")
    def test_synthesize_returns_wav_bytes(self, mock_synth):
        mock_synth.return_value = make_wav(make_pcm(0.5))
        from channels_consumers.translation_consumer import _synthesize
        result = _synthesize("مرحبا", [0.1] * 256, "ar")
        assert isinstance(result, bytes)
        assert len(result) > 0
        mock_synth.assert_called_once_with(text="مرحبا", embedding=[0.1] * 256, language="ar")

    @patch("services.xtts_client.synthesize_speech")
    def test_synthesize_returns_none_on_failure(self, mock_synth):
        mock_synth.return_value = None
        from channels_consumers.translation_consumer import _synthesize
        result = _synthesize("test", [0.1] * 256, "en")
        assert result is None


# ─── XTTS Client ─────────────────────────────────────────────────────────────

class TestXttsClient:

    @patch("httpx.post")
    def test_compute_embedding_success(self, mock_post, tmp_path):
        mock_response           = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.1] * 256}
        mock_post.return_value  = mock_response

        # Create a temp WAV file
        wav_path = tmp_path / "sample.wav"
        wav_path.write_bytes(make_wav(make_pcm(4.0)))

        from services.xtts_client import compute_speaker_embedding
        result = compute_speaker_embedding([str(wav_path)])
        assert result is not None
        assert len(result) == 256

    @patch("httpx.post")
    def test_compute_embedding_returns_none_on_http_error(self, mock_post, tmp_path):
        mock_response             = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("500 error")
        mock_post.return_value    = mock_response

        wav_path = tmp_path / "sample.wav"
        wav_path.write_bytes(make_wav(make_pcm(4.0)))

        from services.xtts_client import compute_speaker_embedding
        result = compute_speaker_embedding([str(wav_path)])
        assert result is None

    def test_compute_embedding_empty_paths(self):
        from services.xtts_client import compute_speaker_embedding
        result = compute_speaker_embedding([])
        assert result is None

    @patch("httpx.post")
    def test_synthesize_speech_success(self, mock_post):
        mock_response           = MagicMock()
        mock_response.status_code = 200
        mock_response.content   = make_wav(make_pcm(0.5))
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value  = mock_response

        from services.xtts_client import synthesize_speech
        result = synthesize_speech("Hello", [0.1] * 256, "en")
        assert isinstance(result, bytes)

    @patch("httpx.get")
    def test_health_check_ok(self, mock_get):
        mock_get.return_value.status_code = 200
        from services.xtts_client import is_xtts_service_healthy
        assert is_xtts_service_healthy() is True

    @patch("httpx.get")
    def test_health_check_fail(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        from services.xtts_client import is_xtts_service_healthy
        assert is_xtts_service_healthy() is False


# ─── Whisper Client ───────────────────────────────────────────────────────────

class TestWhisperClient:

    @patch("httpx.post")
    def test_transcribe_success(self, mock_post):
        mock_response             = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "Hello world", "language": "en",
            "duration": 1.0, "segments": [],
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value    = mock_response

        from services.whisper_service import transcribe
        result = transcribe(make_wav(make_pcm(1.0)), language="en")
        assert result is not None
        assert result["text"] == "Hello world"
        assert result["language"] == "en"

    @patch("httpx.post")
    def test_transcribe_returns_none_on_timeout(self, mock_post):
        import httpx
        mock_post.side_effect = httpx.TimeoutException("timeout")
        from services.whisper_service import transcribe
        result = transcribe(make_wav(make_pcm(1.0)))
        assert result is None

    @patch("httpx.get")
    def test_health_check(self, mock_get):
        mock_get.return_value.status_code = 200
        from services.whisper_service import is_whisper_service_healthy
        assert is_whisper_service_healthy() is True


# ─── Translation Service ──────────────────────────────────────────────────────

class TestTranslationService:

    @patch("deepl.Translator")
    def test_deepl_translate_success(self, mock_translator_class):
        mock_result      = MagicMock()
        mock_result.text = "Bonjour le monde"
        mock_translator  = MagicMock()
        mock_translator.translate_text.return_value = mock_result
        mock_translator_class.return_value          = mock_translator

        from services.translation import _try_deepl
        with patch("django.conf.settings") as mock_settings:
            mock_settings.DEEPL_API_KEY  = "test-key"
            result = _try_deepl("Hello world", "fr", "en")
        # Result depends on deepl mock setup — just check it calls through
        # (actual assertion on mock_translator.translate_text)
        mock_translator.translate_text.assert_called()

    def test_cache_key_consistent(self):
        from services.translation import _cache_key
        key1 = _cache_key("Hello world", "ar")
        key2 = _cache_key("Hello world", "ar")
        assert key1 == key2

    def test_cache_key_different_for_different_inputs(self):
        from services.translation import _cache_key
        key1 = _cache_key("Hello", "ar")
        key2 = _cache_key("Hello", "fr")
        assert key1 != key2

    @patch("django.core.cache.cache.get")
    @patch("django.core.cache.cache.set")
    @patch("services.translation._try_deepl")
    def test_translate_uses_cache(self, mock_deepl, mock_cache_set, mock_cache_get):
        mock_cache_get.return_value = "cached translation"
        from services.translation import translate
        result = translate("Hello", "ar", "en")
        assert result == "cached translation"
        mock_deepl.assert_not_called()   # DeepL not called — cache hit

    @patch("django.core.cache.cache.get")
    @patch("django.core.cache.cache.set")
    @patch("services.translation._try_deepl")
    @patch("services.translation._try_helsinki")
    def test_translate_falls_back_to_helsinki(self, mock_helsinki, mock_deepl, mock_set, mock_get):
        mock_get.return_value    = None           # cache miss
        mock_deepl.return_value  = None           # DeepL fails
        mock_helsinki.return_value = "Translated via Helsinki"
        from services.translation import translate
        result = translate("Hello", "hi", "en")   # Hindi — not in DeepL
        assert result == "Translated via Helsinki"

    @patch("django.core.cache.cache.get")
    @patch("services.translation._try_deepl")
    @patch("services.translation._try_helsinki")
    def test_translate_returns_original_on_total_failure(self, mock_helsinki, mock_deepl, mock_get):
        mock_get.return_value    = None
        mock_deepl.return_value  = None
        mock_helsinki.return_value = None
        from services.translation import translate
        result = translate("Hello", "xx", "en")
        assert result == "Hello"   # original returned on failure

    def test_same_language_returns_original(self):
        from services.translation import translate
        result = translate("Hello", "en", "en")
        assert result == "Hello"


# ─── Audio Processing ─────────────────────────────────────────────────────────

class TestAudioProcessing:

    def test_validate_valid_wav(self):
        from services.audio_processing import validate_and_process_wav
        pcm    = make_pcm(4.0, amplitude=5000)
        wav    = make_wav(pcm)
        result = validate_and_process_wav(wav, "audio.wav")
        assert result["ok"] is True
        assert result["duration"] > 0
        assert result["processed_bytes"] is not None

    def test_reject_too_short(self):
        from services.audio_processing import validate_and_process_wav
        pcm    = make_pcm(1.0)    # only 1 second — below 3s minimum
        wav    = make_wav(pcm)
        result = validate_and_process_wav(wav, "short.wav")
        assert result["ok"] is False
        assert "short" in result["error"].lower()

    def test_reject_too_long(self):
        from services.audio_processing import validate_and_process_wav
        pcm    = make_pcm(35.0)   # 35 seconds — above 30s maximum
        wav    = make_wav(pcm)
        result = validate_and_process_wav(wav, "long.wav")
        assert result["ok"] is False
        assert "long" in result["error"].lower()

    def test_noise_floor_measured(self):
        from services.audio_processing import validate_and_process_wav
        pcm    = make_pcm(4.0, amplitude=5000)
        wav    = make_wav(pcm)
        result = validate_and_process_wav(wav, "audio.wav")
        assert result["ok"] is True
        assert isinstance(result["noise_floor_db"], float)
        assert result["noise_floor_db"] < 0   # negative dBFS

    def test_peak_normalize(self):
        from services.audio_processing import _peak_normalize, _rms_dbfs
        pcm       = make_pcm(1.0, amplitude=1000)   # quiet
        normalized = _peak_normalize(pcm)
        samples_orig = [struct.unpack_from("<h", pcm, i)[0] for i in range(0, len(pcm) - 1, 2)]
        samples_norm = [struct.unpack_from("<h", normalized, i)[0] for i in range(0, len(normalized) - 1, 2)]
        # Normalized peak should be louder
        assert max(abs(s) for s in samples_norm) > max(abs(s) for s in samples_orig)
