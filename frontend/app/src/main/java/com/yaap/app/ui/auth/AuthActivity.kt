package com.yaap.app.ui.auth

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.google.android.material.tabs.TabLayoutMediator
import com.yaap.app.databinding.ActivityAuthBinding
import com.yaap.app.ui.main.MainActivity
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class AuthActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAuthBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAuthBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupViewPager()

        // ── DEV ONLY: skip auth and go straight to MainActivity ──────
        // Uncomment the lines below to bypass login during UI testing.
        // Comment them back out before building for production.
        //
        //binding.root.postDelayed({
         //startActivity(Intent(this, MainActivity::class.java))
            // finish()
         //}, 300)
        // ─────────────────────────────────────────────────────────────
    }

    private fun setupViewPager() {
        val tabs = listOf("Login", "Sign Up")//"OTP"
        val fragments: List<() -> Fragment> = listOf(
            { LoginFragment() },
            { SignUpFragment() }
            //{ OtpFragment() }
        )

        binding.viewPager.adapter = object : FragmentStateAdapter(this) {
            override fun getItemCount() = tabs.size
            override fun createFragment(position: Int) = fragments[position]()
        }

        TabLayoutMediator(binding.tabLayout, binding.viewPager) { tab, position ->
            tab.text = tabs[position]
        }.attach()
    }

    /** Called by child fragments after successful auth to route per next_step */
    fun navigatePerNextStep(nextStep: String) {
        val cls = when (nextStep) {
            "personal_details"   -> com.yaap.app.ui.onboarding.PersonalDetailsActivity::class.java
            "language_selection" -> com.yaap.app.ui.onboarding.LanguageSelectionActivity::class.java
            "voice_training"     -> com.yaap.app.ui.onboarding.VoiceTrainingActivity::class.java
            else                 -> MainActivity::class.java
        }
        startActivity(Intent(this, cls).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        })
        finish()
    }
}