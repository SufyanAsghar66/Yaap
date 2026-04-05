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
        val result = safeCall { api.getConversations() }
        if (result is Result.Success) {
            val entities = result.data.map { c ->
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
        }
        return result
    }

    suspend fun startConversation(userId: String): Result<StartConversationResponse> = safeCall {
        api.startConversation(StartConversationRequest(userId))
    }

    suspend fun getMessages(conversationId: String, cursor: String? = null): Result<MessagesPage> {
        val result = safeCall { api.getMessages(conversationId, cursor) }
        if (result is Result.Success) {
            val entities = result.data.messages.map { m ->
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

    suspend fun translateMessage(messageId: String, language: String): Result<TranslateMessageResponse> =
        safeCall { api.translateMessage(messageId, TranslateMessageRequest(language)) }

    suspend fun deleteMessage(messageId: String): Result<MessageResponse> = safeCall {
        api.deleteMessage(messageId)
    }
}

// ────────────────────────────────────────────────────────────────────
//  FriendRepository
// ────────────────────────────────────────────────────────────────────
@Singleton
class FriendRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun registerDevice(fcmToken: String, deviceName: String): Result<MessageResponse> = safeCall {
        api.registerDevice(RegisterDeviceRequest(fcmToken, deviceName))
    }

    suspend fun getFriends(): Result<List<Friendship>> = safeCall { api.getFriends() }

    suspend fun unfriend(friendshipId: String): Result<MessageResponse> = safeCall {
        api.unfriend(friendshipId)
    }

    suspend fun sendFriendRequest(toUserId: String): Result<FriendRequest> = safeCall {
        api.sendFriendRequest(SendFriendRequest(toUserId))
    }

    suspend fun getReceivedRequests(): Result<List<FriendRequest>> = safeCall {
        api.getReceivedRequests()
    }

    suspend fun getSentRequests(): Result<List<FriendRequest>> = safeCall {
        api.getSentRequests()
    }

    suspend fun acceptRequest(requestId: String): Result<Friendship> = safeCall {
        api.acceptFriendRequest(requestId)
    }

    suspend fun declineRequest(requestId: String): Result<MessageResponse> = safeCall {
        api.declineFriendRequest(requestId)
    }

    suspend fun cancelRequest(requestId: String): Result<MessageResponse> = safeCall {
        api.cancelFriendRequest(requestId)
    }

    suspend fun blockUser(userId: String): Result<MessageResponse> = safeCall {
        api.blockUser(BlockRequest(userId))
    }

    suspend fun unblockUser(userId: String): Result<MessageResponse> = safeCall {
        api.unblockUser(userId)
    }

    suspend fun getBlockedUsers(): Result<List<User>> = safeCall { api.getBlockedUsers() }
}

// ────────────────────────────────────────────────────────────────────
//  VoiceRepository
// ────────────────────────────────────────────────────────────────────
@Singleton
class VoiceRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun getSentences(): Result<List<VoiceSentence>> = safeCall { api.getVoiceSentences() }

    suspend fun uploadSample(
        audioPart: MultipartBody.Part,
        sampleIndex: Int,
        sentenceId: String
    ): Result<VoiceSampleResponse> = safeCall {
        api.uploadVoiceSample(audioPart, sampleIndex, sentenceId)
    }

    suspend fun deleteSample(index: Int): Result<MessageResponse> = safeCall {
        api.deleteVoiceSample(index)
    }

    suspend fun trainVoice(): Result<VoiceTrainResponse> = safeCall { api.trainVoice() }

    suspend fun getVoiceStatus(): Result<VoiceStatusResponse> = safeCall { api.getVoiceStatus() }

    suspend fun resetVoice(): Result<MessageResponse> = safeCall { api.resetVoice() }
}

// ────────────────────────────────────────────────────────────────────
//  CallRepository
// ────────────────────────────────────────────────────────────────────
@Singleton
class CallRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun initiateCall(calleeId: String, language: String? = null): Result<InitiateCallResponse> =
        safeCall { api.initiateCall(InitiateCallRequest(calleeId, language)) }

    suspend fun getIceConfig(roomId: String): Result<IceConfigResponse> = safeCall {
        api.getIceConfig(roomId)
    }

    suspend fun endCall(roomId: String): Result<MessageResponse> = safeCall { api.endCall(roomId) }

    suspend fun declineCall(roomId: String): Result<MessageResponse> = safeCall {
        api.declineCall(roomId)
    }
}
