"""
Translation Service
Primary:  DeepL API (highest quality)
Fallback: Helsinki-NLP Opus-MT (free, offline)
Caching:  Django cache keyed by SHA256(original_text + target_lang)
          Avoids re-translating identical text.
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# DeepL language code mapping (XTTS code → DeepL code)
DEEPL_LANG_MAP = {
    "en": "EN-US", "es": "ES", "fr": "FR", "de": "DE",
    "it": "IT",    "pt": "PT-PT", "pl": "PL", "tr": "TR",
    "ru": "RU",    "nl": "NL",   "cs": "CS", "ar": "AR",
    "zh": "ZH",    "ja": "JA",   "ko": "KO", "hu": "HU",
    "hi": None,    # DeepL doesn't support Hindi — falls back to Helsinki
}

CACHE_TIMEOUT = 60 * 60 * 24 * 7   # 7 days — translations don't expire


def translate(text: str, target_language: str, source_language: str = None) -> str:
    """
    Translate `text` into `target_language`.
    Returns original text if both languages are the same or on complete failure.
    All results are cached to avoid redundant API calls.

    Args:
        text:            Text to translate
        target_language: XTTS language code (e.g. 'ar', 'de', 'zh')
        source_language: Optional hint; if None, auto-detected

    Returns:
        Translated string
    """
    if not text or not text.strip():
        return text

    if source_language and source_language == target_language:
        return text

    cache_key = _cache_key(text, target_language)
    cached    = cache.get(cache_key)
    if cached:
        logger.debug("Translation cache hit: lang=%s", target_language)
        return cached

    translated = _try_deepl(text, target_language, source_language)
    if translated is None:
        translated = _try_helsinki(text, target_language, source_language)
    if translated is None:
        logger.error("All translation providers failed for lang=%s", target_language)
        return text

    cache.set(cache_key, translated, timeout=CACHE_TIMEOUT)
    return translated


def _cache_key(text: str, target_language: str) -> str:
    digest = hashlib.sha256(f"{text}::{target_language}".encode()).hexdigest()
    return f"yaap:translation:{digest}"


# ─── DeepL ────────────────────────────────────────────────────────────────────

def _try_deepl(text: str, target_language: str, source_language: str = None) -> str | None:
    api_key   = settings.DEEPL_API_KEY
    deepl_target = DEEPL_LANG_MAP.get(target_language)

    if not api_key or not deepl_target:
        return None

    try:
        import deepl
        translator = deepl.Translator(api_key)
        result     = translator.translate_text(
            text,
            target_lang  = deepl_target,
            source_lang  = DEEPL_LANG_MAP.get(source_language) if source_language else None,
        )
        logger.info("DeepL translation: %s → %s (%d chars)", source_language, target_language, len(text))
        return result.text
    except Exception as e:
        logger.warning("DeepL translation failed: %s", e)
        return None


# ─── Helsinki-NLP Opus-MT (fallback) ──────────────────────────────────────────

_helsinki_pipelines: dict = {}   # cache loaded pipelines in memory


def _try_helsinki(text: str, target_language: str, source_language: str = None) -> str | None:
    """
    Uses the 'opus-mt' MarianMT models from Helsinki-NLP via HuggingFace transformers.
    Models are downloaded on first use (cached to ~/.cache/huggingface/).
    """
    try:
        from transformers import pipeline

        src  = source_language or "en"
        key  = f"{src}-{target_language}"
        model_name = f"Helsinki-NLP/opus-mt-{src}-{target_language}"

        if key not in _helsinki_pipelines:
            logger.info("Loading Helsinki-NLP model: %s", model_name)
            _helsinki_pipelines[key] = pipeline("translation", model=model_name)

        pipe   = _helsinki_pipelines[key]
        result = pipe(text, max_length=512)
        logger.info("Helsinki-NLP translation: %s → %s", src, target_language)
        return result[0]["translation_text"]

    except Exception as e:
        logger.warning("Helsinki-NLP translation failed for %s→%s: %s", source_language, target_language, e)
        return None


# ─── Async Celery task wrapper ────────────────────────────────────────────────

from celery import shared_task


@shared_task(name="translation.translate_message", queue="translation")
def translate_message_task(message_id: str, target_language: str):
    """
    Celery task: translate a message and store result in MessageTranslation.
    Called automatically when a message is received by a user with a different
    language preference.

    After saving, pushes the translation to the conversation's WebSocket group
    so the receiver sees it in real-time.
    """
    from apps.messaging.models import Message, MessageTranslation

    try:
        message = Message.objects.get(id=message_id)
        if message.deleted_for_everyone:
            return

        # Skip if translation already exists
        if MessageTranslation.objects.filter(message=message, language=target_language).exists():
            return

        translated = translate(
            text             = message.content,
            target_language  = target_language,
            source_language  = message.original_language,
        )

        MessageTranslation.objects.create(
            message            = message,
            language           = target_language,
            translated_content = translated,
        )
        logger.info("Message %s translated to %s", message_id, target_language)

        # Push translated content to the conversation WebSocket group in real-time
        _push_translation_to_ws(message, target_language, translated)

    except Message.DoesNotExist:
        logger.warning("translate_message_task: message %s not found", message_id)
    except Exception as e:
        logger.error("translate_message_task failed: %s", e)
        raise


def _push_translation_to_ws(message, target_language: str, translated_content: str):
    """
    Send translated message content to the conversation's WebSocket channel group.
    The ChatConsumer's `chat_message_translated` handler will only deliver it
    to the user whose language_preference matches.
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning("No channel layer configured; cannot push translation via WS.")
            return

        group_name = f"chat_{message.conversation_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "chat.message_translated",
                "payload": {
                    "message_id": str(message.id),
                    "language": target_language,
                    "translated_content": translated_content,
                },
            },
        )
        logger.info("Pushed translation for message %s to WS group %s", message.id, group_name)
    except Exception as e:
        # Non-fatal: the translation is saved in DB regardless
        logger.warning("Failed to push translation via WS: %s", e)

