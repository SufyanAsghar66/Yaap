package com.yaap.app.data.local.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "conversations")
data class ConversationEntity(
    @PrimaryKey val id: String,
    val otherUserId: String,
    val otherUserName: String,
    val otherUserAvatar: String?,
    val otherUserCountryCode: String?,
    val otherUserTimezone: String?,
    val otherUserOnline: Boolean = false,
    val lastMessageContent: String?,
    val lastMessageTranslation: String?,
    val lastMessageTimestamp: String?,
    val unreadCount: Int = 0,
    val updatedAt: String
)

@Entity(tableName = "messages", indices = [Index("conversationId")])
data class MessageEntity(
    @PrimaryKey val id: String,
    val conversationId: String,
    val senderId: String,
    val content: String,
    val translation: String?,
    val status: String,
    val createdAt: String,
    val deleted: Boolean = false
)

@Entity(tableName = "users")
data class UserEntity(
    @PrimaryKey val id: String,
    val displayName: String,
    val email: String,
    val avatarUrl: String?,
    val countryCode: String?,
    val timezone: String?,
    val bio: String?,
    val isOnline: Boolean = false,
    val languagePreference: String?,
    val voiceTrained: Boolean = false
)

@Entity(tableName = "friend_requests", indices = [Index("fromUserId")])
data class FriendRequestEntity(
    @PrimaryKey val id: String,
    val fromUserId: String,
    val fromUserName: String,
    val fromUserAvatar: String?,
    val toUserId: String,
    val status: String,
    val message: String?,
    val createdAt: String
)
