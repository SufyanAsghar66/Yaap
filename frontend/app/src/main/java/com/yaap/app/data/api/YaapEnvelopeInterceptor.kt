package com.yaap.app.data.api

import com.google.gson.JsonParser
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody

/**
 * The Django API wraps successful JSON as `{ "success": true, "data": <payload> }`.
 * This interceptor replaces the body with `<payload>` only so Retrofit + Gson can
 * deserialize using the inner shape (e.g. [com.yaap.app.model.User] for /users/me/).
 *
 * Error responses (`success: false`) are left unchanged for [com.yaap.app.data.repository.parseYaapErrorMessage].
 */
class YaapEnvelopeInterceptor : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())
        if (!response.isSuccessful) return response
        val body = response.body ?: return response
        val contentType = body.contentType()
        val raw = body.string()

        return try {
            val root = JsonParser.parseString(raw).takeIf { it.isJsonObject }?.asJsonObject
                ?: return response.newBuilder().body(raw.toResponseBody(contentType)).build()

            val successEl = root.get("success") ?: return response.newBuilder()
                .body(raw.toResponseBody(contentType)).build()
            if (!successEl.isJsonPrimitive || !successEl.asBoolean || !root.has("data")) {
                return response.newBuilder().body(raw.toResponseBody(contentType)).build()
            }

            val dataEl = root.get("data")
            val innerJson = when {
                dataEl.isJsonNull -> "null"
                else -> dataEl.toString()
            }
            val newBody = innerJson.toResponseBody((contentType ?: "application/json".toMediaTypeOrNull()))
            response.newBuilder().body(newBody).build()
        } catch (_: Exception) {
            response.newBuilder().body(raw.toResponseBody(contentType)).build()
        }
    }
}
