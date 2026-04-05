package com.yaap.app.model

import com.google.gson.annotations.SerializedName

// ---- Auth ----

data class LoginRequest(val email: String, val password: String)

/** Matches Django [SignupSerializer]: email, password, password_confirm, full_name. */
data class SignupRequest(
    val email: String,
    val password: String,
    @SerializedName("password_confirm") val passwordConfirm: String,
    @SerializedName("full_name") val fullName: String
)

data class OtpRequestBody(val email: String)

/** Backend expects `code` (6-digit), not `otp`. */
data class OtpVerifyRequest(val email: String, val code: String)

data class GoogleAuthRequest(@SerializedName("id_token") val idToken: String)

/** simplejwt expects the field name `refresh`. */
data class RefreshTokenRequest(@SerializedName("refresh") val refresh: String)

data class PasswordStrengthRequest(val password: String)

/** UI model: [score] is 1–4 for the strength bars; [label] is the backend level string. */
data class PasswordStrengthResponse(val score: Int, val label: String)

data class PasswordStrengthWire(@SerializedName("strength") val strength: PasswordStrengthDetail)

data class PasswordStrengthDetail(
    val score: Int,
    val level: String,
    @SerializedName("has_upper") val hasUpper: Boolean = false,
    @SerializedName("has_lower") val hasLower: Boolean = false,
    @SerializedName("has_digit") val hasDigit: Boolean = false,
    @SerializedName("has_symbol") val hasSymbol: Boolean = false,
    val length: Int = 0
)

data class TokenPair(
    val access: String,
    val refresh: String
)

/**
 * Inner auth payload after envelope unwrap (login, signup, OTP verify, Google).
 */
data class AuthWireModel(
    val user: User?,
    val tokens: TokenPair,
    @SerializedName("next_step") val nextStep: String,
    @SerializedName("is_new") val isNew: Boolean = false,
    @SerializedName("password_strength") val passwordStrength: PasswordStrengthDetail? = null
)

/** Token refresh inner payload: `{ "tokens": { "access", "refresh" } }`. */
data class RefreshWireModel(val tokens: TokenPair)

/**
 * Domain type used by [com.yaap.app.ui.auth.AuthViewModel] after mapping from [AuthWireModel].
 */
data class AuthResponse(
    val accessToken: String,
    val refreshToken: String,
    val nextStep: String,
    val isNew: Boolean = false
)

fun AuthWireModel.toAuthResponse() = AuthResponse(
    accessToken = tokens.access,
    refreshToken = tokens.refresh,
    nextStep = nextStep,
    isNew = isNew
)

fun PasswordStrengthWire.toPasswordStrengthResponse(): PasswordStrengthResponse {
    val uiScore = when (strength.level) {
        "weak" -> 1
        "fair" -> 2
        "strong" -> 3
        "very_strong" -> 4
        else -> 1
    }
    return PasswordStrengthResponse(uiScore, strength.level)
}

// ---- User / Profile ----

/** Defaults allow Gson to parse partial user blobs (e.g. chat [other_user]) from the API. */
data class User(
    val id: String,
    val email: String = "",
    @SerializedName("display_name") val displayName: String = "",
    @SerializedName("avatar_url") val avatarUrl: String? = null,
    @SerializedName("country_code") val countryCode: String? = null,
    val timezone: String? = null,
    val bio: String? = null,
    @SerializedName("is_online") val isOnline: Boolean = false,
    @SerializedName("language_preference") val languagePreference: String? = null,
    @SerializedName("voice_trained") val voiceTrained: Boolean = false,
    @SerializedName("date_of_birth") val dateOfBirth: String? = null,
    @SerializedName("next_step") val nextStep: String? = null,
    @SerializedName("full_name") val fullName: String? = null
)

data class UpdateProfileRequest(
    @SerializedName("display_name") val displayName: String? = null,
    val bio: String? = null,
    @SerializedName("country_code") val countryCode: String? = null,
    @SerializedName("date_of_birth") val dateOfBirth: String? = null,
    val timezone: String? = null
)

data class LanguageUpdateRequest(@SerializedName("language_preference") val language: String)

data class Language(
    val code: String,
    val name: String,
    @SerializedName("native_name") val nativeName: String,
    @SerializedName("flag_emoji") val flagEmoji: String
)

// ---- Voice Training ----

/** Backend fields: `sentence`, `position` (see VoiceSentenceSerializer). */
data class VoiceSentence(
    val id: String,
    @SerializedName("sentence") val text: String,
    @SerializedName("position") val index: Int,
    val language: String? = null
)

data class VoiceSampleResponse(
    val id: String,
    @SerializedName("noise_warning") val noiseWarning: Boolean = false
)

data class VoiceTrainResponse(val status: String)
data class VoiceStatusResponse(
    val status: String,
    @SerializedName("voice_trained") val voiceTrained: Boolean
)

// ---- Friendship ----

data class FriendRequest(
    val id: String,
    @SerializedName("from_user") val fromUser: User,
    @SerializedName("to_user") val toUser: User,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
    val message: String?
)

data class SendFriendRequest(
    @SerializedName("to_user_id") val toUserId: String,
    val message: String? = null
)

data class Friendship(
    val id: String,
    val friend: User,
    @SerializedName("friendship_since") val createdAt: String
)

data class BlockRequest(@SerializedName("user_id") val userId: String)

data class UserSearchResult(
    val id: String,
    @SerializedName("display_name") val displayName: String,
    @SerializedName("avatar_url") val avatarUrl: String?,
    @SerializedName("country_code") val countryCode: String?,
    val timezone: String?,
    @SerializedName("mutual_friends") val mutualFriends: Int = 0,
    @SerializedName("friendship_status") val friendshipStatus: String // none, requested, friends
)

// ---- Conversations & Messages ----

data class Conversation(
    val id: String,
    @SerializedName("other_user") val otherUser: User,
    @SerializedName("last_message") val lastMessage: Message?,
    @SerializedName("unread_count") val unreadCount: Int = 0,
    @SerializedName("updated_at") val updatedAt: String,
    @SerializedName("created_at") val createdAt: String? = null
)

data class Message(
    val id: String,
    @SerializedName("conversation_id") val conversationId: String = "",
    @SerializedName("sender_id") val senderId: String,
    val content: String,
    val translation: String?,
    val status: String, // pending, sent, delivered, read
    @SerializedName("created_at") val createdAt: String,
    val deleted: Boolean = false
)

data class StartConversationRequest(@SerializedName("user_id") val userId: String)

data class StartConversationResponse(val id: String)

/** After envelope unwrap, POST /conversations/start/ returns `{ "conversation": { ... } }`. */
data class StartConversationPayload(
    val conversation: Conversation
)

data class TranslateMessageRequest(val language: String)

data class TranslateMessageResponse(
    @SerializedName("translated_content") val translation: String,
    val language: String
)

data class MessagesPage(
    val messages: List<Message>,
    @SerializedName("next_cursor") val nextCursor: String?,
    @SerializedName("has_more") val hasMore: Boolean
)

// ---- Calls ----

data class InitiateCallRequest(
    @SerializedName("callee_id") val calleeId: String,
    val language: String? = null
)

data class InitiateCallResponse(
    @SerializedName("room_id") val roomId: String,
    @SerializedName("caller_id") val callerId: String,
    @SerializedName("callee_id") val calleeId: String
)

/** POST /calls/initiate/ inner payload after envelope unwrap. */
data class InitiateCallWire(
    val room: InitiateCallRoomWire,
    val ice: Map<String, Any>? = null,
    @SerializedName("ws_url") val wsUrl: String? = null
)

data class InitiateCallRoomWire(
    val id: String,
    @SerializedName("room_id") val roomId: String,
    val caller: User,
    val callee: User
)

data class IceConfigResponse(
    @SerializedName("ice_servers") val iceServers: List<IceServer>
)

data class IceServer(
    val urls: List<String>,
    val username: String?,
    val credential: String?
)

// ---- FCM Device ----

data class RegisterDeviceRequest(
    @SerializedName("fcm_token") val fcmToken: String,
    @SerializedName("device_name") val deviceName: String
)

// ---- API inner payloads (after [YaapEnvelopeInterceptor] unwrap) ----

data class LanguagesListPayload(@SerializedName("languages") val languages: List<Language>)

data class FriendsListPayload(
    val friends: List<Friendship>,
    val count: Int
)

data class ConversationsListPayload(
    @SerializedName("conversations") val conversations: List<Conversation>
)

data class SearchUsersPayload(
    val results: List<UserSearchResult>,
    val count: Int
)

data class OtpRequestData(
    val message: String,
    @SerializedName("expires_in") val expiresInSeconds: Int? = null
)

data class VoiceSentencesPayload(
    val language: String,
    @SerializedName("language_name") val languageName: String? = null,
    val sentences: List<VoiceSentence>,
    @SerializedName("total_required") val totalRequired: Int? = null
)

data class VoiceUploadPayload(
    val sample: VoiceSampleInner,
    @SerializedName("noise_warning") val noiseWarning: Boolean? = null
)

data class VoiceSampleInner(val id: String)

data class VoiceTrainWire(
    val job: VoiceTrainingJobWire? = null,
    val message: String? = null
)

data class VoiceTrainingJobWire(val status: String? = null)

data class VoiceStatusWire(
    @SerializedName("voice_trained") val voiceTrained: Boolean,
    @SerializedName("samples_uploaded") val samplesUploaded: Int? = null,
    @SerializedName("active_job") val activeJob: VoiceTrainingJobWire? = null
)

data class ActiveCallPayload(@SerializedName("active_call") val activeCall: Map<String, Any>?)

data class CallHistoryPayload(
    val calls: List<Map<String, Any>>,
    val total: Int,
    val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("has_more") val hasMore: Boolean
)

data class AvatarUrlPayload(@SerializedName("avatar_url") val avatarUrl: String)

data class LanguageUpdatePayload(
    @SerializedName("language_preference") val languagePreference: String,
    @SerializedName("language_name") val languageName: String? = null
)

// ---- Generic ----

data class ApiError(val message: String, val detail: String?)

data class MessageResponse(
    val message: String,
    @SerializedName("expires_in") val expiresInSeconds: Int? = null,
    @SerializedName("duration_seconds") val durationSeconds: Int? = null,
    @SerializedName("friendship_id") val friendshipId: String? = null,
    @SerializedName("device_id") val deviceId: String? = null,
    @SerializedName("block_id") val blockId: String? = null
)

data class FriendRequestsPayload(
    val requests: List<FriendRequest>,
    val count: Int
)

data class BlockedUsersPayload(
    val blocked: List<User>,
    val count: Int
)

data class SendFriendRequestPayload(val request: FriendRequest)

fun VoiceUploadPayload.toVoiceSampleResponse(): VoiceSampleResponse =
    VoiceSampleResponse(id = sample.id, noiseWarning = noiseWarning == true)

fun VoiceTrainWire.toVoiceTrainResponse(): VoiceTrainResponse =
    VoiceTrainResponse(status = job?.status ?: message ?: "pending")

fun VoiceStatusWire.toVoiceStatusResponse(): VoiceStatusResponse =
    VoiceStatusResponse(
        status = when {
            voiceTrained -> "complete"
            activeJob != null -> activeJob.status ?: "processing"
            else -> "ready"
        },
        voiceTrained = voiceTrained
    )

fun InitiateCallWire.toInitiateCallResponse(): InitiateCallResponse =
    InitiateCallResponse(
        roomId = room.roomId,
        callerId = room.caller.id,
        calleeId = room.callee.id
    )
