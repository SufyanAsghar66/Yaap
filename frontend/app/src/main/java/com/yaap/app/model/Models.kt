package com.yaap.app.model

import com.google.gson.annotations.SerializedName

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Generic API Envelope — wraps every backend response
//  Backend shape: {"success": true/false, "data": {...}} or
//                 {"success": false, "error": {"code": "...", "message": "..."}}
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class ApiEnvelope<T>(
    val success: Boolean,
    val data: T?,
    val error: ApiErrorDetail? = null
)

data class ApiErrorDetail(
    val code: String?,
    val message: String?
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Auth — Request Models
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class LoginRequest(val email: String, val password: String)

data class SignupRequest(
    val email: String,
    val password: String,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("password_confirm") val passwordConfirm: String
)

data class OtpRequestBody(val email: String)
data class OtpVerifyRequest(val email: String, val otp: String)
data class GoogleAuthRequest(@SerializedName("id_token") val idToken: String)
data class RefreshTokenRequest(val refresh: String)  // Backend expects "refresh", not "refresh_token"
data class PasswordStrengthRequest(val password: String)
data class PasswordStrengthResponse(val score: Int, val label: String)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Auth — Response Models (match backend's nested structure)
//
//  Backend login/signup returns:
//  {"success": true, "data": {
//      "user": {...},
//      "tokens": {"access": "...", "refresh": "..."},
//      "next_step": "personal_details"
//  }}
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class TokenPair(
    val access: String,
    val refresh: String
)

data class AuthDataResponse(
    val user: User?,
    val tokens: TokenPair,
    @SerializedName("next_step") val nextStep: String,
    @SerializedName("is_new") val isNew: Boolean = false,
    @SerializedName("password_strength") val passwordStrength: Map<String, Any>? = null
)

/** Convenience — old code referenced this flat shape. Now it's built from AuthDataResponse. */
data class AuthResponse(
    val accessToken: String,
    val refreshToken: String,
    val nextStep: String,
    val isNew: Boolean = false
) {
    companion object {
        fun from(data: AuthDataResponse): AuthResponse = AuthResponse(
            accessToken = data.tokens.access,
            refreshToken = data.tokens.refresh,
            nextStep = data.nextStep,
            isNew = data.isNew
        )
    }
}

/**
 *  Token refresh response shape:
 *  {"success": true, "data": {"tokens": {"access": "...", "refresh": "..."}}}
 */
data class TokenRefreshDataResponse(
    val tokens: TokenPair
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  User / Profile
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class User(
    val id: String,
    val email: String,
    @SerializedName("display_name") val displayName: String,
    @SerializedName("avatar_url") val avatarUrl: String?,
    @SerializedName("country_code") val countryCode: String?,
    val timezone: String?,
    val bio: String?,
    @SerializedName("is_online") val isOnline: Boolean = false,
    @SerializedName("language_preference") val languagePreference: String?,
    @SerializedName("voice_trained") val voiceTrained: Boolean = false,
    @SerializedName("date_of_birth") val dateOfBirth: String?,
    @SerializedName("next_step") val nextStep: String?,
    @SerializedName("full_name") val fullName: String? = null,
    @SerializedName("profile_complete") val profileComplete: Boolean = false,
    @SerializedName("language_selected") val languageSelected: Boolean = false
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
    @SerializedName("native_name") val nativeName: String? = null,
    @SerializedName("flag_emoji") val flagEmoji: String? = null
)

// Backend response wrappers for user endpoints
data class LanguagesDataResponse(
    val languages: List<Language>
)

data class UserSearchDataResponse(
    val results: List<UserSearchResult>,
    val count: Int
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Voice Training
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class VoiceSentence(
    val id: String,
    val text: String,
    val index: Int
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

// Backend response wrappers for voice endpoints
data class VoiceSentencesDataResponse(
    val language: String,
    @SerializedName("language_name") val languageName: String,
    val sentences: List<VoiceSentence>,
    @SerializedName("total_required") val totalRequired: Int
)

data class VoiceSampleDataResponse(
    val sample: Map<String, Any>,
    @SerializedName("samples_uploaded") val samplesUploaded: Int,
    @SerializedName("samples_required") val samplesRequired: Int,
    @SerializedName("all_uploaded") val allUploaded: Boolean,
    @SerializedName("noise_warning") val noiseWarning: Boolean,
    @SerializedName("noise_floor_db") val noiseFloorDb: Double
)

data class VoiceStatusDataResponse(
    @SerializedName("voice_trained") val voiceTrained: Boolean,
    @SerializedName("samples_uploaded") val samplesUploaded: Int,
    @SerializedName("samples_required") val samplesRequired: Int,
    @SerializedName("all_samples_uploaded") val allSamplesUploaded: Boolean,
    @SerializedName("active_job") val activeJob: Map<String, Any>?,
    val samples: List<Map<String, Any>>
)

data class VoiceTrainDataResponse(
    val job: Map<String, Any>,
    val message: String
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Friendship
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
    @SerializedName("created_at") val createdAt: String
)

data class BlockRequest(@SerializedName("user_id") val userId: String)

data class UserSearchResult(
    val id: String,
    @SerializedName("display_name") val displayName: String,
    @SerializedName("avatar_url") val avatarUrl: String?,
    @SerializedName("country_code") val countryCode: String?,
    val timezone: String?,
    @SerializedName("mutual_friends") val mutualFriends: Int = 0,
    @SerializedName("friendship_status") val friendshipStatus: String
)

// Backend response wrappers for friendship endpoints
data class FriendsDataResponse(
    val friends: List<Friendship>,
    val count: Int
)

data class FriendRequestsDataResponse(
    val requests: List<FriendRequest>,
    val count: Int
)

data class FriendRequestSendDataResponse(
    val request: FriendRequest
)

data class AcceptRequestDataResponse(
    val message: String,
    @SerializedName("friendship_id") val friendshipId: String
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Conversations & Messages
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class Conversation(
    val id: String,
    @SerializedName("other_user") val otherUser: User,
    @SerializedName("last_message") val lastMessage: Message?,
    @SerializedName("unread_count") val unreadCount: Int = 0,
    @SerializedName("updated_at") val updatedAt: String
)

data class Message(
    val id: String,
    @SerializedName("conversation_id") val conversationId: String,
    @SerializedName("sender_id") val senderId: String,
    val content: String,
    val translation: String?,
    val status: String,
    @SerializedName("created_at") val createdAt: String,
    val deleted: Boolean = false
)

data class StartConversationRequest(@SerializedName("user_id") val userId: String)
data class StartConversationResponse(val id: String)

data class TranslateMessageRequest(val language: String)
data class TranslateMessageResponse(val translation: String, val language: String)

data class MessagesPage(
    val messages: List<Message>,
    @SerializedName("next_cursor") val nextCursor: String?,
    @SerializedName("has_more") val hasMore: Boolean
)

// Backend response wrappers for messaging endpoints
data class ConversationsDataResponse(
    val conversations: List<Conversation>
)

data class ConversationDataResponse(
    val conversation: Conversation
)

data class TranslateMessageDataResponse(
    @SerializedName("message_id") val messageId: String,
    val language: String,
    @SerializedName("translated_content") val translatedContent: String,
    val cached: Boolean
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Calls
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class InitiateCallRequest(
    @SerializedName("callee_id") val calleeId: String,
    val language: String? = null
)

data class InitiateCallResponse(
    @SerializedName("room_id") val roomId: String,
    @SerializedName("caller_id") val callerId: String,
    @SerializedName("callee_id") val calleeId: String
)

data class IceConfigResponse(
    @SerializedName("ice_servers") val iceServers: List<IceServer>
)

data class IceServer(
    val urls: List<String>,
    val username: String?,
    val credential: String?
)

// Backend response wrappers for call endpoints
data class InitiateCallDataResponse(
    val room: Map<String, Any>,
    val ice: Map<String, Any>,
    @SerializedName("ws_url") val wsUrl: String
)

data class IceConfigDataResponse(
    @SerializedName("ice_servers") val iceServers: List<IceServer>,
    val username: String,
    val credential: String,
    @SerializedName("expires_at") val expiresAt: String,
    @SerializedName("room_id") val roomId: String
)

data class CallHistoryDataResponse(
    val calls: List<Map<String, Any>>,
    val total: Int,
    val page: Int,
    @SerializedName("page_size") val pageSize: Int,
    @SerializedName("has_more") val hasMore: Boolean
)

data class ActiveCallDataResponse(
    @SerializedName("active_call") val activeCall: Map<String, Any>?
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  FCM Device
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class RegisterDeviceRequest(
    @SerializedName("fcm_token") val fcmToken: String,
    @SerializedName("device_name") val deviceName: String
)

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  Generic
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

data class ApiError(val message: String, val detail: String?)
data class MessageResponse(val message: String)
