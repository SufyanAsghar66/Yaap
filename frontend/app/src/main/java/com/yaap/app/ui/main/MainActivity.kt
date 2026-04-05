package com.yaap.app.ui.main

import android.content.Intent
import android.os.Bundle
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.yaap.app.R
import com.yaap.app.data.api.WebSocketManager
import com.yaap.app.databinding.ActivityMainBinding
import com.yaap.app.ui.call.CallActivity
import com.yaap.app.ui.chat.ChatActivity
import com.yaap.app.ui.chat.ChatListFragment
import com.yaap.app.ui.friends.FriendshipActivity
import com.yaap.app.ui.settings.SettingsFragment
import com.yaap.app.utils.Constants
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    @Inject lateinit var wsManager: WebSocketManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupViewPager()
        setupBottomNav()
        handleFcmIntent(intent)
        wsManager.connect()
        observePresence()
    }

    private fun setupViewPager() {
        val fragments = listOf(
            { ChatListFragment() as Fragment },
            { androidx.fragment.app.Fragment() }, // Friends placeholder (opened as Activity)
            { SettingsFragment() as Fragment }
        )
        binding.viewPager.adapter = object : FragmentStateAdapter(this) {
            override fun getItemCount() = fragments.size
            override fun createFragment(position: Int) = fragments[position]()
        }
        binding.viewPager.isUserInputEnabled = true
        binding.viewPager.offscreenPageLimit = 2

        binding.viewPager.registerOnPageChangeCallback(object : androidx.viewpager2.widget.ViewPager2.OnPageChangeCallback() {
            override fun onPageSelected(position: Int) {
                binding.bottomNav.selectedItemId = when (position) {
                    0 -> R.id.nav_chat
                    1 -> R.id.nav_friends
                    2 -> R.id.nav_settings
                    else -> R.id.nav_chat
                }
                // Friends opens as a separate Activity
                if (position == 1) {
                    startActivity(Intent(this@MainActivity, FriendshipActivity::class.java))
                    binding.viewPager.setCurrentItem(0, false)
                }
            }
        })
    }

    private fun setupBottomNav() {
        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.nav_chat -> { binding.viewPager.setCurrentItem(0, true); true }
                R.id.nav_friends -> { startActivity(Intent(this, FriendshipActivity::class.java)); true }
                R.id.nav_settings -> { binding.viewPager.setCurrentItem(2, true); true }
                else -> false
            }
        }
    }

    private fun handleFcmIntent(intent: Intent?) {
        intent ?: return
        val conversationId = intent.getStringExtra(Constants.EXTRA_CONVERSATION_ID)
        val roomId = intent.getStringExtra(Constants.EXTRA_ROOM_ID)
        when {
            conversationId != null -> startActivity(
                Intent(this, ChatActivity::class.java).putExtra(Constants.EXTRA_CONVERSATION_ID, conversationId)
            )
            roomId != null -> startActivity(
                Intent(this, CallActivity::class.java)
                    .putExtra(Constants.EXTRA_ROOM_ID, roomId)
                    .putExtra(Constants.EXTRA_IS_INCOMING, true)
            )
        }
    }

    private fun observePresence() {
        lifecycleScope.launch {
            wsManager.presenceEvents.collect { json ->
                // Dispatch presence updates to child fragments via shared ViewModel if needed
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleFcmIntent(intent)
    }

    override fun onDestroy() {
        super.onDestroy()
        // Keep WS alive for background notifications; disconnect on explicit logout
    }
}
