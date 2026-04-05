package com.yaap.app.data.api

import com.yaap.app.model.*
import okhttp3.MultipartBody
import retrofit2.Response
import retrofit2.http.*

interface YaapApiService {

    // ---- Auth ----

    @POST("/api/v1/auth/login/")
    suspend fun login(@Body request: LoginRequest): Response<AuthResponse>

    @POST("/api/v1/auth/signup/")
    suspend fun signup(@Body request: SignupRequest): Response<AuthResponse>

    @POST("/api/v1/auth/otp/request/")
    suspend fun requestOtp(@Body request: OtpRequestBody): Response<MessageResponse>

    @POST("/api/v1/auth/otp/verify/")
    suspend fun verifyOtp(@Body request: OtpVerifyRequest): Response<AuthResponse>

    @POST("/api/v1/auth/google/")
    suspend fun googleAuth(@Body request: GoogleAuthRequest): Response<AuthResponse>

    @POST("/api/v1/auth/token/refresh/")
    suspend fun refreshToken(@Body request: RefreshTokenRequest): Response<AuthResponse>

    @POST("/api/v1/auth/logout/")
    suspend fun logout(): Response<MessageResponse>

    @POST("/api/v1/auth/password/strength/")
    suspend fun checkPasswordStrength(@Body request: PasswordStrengthRequest): Response<PasswordStrengthResponse>

    @POST("/api/v1/auth/password/reset/")
    suspend fun resetPassword(@Body request: OtpRequestBody): Response<MessageResponse>

    // ---- User ----

    @GET("/api/v1/users/me/")
    suspend fun getMyProfile(): Response<User>

    @PATCH("/api/v1/users/me/")
    suspend fun updateProfile(@Body request: UpdateProfileRequest): Response<User>

    @Multipart
    @POST("/api/v1/users/me/avatar/")
    suspend fun uploadAvatar(@Part avatar: MultipartBody.Part): Response<User>

    @PATCH("/api/v1/users/me/language/")
    suspend fun updateLanguage(@Body request: LanguageUpdateRequest): Response<User>

    @GET("/api/v1/users/languages/")
    suspend fun getLanguages(): Response<List<Language>>

    @GET("/api/v1/users/search/")
    suspend fun searchUsers(@Query("q") query: String): Response<List<UserSearchResult>>

    @GET("/api/v1/users/{id}/")
    suspend fun getUserProfile(@Path("id") userId: String): Response<User>

    // ---- Voice ----

    @GET("/api/v1/voice/sentences/")
    suspend fun getVoiceSentences(): Response<List<VoiceSentence>>

    @Multipart
    @POST("/api/v1/voice/samples/")
    suspend fun uploadVoiceSample(
        @Part audio: MultipartBody.Part,
        @Part("sample_index") sampleIndex: Int,
        @Part("sentence_id") sentenceId: String
    ): Response<VoiceSampleResponse>

    @DELETE("/api/v1/voice/samples/{index}/")
    suspend fun deleteVoiceSample(@Path("index") index: Int): Response<MessageResponse>

    @POST("/api/v1/voice/train/")
    suspend fun trainVoice(): Response<VoiceTrainResponse>

    @GET("/api/v1/voice/status/")
    suspend fun getVoiceStatus(): Response<VoiceStatusResponse>

    @POST("/api/v1/voice/reset/")
    suspend fun resetVoice(): Response<MessageResponse>

    // ---- Friends ----

    @POST("/api/v1/friends/devices/")
    suspend fun registerDevice(@Body request: RegisterDeviceRequest): Response<MessageResponse>

    @GET("/api/v1/friends/")
    suspend fun getFriends(): Response<List<Friendship>>

    @DELETE("/api/v1/friends/{friendshipId}/")
    suspend fun unfriend(@Path("friendshipId") friendshipId: String): Response<MessageResponse>

    @POST("/api/v1/friends/request/")
    suspend fun sendFriendRequest(@Body request: SendFriendRequest): Response<FriendRequest>

    @GET("/api/v1/friends/requests/received/")
    suspend fun getReceivedRequests(): Response<List<FriendRequest>>

    @GET("/api/v1/friends/requests/sent/")
    suspend fun getSentRequests(): Response<List<FriendRequest>>

    @POST("/api/v1/friends/requests/{id}/accept/")
    suspend fun acceptFriendRequest(@Path("id") requestId: String): Response<Friendship>

    @POST("/api/v1/friends/requests/{id}/decline/")
    suspend fun declineFriendRequest(@Path("id") requestId: String): Response<MessageResponse>

    @DELETE("/api/v1/friends/requests/{id}/")
    suspend fun cancelFriendRequest(@Path("id") requestId: String): Response<MessageResponse>

    @POST("/api/v1/friends/block/")
    suspend fun blockUser(@Body request: BlockRequest): Response<MessageResponse>

    @DELETE("/api/v1/friends/block/{userId}/")
    suspend fun unblockUser(@Path("userId") userId: String): Response<MessageResponse>

    @GET("/api/v1/friends/blocked/")
    suspend fun getBlockedUsers(): Response<List<User>>

    // ---- Conversations ----

    @GET("/api/v1/conversations/")
    suspend fun getConversations(): Response<List<Conversation>>

    @POST("/api/v1/conversations/start/")
    suspend fun startConversation(@Body request: StartConversationRequest): Response<StartConversationResponse>

    @GET("/api/v1/conversations/{id}/messages/")
    suspend fun getMessages(
        @Path("id") conversationId: String,
        @Query("cursor") cursor: String? = null,
        @Query("page_size") pageSize: Int = 50
    ): Response<MessagesPage>

    @POST("/api/v1/conversations/{id}/messages/")
    suspend fun sendMessageRest(
        @Path("id") conversationId: String,
        @Body body: Map<String, String>
    ): Response<Message>

    @POST("/api/v1/conversations/messages/{id}/translate/")
    suspend fun translateMessage(
        @Path("id") messageId: String,
        @Body request: TranslateMessageRequest
    ): Response<TranslateMessageResponse>

    @DELETE("/api/v1/conversations/messages/{id}/")
    suspend fun deleteMessage(@Path("id") messageId: String): Response<MessageResponse>

    // ---- Calls ----

    @POST("/api/v1/calls/initiate/")
    suspend fun initiateCall(@Body request: InitiateCallRequest): Response<InitiateCallResponse>

    @GET("/api/v1/calls/ice-config/{roomId}/")
    suspend fun getIceConfig(@Path("roomId") roomId: String): Response<IceConfigResponse>

    @POST("/api/v1/calls/{roomId}/end/")
    suspend fun endCall(@Path("roomId") roomId: String): Response<MessageResponse>

    @POST("/api/v1/calls/{roomId}/decline/")
    suspend fun declineCall(@Path("roomId") roomId: String): Response<MessageResponse>

    @GET("/api/v1/calls/history/")
    suspend fun getCallHistory(): Response<List<Map<String, Any>>>

    @GET("/api/v1/calls/active/")
    suspend fun getActiveCall(): Response<Map<String, Any>?>
}
