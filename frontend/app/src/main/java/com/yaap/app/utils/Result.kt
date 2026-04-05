package com.yaap.app.utils

/**
 * Generic sealed class representing UI state for any async operation.
 * ViewModels emit StateFlow<Result<T>> to the UI layer.
 */
sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val message: String, val code: Int? = null) : Result<Nothing>()
    object Loading : Result<Nothing>()
    object Idle : Result<Nothing>()
}

/**
 * Extension to safely map success data.
 */
inline fun <T, R> Result<T>.map(transform: (T) -> R): Result<R> = when (this) {
    is Result.Success -> Result.Success(transform(data))
    is Result.Error -> this
    is Result.Loading -> Result.Loading
    is Result.Idle -> Result.Idle
}

/**
 * Extension to handle success case inline.
 */
inline fun <T> Result<T>.onSuccess(action: (T) -> Unit): Result<T> {
    if (this is Result.Success) action(data)
    return this
}

/**
 * Extension to handle error case inline.
 */
inline fun <T> Result<T>.onError(action: (String, Int?) -> Unit): Result<T> {
    if (this is Result.Error) action(message, code)
    return this
}
