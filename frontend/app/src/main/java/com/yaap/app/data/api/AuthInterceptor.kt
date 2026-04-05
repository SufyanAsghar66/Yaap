package com.yaap.app.data.api
import com.yaap.app.model.RefreshTokenRequest
import com.yaap.app.utils.TokenManager
import dagger.Lazy
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.Request
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
                val refreshResponse = lazyApiService.get()
                    .refreshToken(RefreshTokenRequest(refresh = refreshToken))
                if (refreshResponse.isSuccessful) {
                    val body = refreshResponse.body()!!
                    tokenManager.saveTokens(body.tokens.access, body.tokens.refresh)
                    response.request.newBuilder()
                        .header("Authorization", "Bearer ${body.tokens.access}")
                        .header("X-Retry-After-Refresh", "true")
                        .build()
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