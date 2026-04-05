package com.yaap.app.ui.splash

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.yaap.app.R
import com.yaap.app.ui.auth.AuthActivity
import com.yaap.app.ui.main.MainActivity
import com.yaap.app.ui.onboarding.LanguageSelectionActivity
import com.yaap.app.ui.onboarding.PersonalDetailsActivity
import com.yaap.app.ui.onboarding.VoiceTrainingActivity
import com.yaap.app.utils.Constants
import com.yaap.app.utils.TokenManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import javax.inject.Inject

@SuppressLint("CustomSplashScreen")
@AndroidEntryPoint
class SplashActivity : AppCompatActivity() {

    @Inject lateinit var tokenManager: TokenManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash)

        lifecycleScope.launch {
            delay(500) // 500ms logo display
            route()
        }
    }

    private fun route() {
        if (!tokenManager.hasValidToken()) {
            goTo(AuthActivity::class.java)
            return
        }

        val claims = tokenManager.decodeJwtClaims()
        val destination = when (claims?.nextStep) {
            Constants.STEP_PERSONAL_DETAILS -> PersonalDetailsActivity::class.java
            Constants.STEP_LANGUAGE_SELECTION -> LanguageSelectionActivity::class.java
            Constants.STEP_VOICE_TRAINING -> VoiceTrainingActivity::class.java
            else -> MainActivity::class.java
        }
        goTo(destination)
    }

    private fun <T> goTo(cls: Class<T>) {
        startActivity(
            Intent(this, cls).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            }
        )
        finish()
    }
}
