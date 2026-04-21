package com.yaap.app.data.repository

import com.google.gson.Gson
import com.yaap.app.model.ApiEnvelope
import com.yaap.app.model.ApiError
import com.yaap.app.utils.Result
import retrofit2.Response

/**
 * Wraps a Retrofit suspend call that returns ApiEnvelope<T>,
 * automatically unwrapping the envelope and returning Result<T>.
 */
suspend fun <T> safeApiCall(call: suspend () -> Response<ApiEnvelope<T>>): Result<T> {
    return try {
        val response = call()
        if (response.isSuccessful) {
            val envelope = response.body()
            if (envelope != null && envelope.success && envelope.data != null) {
                Result.Success(envelope.data)
            } else if (envelope != null && !envelope.success) {
                val msg = envelope.error?.message ?: "Request failed"
                Result.Error(msg, response.code())
            } else {
                Result.Error("Empty response data", response.code())
            }
        } else {
            val errorBody = response.errorBody()?.string()
            val message = try {
                // Try to parse as envelope error first
                val envelope = Gson().fromJson(errorBody, ApiEnvelope::class.java)
                envelope?.error?.message ?: errorBody ?: "Unknown error"
            } catch (e: Exception) {
                try {
                    Gson().fromJson(errorBody, ApiError::class.java)?.message
                        ?: errorBody ?: "Error ${response.code()}"
                } catch (e2: Exception) {
                    errorBody ?: "Error ${response.code()}"
                }
            }
            Result.Error(message, response.code())
        }
    } catch (e: java.net.SocketTimeoutException) {
        Result.Error("Request timed out. Check your connection.")
    } catch (e: java.net.ConnectException) {
        Result.Error("Unable to connect. Check your network.")
    } catch (e: java.net.UnknownHostException) {
        Result.Error("No internet connection.")
    } catch (e: Exception) {
        Result.Error(e.message ?: "Unexpected error")
    }
}

/**
 * Wraps a Retrofit suspend call that returns a raw (non-envelope) response.
 * Used for endpoints that don't wrap in {"success": true, "data": ...}
 * (e.g. user profile endpoints that return the object directly).
 */
suspend fun <T> safeCall(call: suspend () -> Response<T>): Result<T> {
    return try {
        val response = call()
        if (response.isSuccessful) {
            val body = response.body()
            if (body != null) Result.Success(body)
            else Result.Error("Empty response", response.code())
        } else {
            val errorBody = response.errorBody()?.string()
            val message = try {
                Gson().fromJson(errorBody, ApiError::class.java)?.message
                    ?: errorBody ?: "Unknown error"
            } catch (e: Exception) {
                errorBody ?: "Error ${response.code()}"
            }
            Result.Error(message, response.code())
        }
    } catch (e: java.net.SocketTimeoutException) {
        Result.Error("Request timed out. Check your connection.")
    } catch (e: java.net.ConnectException) {
        Result.Error("Unable to connect. Check your network.")
    } catch (e: java.net.UnknownHostException) {
        Result.Error("No internet connection.")
    } catch (e: Exception) {
        Result.Error(e.message ?: "Unexpected error")
    }
}
