package com.yaap.app.data.api
import com.google.gson.Gson
import com.yaap.app.model.ApiEnvelope
import com.yaap.app.model.RefreshTokenRequest
import com.yaap.app.model.TokenRefreshDataResponse
import com.yaap.app.utils.TokenManager
import dagger.Lazy
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Attaches the Bearer token to every outgoing request.
 */
@Singleton
class AuthInterceptor @Inject constructor(
    private val tokenManager: TokenManager
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val token = tokenManager.getAccessToken()
        val request = if (token != null) {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

/**
 * On 401: attempts a token refresh and retries the original request.
 * Uses Lazy<YaapApiService> to break the Hilt circular dependency:
 *   YaapApiService → TokenAuthenticator → OkHttpClient → Retrofit → YaapApiService
 * Lazy defers the YaapApiService lookup until first actual 401, after the
 * entire object graph has been constructed.
 *
 * Key fix: Backend's SimpleJWT expects {"refresh": "..."} and returns
 * {"success": true, "data": {"tokens": {"access": "...", "refresh": "..."}}}
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokenManager: TokenManager,
    private val lazyApiService: Lazy<YaapApiService>   // ← Lazy breaks the cycle
) : Authenticator {

    override fun authenticate(route: Route?, response: Response): Request? {
        // Prevent infinite retry loops
        if (response.request.header("X-Retry-After-Refresh") != null) {
            tokenManager.clearTokens()
            return null
        }

        val refreshToken = tokenManager.getRefreshToken() ?: run {
            tokenManager.clearTokens()
            return null
        }

        return runBlocking {
            try {
                // Send {"refresh": "..."} — matches SimpleJWT's expected field name
                val refreshResponse = lazyApiService.get()
                    .refreshToken(RefreshTokenRequest(refreshToken))

                if (refreshResponse.isSuccessful) {
                    val envelope = refreshResponse.body()
                    if (envelope != null && envelope.success && envelope.data != null) {
                        val tokens = envelope.data.tokens
                        tokenManager.saveTokens(tokens.access, tokens.refresh)
                        response.request.newBuilder()
                            .header("Authorization", "Bearer ${tokens.access}")
                            .header("X-Retry-After-Refresh", "true")
                            .build()
                    } else {
                        tokenManager.clearTokens()
                        null
                    }
                } else {
                    tokenManager.clearTokens()
                    null
                }
            } catch (e: Exception) {
                tokenManager.clearTokens()
                null
            }
        }
    }
}