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
    suspend fun login(email: String, password: String): Result<AuthResponse> = safeCall {
        api.login(LoginRequest(email, password))
    }

    suspend fun signup(email: String, password: String, fullName: String): Result<AuthResponse> = safeCall {
        api.signup(SignupRequest(email, password, fullName))
    }

    suspend fun requestOtp(email: String): Result<MessageResponse> = safeCall {
        api.requestOtp(OtpRequestBody(email))
    }

    suspend fun verifyOtp(email: String, otp: String): Result<AuthResponse> = safeCall {
        api.verifyOtp(OtpVerifyRequest(email, otp))
    }

    suspend fun googleAuth(idToken: String): Result<AuthResponse> = safeCall {
        api.googleAuth(GoogleAuthRequest(idToken))
    }

    suspend fun logout(): Result<MessageResponse> = safeCall { api.logout() }

    suspend fun checkPasswordStrength(password: String): Result<PasswordStrengthResponse> = safeCall {
        api.checkPasswordStrength(PasswordStrengthRequest(password))
    }

    suspend fun resetPassword(email: String): Result<MessageResponse> = safeCall {
        api.resetPassword(OtpRequestBody(email))
    }

    fun saveTokens(accessToken: String, refreshToken: String) =
        tokenManager.saveTokens(accessToken, refreshToken)

    fun clearTokens() = tokenManager.clearTokens()
}
