package com.yaap.app.data.local.dao

import androidx.room.*
import com.yaap.app.data.local.entity.*
import kotlinx.coroutines.flow.Flow

@Dao
interface ConversationDao {
    @Query("SELECT * FROM conversations ORDER BY updatedAt DESC")
    fun observeAll(): Flow<List<ConversationEntity>>

    @Query("SELECT * FROM conversations ORDER BY updatedAt DESC")
    suspend fun getAll(): List<ConversationEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(conversations: List<ConversationEntity>)

    @Query("DELETE FROM conversations WHERE id = :id")
    suspend fun delete(id: String)

    @Query("UPDATE conversations SET unreadCount = 0 WHERE id = :id")
    suspend fun markRead(id: String)
}

@Dao
interface MessageDao {
    @Query("SELECT * FROM messages WHERE conversationId = :conversationId ORDER BY createdAt DESC LIMIT 50")
    fun observeMessages(conversationId: String): Flow<List<MessageEntity>>

    @Query("SELECT * FROM messages WHERE conversationId = :conversationId ORDER BY createdAt DESC LIMIT :limit OFFSET :offset")
    suspend fun getMessages(conversationId: String, limit: Int = 50, offset: Int = 0): List<MessageEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(messages: List<MessageEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(message: MessageEntity)

    @Query("UPDATE messages SET status = :status WHERE id = :id")
    suspend fun updateStatus(id: String, status: String)

    @Query("UPDATE messages SET translation = :translation WHERE id = :id")
    suspend fun updateTranslation(id: String, translation: String)

    @Query("UPDATE messages SET deleted = 1, content = 'This message was deleted.' WHERE id = :id")
    suspend fun markDeleted(id: String)
}

@Dao
interface UserDao {
    @Query("SELECT * FROM users WHERE id = :id")
    suspend fun getById(id: String): UserEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(user: UserEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(users: List<UserEntity>)

    @Query("UPDATE users SET isOnline = :online WHERE id = :id")
    suspend fun updateOnlineStatus(id: String, online: Boolean)
}

@Dao
interface FriendRequestDao {
    @Query("SELECT * FROM friend_requests WHERE status = 'pending' ORDER BY createdAt DESC")
    fun observePendingReceived(): Flow<List<FriendRequestEntity>>

    @Query("SELECT COUNT(*) FROM friend_requests WHERE status = 'pending'")
    fun observePendingCount(): Flow<Int>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(requests: List<FriendRequestEntity>)

    @Query("DELETE FROM friend_requests WHERE id = :id")
    suspend fun delete(id: String)
}
