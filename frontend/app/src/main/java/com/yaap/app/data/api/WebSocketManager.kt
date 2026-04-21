package com.yaap.app.data.api

import com.yaap.app.utils.Constants
import com.yaap.app.utils.TokenManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class WebSocketManager @Inject constructor(
    private val okHttpClient: OkHttpClient,
    private val tokenManager: TokenManager
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private var presenceWebSocket: WebSocket? = null
    private var reconnectAttempt = 0
    private var pingJob: Job? = null
    private var isConnected = false

    private val _presenceEvents = MutableSharedFlow<JSONObject>(replay = 0, extraBufferCapacity = 64)
    val presenceEvents: SharedFlow<JSONObject> = _presenceEvents

    fun connect() {
        if (isConnected) return
        val token = tokenManager.getAccessToken() ?: return

        val url = "${Constants.WS_BASE_URL}/ws/presence/?token=$token"
        val request = Request.Builder().url(url).build()

        presenceWebSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                isConnected = true
                reconnectAttempt = 0
                startPingJob()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    scope.launch { _presenceEvents.emit(json) }
                } catch (e: Exception) { /* ignore malformed */ }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                stopPingJob()
                scheduleReconnect()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                stopPingJob()
            }
        })
    }

    fun disconnect() {
        isConnected = false
        stopPingJob()
        presenceWebSocket?.close(1000, "User logout")
        presenceWebSocket = null
        reconnectAttempt = 0
    }

    private fun startPingJob() {
        pingJob = scope.launch {
            while (isConnected) {
                delay(Constants.WS_PING_INTERVAL_MS)
                presenceWebSocket?.send("""{"type":"ping"}""")
            }
        }
    }

    private fun stopPingJob() {
        pingJob?.cancel()
        pingJob = null
    }

    private fun scheduleReconnect() {
        val delays = Constants.WS_BACKOFF_DELAYS
        val delayMs = delays.getOrElse(reconnectAttempt) { delays.last() }
        reconnectAttempt++
        scope.launch {
            delay(delayMs)
            if (!isConnected) connect()
        }
    }
}

/**
 * Per-conversation chat WebSocket. Created fresh for each ChatActivity.
 */
class ChatWebSocket(
    private val okHttpClient: OkHttpClient,
    private val conversationId: String,
    private val token: String
) {
    private var webSocket: WebSocket? = null
    private var isConnected = false
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var reconnectAttempt = 0

    private val _messages = MutableSharedFlow<JSONObject>(replay = 0, extraBufferCapacity = 128)
    val messages: SharedFlow<JSONObject> = _messages

    fun connect() {
        val url = "${Constants.WS_BASE_URL}/ws/chat/$conversationId/?token=$token"
        val request = Request.Builder().url(url).build()
        webSocket = okHttpClient.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                isConnected = true
                reconnectAttempt = 0
                // Load initial history
                send("""{"type":"load_history","payload":{"page_size":50}}""")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    scope.launch { _messages.emit(json) }
                } catch (_: Exception) {}
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                scheduleReconnect()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
            }
        })
    }

    fun send(payload: String) = webSocket?.send(payload)

    fun sendMessage(content: String) {
        val payload = JSONObject().put("content", content)
        send(JSONObject().put("type", "send_message").put("payload", payload).toString())
    }

    fun sendTypingStart() = send(JSONObject().put("type", "typing_start").put("payload", JSONObject()).toString())
    
    fun sendTypingStop() = send(JSONObject().put("type", "typing_stop").put("payload", JSONObject()).toString())
    
    fun sendMarkRead(messageId: String) {
        val payload = JSONObject().put("message_id", messageId)
        send(JSONObject().put("type", "mark_read").put("payload", payload).toString())
    }
    
    fun sendDeleteMessage(messageId: String, scope: String = "everyone") {
        val payload = JSONObject().put("message_id", messageId).put("scope", scope)
        send(JSONObject().put("type", "delete_message").put("payload", payload).toString())
    }

    fun loadHistory(cursor: String) {
        val payload = JSONObject().put("cursor", cursor).put("page_size", 50)
        send(JSONObject().put("type", "load_history").put("payload", payload).toString())
    }

    fun disconnect() {
        isConnected = false
        webSocket?.close(1000, "Activity destroyed")
        webSocket = null
    }

    private fun scheduleReconnect() {
        val delays = Constants.WS_BACKOFF_DELAYS
        val delayMs = delays.getOrElse(reconnectAttempt) { delays.last() }
        reconnectAttempt++
        scope.launch {
            delay(delayMs)
            if (!isConnected) connect()
        }
    }
}
