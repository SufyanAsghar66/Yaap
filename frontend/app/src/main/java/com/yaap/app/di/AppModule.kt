package com.yaap.app.di

import android.content.Context
import com.yaap.app.BuildConfig
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.yaap.app.data.api.AuthInterceptor
import com.yaap.app.data.api.IceServerDeserializer
import com.yaap.app.data.api.TokenAuthenticator
import com.yaap.app.data.api.YaapApiService
import com.yaap.app.data.api.YaapEnvelopeInterceptor
import com.yaap.app.model.IceServer
import com.yaap.app.data.local.YaapDatabase
import com.yaap.app.data.local.dao.*
import dagger.Lazy
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideLoggingInterceptor(): HttpLoggingInterceptor =
        HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG)
                HttpLoggingInterceptor.Level.BODY
            else
                HttpLoggingInterceptor.Level.NONE
        }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: AuthInterceptor,
        envelopeInterceptor: YaapEnvelopeInterceptor,
        tokenAuthenticator: Lazy<TokenAuthenticator>,   // ← Lazy breaks the cycle
        loggingInterceptor: HttpLoggingInterceptor
    ): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(authInterceptor)
        .addInterceptor(envelopeInterceptor)
        .authenticator { route, response -> tokenAuthenticator.get().authenticate(route, response) }
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    @Provides
    @Singleton
    fun provideGson(): Gson =
        GsonBuilder()
            .registerTypeAdapter(IceServer::class.java, IceServerDeserializer())
            .create()

    @Provides
    @Singleton
    fun provideYaapEnvelopeInterceptor(): YaapEnvelopeInterceptor = YaapEnvelopeInterceptor()

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient, gson: Gson): Retrofit =
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()

    @Provides
    @Singleton
    fun provideApiService(retrofit: Retrofit): YaapApiService =
        retrofit.create(YaapApiService::class.java)
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): YaapDatabase =
        YaapDatabase.create(context)

    @Provides fun provideConversationDao(db: YaapDatabase): ConversationDao = db.conversationDao()
    @Provides fun provideMessageDao(db: YaapDatabase): MessageDao = db.messageDao()
    @Provides fun provideUserDao(db: YaapDatabase): UserDao = db.userDao()
    @Provides fun provideFriendRequestDao(db: YaapDatabase): FriendRequestDao = db.friendRequestDao()
}