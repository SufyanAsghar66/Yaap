package com.yaap.app.data.repository

import com.yaap.app.data.api.YaapApiService
import com.yaap.app.model.*
import com.yaap.app.utils.Result
import okhttp3.MultipartBody
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UserRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun getMyProfile(): Result<User> = safeCall { api.getMyProfile() }

    suspend fun updateProfile(request: UpdateProfileRequest): Result<User> = safeCall {
        api.updateProfile(request)
    }

    suspend fun uploadAvatar(avatarPart: MultipartBody.Part): Result<User> = safeCall {
        api.uploadAvatar(avatarPart)
    }

    suspend fun updateLanguage(language: String): Result<User> = safeCall {
        api.updateLanguage(LanguageUpdateRequest(language))
    }

    suspend fun getLanguages(): Result<List<Language>> = safeCall { api.getLanguages() }

    suspend fun searchUsers(query: String): Result<List<UserSearchResult>> = safeCall {
        api.searchUsers(query)
    }

    suspend fun getUserProfile(userId: String): Result<User> = safeCall {
        api.getUserProfile(userId)
    }
}
