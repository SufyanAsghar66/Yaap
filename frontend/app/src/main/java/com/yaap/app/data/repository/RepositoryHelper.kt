package com.yaap.app.data.repository

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.annotations.SerializedName
import com.yaap.app.model.ApiError
import com.yaap.app.utils.Result
import retrofit2.Response
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

/**
 * Wraps a Retrofit suspend call in a [Result], parsing YAAP error envelopes.
 * Successful bodies are expected to be already unwrapped by [com.yaap.app.data.api.YaapEnvelopeInterceptor].
 */
suspend fun <T> safeCall(call: suspend () -> Response<T>): Result<T> {
    return try {
        val response = call()
        if (response.isSuccessful) {
            val body = response.body()
            if (body != null) Result.Success(body)
            else Result.Error("Empty response", response.code())
        } else {
            val raw = response.errorBody()?.string()
            Result.Error(parseYaapErrorMessage(raw), response.code())
        }
    } catch (e: SocketTimeoutException) {
        Result.Error("Request timed out. Check your connection.")
    } catch (e: ConnectException) {
        Result.Error("Unable to connect. Check your network.")
    } catch (e: UnknownHostException) {
        Result.Error("No internet connection.")
    } catch (e: Exception) {
        Result.Error(e.message ?: "Unexpected error")
    }
}

private data class YaapErrorEnvelope(
    @SerializedName("success") val success: Boolean? = null,
    @SerializedName("error") val error: YaapErrorBody? = null
)

private data class YaapErrorBody(
    @SerializedName("message") val message: String? = null,
    @SerializedName("code") val code: String? = null
)

internal fun parseYaapErrorMessage(errorBody: String?): String {
    if (errorBody.isNullOrBlank()) return "Unknown error"
    return try {
        val env = Gson().fromJson(errorBody, YaapErrorEnvelope::class.java)
        env.error?.message?.takeIf { it.isNotBlank() }
            ?: extractFirstFieldError(errorBody)
            ?: errorBody
    } catch (_: Exception) {
        try {
            Gson().fromJson(errorBody, ApiError::class.java)?.message?.takeIf { it.isNotBlank() }
                ?: errorBody
        } catch (_: Exception) {
            errorBody
        }
    }
}

/** DRF validation errors sometimes appear only under `details` / field keys. */
private fun extractFirstFieldError(json: String): String? {
    return try {
        val o = Gson().fromJson(json, JsonObject::class.java) ?: return null
        val err = o.getAsJsonObject("error") ?: return null
        val details = err.get("details")?.takeIf { it.isJsonObject }?.asJsonObject ?: return null
        for ((key, value) in details.entrySet()) {
            if (value.isJsonArray && value.asJsonArray.size() > 0) {
                val first = value.asJsonArray[0]
                if (first.isJsonPrimitive) return "$key: ${first.asString}"
            }
        }
        null
    } catch (_: Exception) {
        null
    }
}
