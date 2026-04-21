package com.yaap.app.data.repository

import com.yaap.app.data.api.YaapApiService
import com.yaap.app.model.*
import com.yaap.app.utils.Result
import okhttp3.MultipartBody
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UserRepository @Inject constructor(private val api: YaapApiService) {

    suspend fun getMyProfile(): Result<User> = safeApiCall { api.getMyProfile() }

    suspend fun updateProfile(request: UpdateProfileRequest): Result<User> = safeApiCall {
        api.updateProfile(request)
    }

    suspend fun uploadAvatar(avatarPart: MultipartBody.Part): Result<Map<String, String>> = safeApiCall {
        api.uploadAvatar(avatarPart)
    }

    suspend fun updateLanguage(language: String): Result<Map<String, String>> = safeApiCall {
        api.updateLanguage(LanguageUpdateRequest(language))
    }

    suspend fun getLanguages(): Result<List<Language>> {
        val result = safeApiCall { api.getLanguages() }
        return when (result) {
            is Result.Success -> Result.Success(result.data.languages)
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun searchUsers(query: String): Result<List<UserSearchResult>> {
        val result = safeApiCall { api.searchUsers(query) }
        return when (result) {
            is Result.Success -> Result.Success(result.data.results)
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun getUserProfile(userId: String): Result<User> = safeApiCall {
        api.getUserProfile(userId)
    }
}
