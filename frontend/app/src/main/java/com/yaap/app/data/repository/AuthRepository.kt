package com.yaap.app.data.repository

import com.yaap.app.data.api.YaapApiService
import com.yaap.app.model.*
import com.yaap.app.utils.Result
import com.yaap.app.utils.TokenManager
import com.yaap.app.utils.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: YaapApiService,
    private val tokenManager: TokenManager
) {
    suspend fun login(email: String, password: String): Result<AuthResponse> =
        safeCall { api.login(LoginRequest(email, password)) }.map { it.toAuthResponse() }

    suspend fun signup(
        email: String,
        password: String,
        passwordConfirm: String,
        fullName: String
    ): Result<AuthResponse> = safeCall {
        api.signup(
            SignupRequest(
                email = email,
                password = password,
                passwordConfirm = passwordConfirm,
                fullName = fullName
            )
        )
    }.map { it.toAuthResponse() }

    suspend fun requestOtp(email: String): Result<MessageResponse> =
        safeCall { api.requestOtp(OtpRequestBody(email)) }.map { data ->
            MessageResponse(message = data.message, expiresInSeconds = data.expiresInSeconds)
        }

    suspend fun verifyOtp(email: String, otp: String): Result<AuthResponse> =
        safeCall { api.verifyOtp(OtpVerifyRequest(email = email, code = otp)) }.map { it.toAuthResponse() }

    suspend fun googleAuth(idToken: String): Result<AuthResponse> =
        safeCall { api.googleAuth(GoogleAuthRequest(idToken)) }.map { it.toAuthResponse() }

    suspend fun logout(): Result<MessageResponse> = safeCall { api.logout() }

    suspend fun checkPasswordStrength(password: String): Result<PasswordStrengthResponse> =
        safeCall { api.checkPasswordStrength(PasswordStrengthRequest(password)) }
            .map { it.toPasswordStrengthResponse() }

    suspend fun resetPassword(email: String): Result<MessageResponse> =
        safeCall { api.resetPassword(OtpRequestBody(email)) }

    fun saveTokens(accessToken: String, refreshToken: String) =
        tokenManager.saveTokens(accessToken, refreshToken)

    fun clearTokens() = tokenManager.clearTokens()
}
