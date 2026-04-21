package com.yaap.app.data.repository

import com.yaap.app.data.api.YaapApiService
import com.yaap.app.data.local.dao.ConversationDao
import com.yaap.app.data.local.dao.MessageDao
import com.yaap.app.data.local.entity.ConversationEntity
import com.yaap.app.data.local.entity.MessageEntity
import com.yaap.app.model.*
import com.yaap.app.utils.Result
import kotlinx.coroutines.flow.Flow
import okhttp3.MultipartBody
import javax.inject.Inject
import javax.inject.Singleton

// ────────────────────────────────────────────────────────────────────
//  ChatRepository
// ────────────────────────────────────────────────────────────────────
@Singleton
class ChatRepository @Inject constructor(
    private val api: YaapApiService,
    private val conversationDao: ConversationDao,
    private val messageDao: MessageDao
) {
    fun observeConversations(): Flow<List<ConversationEntity>> = conversationDao.observeAll()

    suspend fun refreshConversations(): Result<List<Conversation>> {
        // Unwrap envelope → get ConversationsDataResponse → extract conversations list
        val result = safeApiCall { api.getConversations() }
        return when (result) {
            is Result.Success -> {
                val conversations = result.data.conversations
                val entities = conversations.map { c ->
                    ConversationEntity(
                        id = c.id,
                        otherUserId = c.otherUser.id,
                        otherUserName = c.otherUser.displayName,
                        otherUserAvatar = c.otherUser.avatarUrl,
                        otherUserCountryCode = c.otherUser.countryCode,
                        otherUserTimezone = c.otherUser.timezone,
                        otherUserOnline = c.otherUser.isOnline,
                        lastMessageContent = c.lastMessage?.content,
                        lastMessageTranslation = c.lastMessage?.translation,
                        lastMessageTimestamp = c.lastMessage?.createdAt,
                        unreadCount = c.unreadCount,
                        updatedAt = c.updatedAt
                    )
                }
                conversationDao.upsertAll(entities)
                Result.Success(conversations)
            }
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun startConversation(userId: String): Result<StartConversationResponse> {
        val result = safeApiCall {
            api.startConversation(StartConversationRequest(userId))
        }
        return when (result) {
            is Result.Success -> {
                val conv = result.data.conversation
                Result.Success(StartConversationResponse(id = conv.id))
            }
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun getMessages(conversationId: String, cursor: String? = null): Result<MessagesPage> {
        val result = safeApiCall { api.getMessages(conversationId, cursor) }
        if (result is Result.Success) {
            val page = result.data
            val entities = page.messages.map { m ->
                MessageEntity(
                    id = m.id,
                    conversationId = m.conversationId,
                    senderId = m.senderId,
                    content = m.content,
                    translation = m.translation,
                    status = m.status,
                    createdAt = m.createdAt,
                    deleted = m.deleted
                )
            }
            messageDao.upsertAll(entities)
        }
        return result
    }

    fun observeMessages(conversationId: String): Flow<List<MessageEntity>> =
        messageDao.observeMessages(conversationId)

    suspend fun insertMessage(entity: MessageEntity) {
        messageDao.insert(entity)
    }

    suspend fun insertMessages(entities: List<MessageEntity>) {
        messageDao.upsertAll(entities)
    }

    suspend fun updateMessageTranslation(messageId: String, translation: String) {
        messageDao.updateTranslation(messageId, translation)
    }

    suspend fun markMessageDeleted(messageId: String) {
        messageDao.markDeleted(messageId)
    }

    suspend fun updateMessageStatus(messageId: String, status: String) {
        messageDao.updateStatus(messageId, status)
    }

    suspend fun translateMessage(messageId: String, language: String): Result<TranslateMessageDataResponse> =
        safeApiCall { api.translateMessage(messageId, TranslateMessageRequest(language)) }

    suspend fun deleteMessage(messageId: String): Result<MessageResponse> = safeApiCall {
        api.deleteMessage(messageId)
    }
}

// ────────────────────────────────────────────────────────────────────
//  FriendRepository
// ────────────────────────────────────────────────────────────────────
@Singleton
class FriendRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun registerDevice(fcmToken: String, deviceName: String): Result<MessageResponse> = safeApiCall {
        api.registerDevice(RegisterDeviceRequest(fcmToken, deviceName))
    }

    suspend fun getFriends(): Result<List<Friendship>> {
        val result = safeApiCall { api.getFriends() }
        return when (result) {
            is Result.Success -> Result.Success(result.data.friends)
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun unfriend(friendshipId: String): Result<MessageResponse> = safeApiCall {
        api.unfriend(friendshipId)
    }

    suspend fun sendFriendRequest(toUserId: String): Result<FriendRequest> {
        val result = safeApiCall {
            api.sendFriendRequest(SendFriendRequest(toUserId))
        }
        return when (result) {
            is Result.Success -> Result.Success(result.data.request)
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun getReceivedRequests(): Result<List<FriendRequest>> {
        val result = safeApiCall { api.getReceivedRequests() }
        return when (result) {
            is Result.Success -> Result.Success(result.data.requests)
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun getSentRequests(): Result<List<FriendRequest>> {
        val result = safeApiCall { api.getSentRequests() }
        return when (result) {
            is Result.Success -> Result.Success(result.data.requests)
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun acceptRequest(requestId: String): Result<AcceptRequestDataResponse> = safeApiCall {
        api.acceptFriendRequest(requestId)
    }

    suspend fun declineRequest(requestId: String): Result<MessageResponse> = safeApiCall {
        api.declineFriendRequest(requestId)
    }

    suspend fun cancelRequest(requestId: String): Result<MessageResponse> = safeApiCall {
        api.cancelFriendRequest(requestId)
    }

    suspend fun blockUser(userId: String): Result<MessageResponse> = safeApiCall {
        api.blockUser(BlockRequest(userId))
    }

    suspend fun unblockUser(userId: String): Result<MessageResponse> = safeApiCall {
        api.unblockUser(userId)
    }

    suspend fun getBlockedUsers(): Result<Map<String, Any>> = safeApiCall { api.getBlockedUsers() }
}

// ────────────────────────────────────────────────────────────────────
//  VoiceRepository
// ────────────────────────────────────────────────────────────────────
@Singleton
class VoiceRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun getSentences(): Result<VoiceSentencesDataResponse> = safeApiCall {
        api.getVoiceSentences()
    }

    suspend fun uploadSample(
        audioPart: MultipartBody.Part,
        sampleIndex: Int,
        sentenceId: String
    ): Result<VoiceSampleDataResponse> = safeApiCall {
        api.uploadVoiceSample(audioPart, sampleIndex, sentenceId)
    }

    suspend fun deleteSample(index: Int): Result<MessageResponse> = safeApiCall {
        api.deleteVoiceSample(index)
    }

    suspend fun trainVoice(): Result<VoiceTrainDataResponse> = safeApiCall { api.trainVoice() }

    suspend fun getVoiceStatus(): Result<VoiceStatusDataResponse> = safeApiCall { api.getVoiceStatus() }

    suspend fun resetVoice(): Result<MessageResponse> = safeApiCall { api.resetVoice() }
}

// ────────────────────────────────────────────────────────────────────
//  CallRepository
// ────────────────────────────────────────────────────────────────────
@Singleton
class CallRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun initiateCall(calleeId: String, language: String? = null): Result<InitiateCallDataResponse> =
        safeApiCall { api.initiateCall(InitiateCallRequest(calleeId, language)) }

    suspend fun getIceConfig(roomId: String): Result<IceConfigDataResponse> = safeApiCall {
        api.getIceConfig(roomId)
    }

    suspend fun endCall(roomId: String): Result<MessageResponse> = safeApiCall { api.endCall(roomId) }

    suspend fun declineCall(roomId: String): Result<MessageResponse> = safeApiCall {
        api.declineCall(roomId)
    }
}
