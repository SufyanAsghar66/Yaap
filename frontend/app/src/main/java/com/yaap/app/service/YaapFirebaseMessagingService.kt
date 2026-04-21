package com.yaap.app.service

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.yaap.app.R
import com.yaap.app.data.api.YaapApiService
import com.yaap.app.model.RegisterDeviceRequest
import com.yaap.app.ui.call.CallActivity
import com.yaap.app.ui.chat.ChatActivity
import com.yaap.app.ui.friends.FriendshipActivity
import com.yaap.app.ui.main.MainActivity
import com.yaap.app.utils.Constants
import com.yaap.app.utils.TokenManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class YaapFirebaseMessagingService : FirebaseMessagingService() {

    @Inject lateinit var apiService: YaapApiService
    @Inject lateinit var tokenManager: TokenManager

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    companion object {
        private const val TAG = "YaapFCM"
    }

    /**
     * Called when FCM generates a new registration token.
     * Posts the token to the backend so push notifications can be sent to this device.
     */
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "New FCM token received")

        // Only register if the user is logged in (has an access token)
        if (tokenManager.hasValidToken()) {
            serviceScope.launch {
                try {
                    val deviceName = "${Build.MANUFACTURER} ${Build.MODEL}"
                    val response = apiService.registerDevice(
                        RegisterDeviceRequest(fcmToken = token, deviceName = deviceName)
                    )
                    if (response.isSuccessful) {
                        Log.d(TAG, "FCM token registered with backend")
                    } else {
                        Log.w(TAG, "FCM token registration failed: ${response.code()}")
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "FCM token registration error", e)
                }
            }
        } else {
            Log.d(TAG, "User not logged in, skipping FCM token registration")
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val data = message.data
        when (data["type"]) {
            Constants.NOTIF_MESSAGE -> handleMessageNotification(data)
            Constants.NOTIF_CALL -> handleCallNotification(data)
            Constants.NOTIF_FRIEND_REQUEST -> handleFriendRequestNotification(data)
            Constants.NOTIF_VOICE_TRAINED -> handleVoiceTrainedNotification()
            Constants.NOTIF_MISSED_CALL -> handleMissedCallNotification(data)
        }
    }

    private fun handleMessageNotification(data: Map<String, String>) {
        val conversationId = data["conversation_id"] ?: return
        val senderName = data["sender_name"] ?: "Someone"
        val preview = data["preview"] ?: "Sent you a message"

        val intent = Intent(this, ChatActivity::class.java)
            .putExtra(Constants.EXTRA_CONVERSATION_ID, conversationId)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)

        val pendingIntent = PendingIntent.getActivity(
            this, conversationId.hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        showNotification(
            id = conversationId.hashCode(),
            channel = Constants.CHANNEL_MESSAGES,
            title = senderName,
            body = preview,
            pendingIntent = pendingIntent
        )
    }

    private fun handleCallNotification(data: Map<String, String>) {
        val roomId = data["room_id"] ?: return
        val callerName = data["caller_name"] ?: "Someone"
        val callerAvatar = data["caller_avatar"]

        val intent = Intent(this, CallActivity::class.java).apply {
            putExtra(Constants.EXTRA_ROOM_ID, roomId)
            putExtra(Constants.EXTRA_IS_INCOMING, true)
            putExtra(Constants.EXTRA_CALLER_NAME, callerName)
            putExtra(Constants.EXTRA_CALLER_AVATAR, callerAvatar)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }

        val pendingIntent = PendingIntent.getActivity(
            this, roomId.hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        val notification = NotificationCompat.Builder(this, Constants.CHANNEL_CALLS)
            .setSmallIcon(R.drawable.ic_call)
            .setContentTitle("Incoming Call")
            .setContentText("$callerName is calling…")
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setFullScreenIntent(pendingIntent, true)
            .setAutoCancel(true)
            .build()

        getSystemService(NotificationManager::class.java)
            .notify(roomId.hashCode(), notification)
    }

    private fun handleFriendRequestNotification(data: Map<String, String>) {
        val requesterName = data["requester_name"] ?: "Someone"

        val intent = Intent(this, FriendshipActivity::class.java)
            .putExtra(Constants.EXTRA_FRIENDSHIP_TAB, 1)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)

        val pendingIntent = PendingIntent.getActivity(
            this, "friend_request".hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        showNotification(
            id = "friend_request".hashCode(),
            channel = Constants.CHANNEL_SOCIAL,
            title = "Friend Request",
            body = "$requesterName wants to connect with you",
            pendingIntent = pendingIntent
        )
    }

    private fun handleVoiceTrainedNotification() {
        val intent = Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
        val pendingIntent = PendingIntent.getActivity(
            this, "voice_trained".hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        showNotification(
            id = "voice_trained".hashCode(),
            channel = Constants.CHANNEL_SYSTEM,
            title = "Voice Training Complete",
            body = "Your voice model is ready. Start making translated calls!",
            pendingIntent = pendingIntent
        )
    }

    private fun handleMissedCallNotification(data: Map<String, String>) {
        val intent = Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
        val pendingIntent = PendingIntent.getActivity(
            this, "missed_call".hashCode(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        showNotification(
            id = "missed_call".hashCode(),
            channel = Constants.CHANNEL_CALLS,
            title = "Missed Call",
            body = "You missed a call",
            pendingIntent = pendingIntent
        )
    }

    private fun showNotification(
        id: Int,
        channel: String,
        title: String,
        body: String,
        pendingIntent: PendingIntent
    ) {
        val notification = NotificationCompat.Builder(this, channel)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        getSystemService(NotificationManager::class.java).notify(id, notification)
    }
}
