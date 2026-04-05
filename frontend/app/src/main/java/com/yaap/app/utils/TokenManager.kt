package com.yaap.app.utils

import android.content.Context
import android.util.Base64
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.yaap.app.utils.Constants.PREF_ACCESS_TOKEN
import com.yaap.app.utils.Constants.PREF_REFRESH_TOKEN
import dagger.hilt.android.qualifiers.ApplicationContext
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

data class JwtClaims(
    val userId: String?,
    val nextStep: String?,
    val email: String?
)

@Singleton
class TokenManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "yaap_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun saveTokens(accessToken: String, refreshToken: String) {
        prefs.edit()
            .putString(PREF_ACCESS_TOKEN, accessToken)
            .putString(PREF_REFRESH_TOKEN, refreshToken)
            .apply()
    }

    fun getAccessToken(): String? = prefs.getString(PREF_ACCESS_TOKEN, null)

    fun getRefreshToken(): String? = prefs.getString(PREF_REFRESH_TOKEN, null)

    fun clearTokens() {
        prefs.edit()
            .remove(PREF_ACCESS_TOKEN)
            .remove(PREF_REFRESH_TOKEN)
            .apply()
    }

    fun hasValidToken(): Boolean = getAccessToken() != null

    /**
     * Decode JWT payload (no signature verification — for routing only).
     * Returns null if token is missing or malformed.
     */
    fun decodeJwtClaims(): JwtClaims? {
        val token = getAccessToken() ?: return null
        return try {
            val parts = token.split(".")
            if (parts.size != 3) return null
            val payloadJson = String(Base64.decode(parts[1], Base64.URL_SAFE or Base64.NO_PADDING))
            val json = JSONObject(payloadJson)
            JwtClaims(
                userId = json.optString("user_id").takeIf { it.isNotBlank() },
                nextStep = json.optString("next_step").takeIf { it.isNotBlank() },
                email = json.optString("email").takeIf { it.isNotBlank() }
            )
        } catch (e: Exception) {
            null
        }
    }
}
