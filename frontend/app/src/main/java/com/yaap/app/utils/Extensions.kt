package com.yaap.app.utils

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.ImageView
import android.widget.Toast
import androidx.fragment.app.Fragment
import com.bumptech.glide.Glide
import com.bumptech.glide.load.resource.bitmap.CircleCrop
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.debounce
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

// ---- View extensions ----

fun View.show() { visibility = View.VISIBLE }
fun View.hide() { visibility = View.GONE }
fun View.invisible() { visibility = View.INVISIBLE }
fun View.isVisible() = visibility == View.VISIBLE

fun View.showSnackbar(message: String, duration: Int = Snackbar.LENGTH_SHORT) {
    Snackbar.make(this, message, duration).show()
}

fun View.showSnackbarError(message: String) {
    Snackbar.make(this, message, Snackbar.LENGTH_LONG).show()
}

// ---- EditText extensions ----

fun EditText.textFlow(): Flow<String> = callbackFlow {
    val watcher = object : android.text.TextWatcher {
        override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
        override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
            trySend(s.toString())
        }
        override fun afterTextChanged(s: android.text.Editable?) {}
    }
    addTextChangedListener(watcher)
    awaitClose { removeTextChangedListener(watcher) }
}.debounce(Constants.SEARCH_DEBOUNCE_MS)

fun EditText.textString() = text.toString().trim()

// ---- Activity extensions ----

fun Activity.hideKeyboard() {
    val imm = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
    imm.hideSoftInputFromWindow(currentFocus?.windowToken, 0)
}

fun Activity.toast(message: String) {
    Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
}

// ---- Fragment extensions ----

fun Fragment.toast(message: String) {
    Toast.makeText(requireContext(), message, Toast.LENGTH_SHORT).show()
}

// ---- ImageView extensions ----

fun ImageView.loadAvatar(url: String?, initials: String = "?") {
    if (url.isNullOrBlank()) {
        // Glide placeholder with initials will be handled by a custom target
        // For simplicity, set a default placeholder drawable
        setImageResource(android.R.drawable.ic_menu_myplaces)
    } else {
        Glide.with(context)
            .load(url)
            .transform(CircleCrop())
            .placeholder(android.R.drawable.ic_menu_myplaces)
            .error(android.R.drawable.ic_menu_myplaces)
            .into(this)
    }
}

fun ImageView.loadRounded(url: String?, cornerRadius: Int = 12) {
    Glide.with(context)
        .load(url)
        .placeholder(android.R.drawable.ic_menu_gallery)
        .error(android.R.drawable.ic_menu_gallery)
        .into(this)
}

// ---- Date/Time extensions ----

fun String.toLocalTime(timezone: String): String {
    return try {
        // Assumes input is UTC ISO8601 datetime
        val tz = TimeZone.getTimeZone(timezone)
        val sdf = SimpleDateFormat("HH:mm", Locale.getDefault()).apply {
            timeZone = tz
        }
        sdf.format(Date()) // Use current time converted to their timezone
    } catch (e: Exception) {
        "--:--"
    }
}

fun getCurrentTimeInTimezone(timezone: String): String {
    return try {
        val tz = TimeZone.getTimeZone(timezone)
        val sdf = SimpleDateFormat("HH:mm", Locale.getDefault()).apply {
            timeZone = tz
        }
        sdf.format(Date())
    } catch (e: Exception) {
        "--:--"
    }
}

fun String.toMessageTimestamp(): String {
    return try {
        val inputSdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.getDefault()).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val date = inputSdf.parse(this) ?: return this
        val now = Date()
        val diffMs = now.time - date.time
        val diffHours = diffMs / (1000 * 60 * 60)
        when {
            diffHours < 1 -> {
                val diffMins = diffMs / (1000 * 60)
                if (diffMins < 1) "Just now" else "${diffMins}m ago"
            }
            diffHours < 24 -> {
                SimpleDateFormat("HH:mm", Locale.getDefault()).format(date)
            }
            else -> SimpleDateFormat("MMM d", Locale.getDefault()).format(date)
        }
    } catch (e: Exception) {
        this
    }
}

// ---- Intent extras helper ----

inline fun <reified T : Activity> Context.startActivity(vararg extras: Pair<String, Any?>) {
    val intent = Intent(this, T::class.java)
    extras.forEach { (key, value) ->
        when (value) {
            is String -> intent.putExtra(key, value)
            is Int -> intent.putExtra(key, value)
            is Boolean -> intent.putExtra(key, value)
            is Long -> intent.putExtra(key, value)
        }
    }
    startActivity(intent)
}

// ---- Validation extensions ----

fun String.isValidEmail(): Boolean {
    return android.util.Patterns.EMAIL_ADDRESS.matcher(this).matches()
}

fun String.isValidPassword(): Boolean = length >= Constants.MIN_PASSWORD_LENGTH
