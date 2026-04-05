package com.yaap.app.model

import com.google.gson.annotations.SerializedName

// ---- Auth ----

data class LoginRequest(val email: String, val password: String)

data class SignupRequest(
    val email: String,
    val password: String,
    @SerializedName("full_name") val fullName: String
)

data class OtpRequestBody(val email: String)
data class OtpVerifyRequest(val email: String, val otp: String)
data class GoogleAuthRequest(@SerializedName("id_token") val idToken: String)
data class RefreshTokenRequest(@SerializedName("refresh_token") val refreshToken: String)
data class PasswordStrengthRequest(val password: String)
data class PasswordStrengthResponse(val score: Int, val label: String) // score 1-4

data class AuthResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("next_step") val nextStep: String,
    @SerializedName("is_new") val isNew: Boolean = false
)

// ---- User / Profile ----

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
    @SerializedName("next_step") val nextStep: String?
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
    @SerializedName("friendship_status") val friendshipStatus: String // none, requested, friends
)

// ---- Conversations & Messages ----

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
    val status: String, // pending, sent, delivered, read
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

// ---- Generic ----

data class ApiError(val message: String, val detail: String?)
data class MessageResponse(val message: String)
