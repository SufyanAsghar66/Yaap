package com.yaap.app.data.repository

import com.google.gson.Gson
import com.yaap.app.model.ApiError
import com.yaap.app.utils.Result
import retrofit2.Response

/**
 * Wraps a Retrofit suspend call in a Result, parsing error bodies automatically.
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
