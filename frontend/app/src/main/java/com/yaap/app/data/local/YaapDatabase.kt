package com.yaap.app.data.local

import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import android.content.Context
import com.yaap.app.data.local.dao.*
import com.yaap.app.data.local.entity.*

@Database(
    entities = [
        ConversationEntity::class,
        MessageEntity::class,
        UserEntity::class,
        FriendRequestEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class YaapDatabase : RoomDatabase() {
    abstract fun conversationDao(): ConversationDao
    abstract fun messageDao(): MessageDao
    abstract fun userDao(): UserDao
    abstract fun friendRequestDao(): FriendRequestDao

    companion object {
        fun create(context: Context): YaapDatabase =
            Room.databaseBuilder(context, YaapDatabase::class.java, "yaap.db")
                .fallbackToDestructiveMigration()
                .build()
    }
}
