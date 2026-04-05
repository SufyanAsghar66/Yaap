package com.yaap.app.utils

import com.yaap.app.BuildConfig

object Constants {
    // API
    const val BASE_URL = BuildConfig.BASE_URL
    const val WS_BASE_URL = BuildConfig.WS_BASE_URL
    const val API_V1 = "/api/v1"

    // Prefs keys
    const val PREF_ACCESS_TOKEN = "access_token"
    const val PREF_REFRESH_TOKEN = "refresh_token"
    const val PREF_USER_ID = "user_id"
    const val PREF_DISPLAY_NAME = "display_name"
    const val PREF_LANGUAGE_PREF = "language_preference"
    const val PREF_VOICE_TRAINED = "voice_trained"
    const val PREF_PROFILE_COMPLETE = "profile_complete"

    // Intent extras
    const val EXTRA_CONVERSATION_ID = "conversation_id"
    const val EXTRA_ROOM_ID = "room_id"
    const val EXTRA_CALLER_NAME = "caller_name"
    const val EXTRA_CALLER_AVATAR = "caller_avatar"
    const val EXTRA_IS_INCOMING = "is_incoming"
    const val EXTRA_FRIEND_ID = "friend_id"
    const val EXTRA_FRIENDSHIP_TAB = "friendship_tab"

    // Notification channels
    const val CHANNEL_MESSAGES = "yaap_messages"
    const val CHANNEL_CALLS = "yaap_calls"
    const val CHANNEL_SOCIAL = "yaap_social"
    const val CHANNEL_SYSTEM = "yaap_system"

    // Audio
    const val AUDIO_SAMPLE_RATE = 16000
    const val AUDIO_FRAME_SIZE = 1280 // 40ms at 16kHz

    // WebSocket reconnect
    val WS_BACKOFF_DELAYS = listOf(1000L, 2000L, 4000L, 8000L, 30000L)
    const val WS_PING_INTERVAL_MS = 30_000L

    // JWT next_step values
    const val STEP_PERSONAL_DETAILS = "personal_details"
    const val STEP_LANGUAGE_SELECTION = "language_selection"
    const val STEP_VOICE_TRAINING = "voice_training"
    const val STEP_MAIN_CHAT = "main_chat"

    // FCM notification types
    const val NOTIF_MESSAGE = "message"
    const val NOTIF_CALL = "call"
    const val NOTIF_FRIEND_REQUEST = "friend_request"
    const val NOTIF_VOICE_TRAINED = "voice_trained"
    const val NOTIF_MISSED_CALL = "missed_call"

    // Call timeout
    const val CALL_TIMEOUT_MS = 30_000L

    // Validation
    const val MIN_PASSWORD_LENGTH = 8
    const val BIO_MAX_CHARS = 160
    const val MIN_AGE_YEARS = 13
    const val SEARCH_DEBOUNCE_MS = 300L
    const val TYPING_STOP_DELAY_MS = 2000L
    const val WAVEFORM_POLL_INTERVAL_MS = 50L
    const val MAX_RECORDING_SECONDS = 30
}
