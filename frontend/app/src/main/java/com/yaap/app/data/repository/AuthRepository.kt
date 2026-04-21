package com.yaap.app.data.repository

import com.yaap.app.data.api.YaapApiService
import com.yaap.app.model.*
import com.yaap.app.utils.Result
import com.yaap.app.utils.TokenManager
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: YaapApiService,
    private val tokenManager: TokenManager
) {
    /**
     * Login → unwrap envelope → extract tokens → return AuthResponse for UI.
     */
    suspend fun login(email: String, password: String): Result<AuthResponse> {
        val result = safeApiCall { api.login(LoginRequest(email, password)) }
        return when (result) {
            is Result.Success -> {
                val data = result.data
                tokenManager.saveTokens(data.tokens.access, data.tokens.refresh)
                Result.Success(AuthResponse.from(data))
            }
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    /**
     * Signup → sends password_confirm = password (backend requires it).
     */
    suspend fun signup(email: String, password: String, fullName: String): Result<AuthResponse> {
        val result = safeApiCall {
            api.signup(SignupRequest(email, password, fullName, passwordConfirm = password))
        }
        return when (result) {
            is Result.Success -> {
                val data = result.data
                tokenManager.saveTokens(data.tokens.access, data.tokens.refresh)
                Result.Success(AuthResponse.from(data))
            }
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun requestOtp(email: String): Result<MessageResponse> = safeApiCall {
        api.requestOtp(OtpRequestBody(email))
    }

    suspend fun verifyOtp(email: String, otp: String): Result<AuthResponse> {
        val result = safeApiCall { api.verifyOtp(OtpVerifyRequest(email, otp)) }
        return when (result) {
            is Result.Success -> {
                val data = result.data
                tokenManager.saveTokens(data.tokens.access, data.tokens.refresh)
                Result.Success(AuthResponse.from(data))
            }
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun googleAuth(idToken: String): Result<AuthResponse> {
        val result = safeApiCall { api.googleAuth(GoogleAuthRequest(idToken)) }
        return when (result) {
            is Result.Success -> {
                val data = result.data
                tokenManager.saveTokens(data.tokens.access, data.tokens.refresh)
                Result.Success(AuthResponse.from(data))
            }
            is Result.Error -> Result.Error(result.message, result.code)
            is Result.Loading -> Result.Loading
            is Result.Idle -> Result.Idle
        }
    }

    suspend fun logout(): Result<MessageResponse> = safeApiCall { api.logout() }

    suspend fun checkPasswordStrength(password: String): Result<PasswordStrengthResponse> = safeApiCall {
        api.checkPasswordStrength(PasswordStrengthRequest(password))
    }

    suspend fun resetPassword(email: String): Result<MessageResponse> = safeApiCall {
        api.resetPassword(OtpRequestBody(email))
    }

    fun saveTokens(accessToken: String, refreshToken: String) =
        tokenManager.saveTokens(accessToken, refreshToken)

    fun clearTokens() = tokenManager.clearTokens()
}
