package com.yaap.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import com.yaap.app.utils.Constants
import dagger.hilt.android.HiltAndroidApp
import org.webrtc.PeerConnectionFactory

@HiltAndroidApp
class YaapApplication : Application() {

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        initWebRTC()
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)

            val channels = listOf(
                NotificationChannel(
                    Constants.CHANNEL_MESSAGES,
                    "Messages",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Chat message notifications"
                    enableVibration(true)
                },
                NotificationChannel(
                    Constants.CHANNEL_CALLS,
                    "Calls",
                    NotificationManager.IMPORTANCE_MAX
                ).apply {
                    description = "Incoming call notifications"
                    enableVibration(true)
                },
                NotificationChannel(
                    Constants.CHANNEL_SOCIAL,
                    "Friend Requests",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "Friend request notifications"
                },
                NotificationChannel(
                    Constants.CHANNEL_SYSTEM,
                    "System",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "Voice training and system notifications"
                }
            )

            channels.forEach { manager.createNotificationChannel(it) }
        }
    }

    private fun initWebRTC() {
        PeerConnectionFactory.initialize(
            PeerConnectionFactory.InitializationOptions.builder(this)
                .setEnableInternalTracer(false)
                .createInitializationOptions()
        )
    }
}
