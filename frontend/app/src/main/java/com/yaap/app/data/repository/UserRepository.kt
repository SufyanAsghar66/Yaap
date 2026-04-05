package com.yaap.app.data.repository

import com.yaap.app.data.api.YaapApiService
import com.yaap.app.model.*
import com.yaap.app.utils.Result
import com.yaap.app.utils.map
import okhttp3.MultipartBody
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UserRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun getMyProfile(): Result<User> = safeCall { api.getMyProfile() }

    suspend fun updateProfile(request: UpdateProfileRequest): Result<User> = safeCall {
        api.updateProfile(request)
    }

    suspend fun uploadAvatar(avatarPart: MultipartBody.Part): Result<User> {
        when (val up = safeCall { api.uploadAvatar(avatarPart) }) {
            is Result.Error -> return up
            is Result.Success -> Unit
            else -> return Result.Error("Unexpected state")
        }
        return getMyProfile()
    }

    suspend fun updateLanguage(language: String): Result<User> {
        when (val r = safeCall { api.updateLanguage(LanguageUpdateRequest(language)) }) {
            is Result.Error -> return r
            is Result.Success -> Unit
            else -> return Result.Error("Unexpected state")
        }
        return getMyProfile()
    }

    suspend fun getLanguages(): Result<List<Language>> =
        safeCall { api.getLanguages() }.map { it.languages }

    suspend fun searchUsers(query: String): Result<List<UserSearchResult>> =
        safeCall { api.searchUsers(query) }.map { it.results }

    suspend fun getUserProfile(userId: String): Result<User> = safeCall {
        api.getUserProfile(userId)
    }
}
