package com.yaap.app.ui.friends

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import com.yaap.app.R
import com.yaap.app.data.repository.ChatRepository
import com.yaap.app.data.repository.FriendRepository
import com.yaap.app.data.repository.UserRepository
import com.yaap.app.databinding.ActivityFriendProfileBinding
import com.yaap.app.model.User
import com.yaap.app.ui.call.CallActivity
import com.yaap.app.ui.chat.ChatActivity
import com.yaap.app.utils.*
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class FriendProfileViewModel @Inject constructor(
    private val userRepo: UserRepository,
    private val friendRepo: FriendRepository,
    private val chatRepo: ChatRepository
) : ViewModel() {
    private val _user = MutableStateFlow<User?>(null)
    val user: StateFlow<User?> = _user.asStateFlow()

    private val _event = MutableSharedFlow<String>()
    val event: SharedFlow<String> = _event

    private val _conversationId = MutableSharedFlow<String>()
    val conversationId: SharedFlow<String> = _conversationId

    fun loadUser(userId: String) = viewModelScope.launch {
        when (val r = userRepo.getUserProfile(userId)) {
            is Result.Success -> _user.value = r.data
            is Result.Error -> _event.emit(r.message)
            else -> {}
        }
    }

    fun openChat(userId: String) = viewModelScope.launch {
        when (val r = chatRepo.startConversation(userId)) {
            is Result.Success -> _conversationId.emit(r.data.id)
            is Result.Error -> _event.emit(r.message)
            else -> {}
        }
    }

    fun blockUser(userId: String) = viewModelScope.launch {
        friendRepo.blockUser(userId)
        _event.emit("User blocked")
    }

    fun unfriend(friendshipId: String) = viewModelScope.launch {
        friendRepo.unfriend(friendshipId)
        _event.emit("Unfriended")
    }
}

@AndroidEntryPoint
class FriendProfileActivity : AppCompatActivity() {

    private lateinit var binding: ActivityFriendProfileBinding
    private val viewModel: FriendProfileViewModel by viewModels()
    private var friendId: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFriendProfileBinding.inflate(layoutInflater)
        setContentView(binding.root)

        friendId = intent.getStringExtra(Constants.EXTRA_FRIEND_ID) ?: run { finish(); return }

        binding.btnBack.setOnClickListener { finish() }
        binding.btnCall.setOnClickListener {
            startActivity(Intent(this, CallActivity::class.java)
                .putExtra(Constants.EXTRA_FRIEND_ID, friendId))
        }
        binding.btnMessage.setOnClickListener { viewModel.openChat(friendId) }

        lifecycleScope.launch {
            viewModel.user.collect { user ->
                user ?: return@collect
                binding.ivAvatar.loadAvatar(user.avatarUrl, user.displayName.take(1))
                binding.tvName.text = user.displayName
                binding.tvBio.text = user.bio ?: ""
                binding.tvBio.visibility = if (user.bio.isNullOrBlank()) View.GONE else View.VISIBLE
                binding.tvLocalTime.text = user.timezone?.let { getCurrentTimeInTimezone(it) } ?: ""
                binding.onlineIndicator.visibility = if (user.isOnline) View.VISIBLE else View.GONE
            }
        }

        lifecycleScope.launch {
            viewModel.conversationId.collect { convId ->
                startActivity(Intent(this@FriendProfileActivity, ChatActivity::class.java)
                    .putExtra(Constants.EXTRA_CONVERSATION_ID, convId))
            }
        }

        lifecycleScope.launch {
            viewModel.event.collect { msg ->
                com.google.android.material.snackbar.Snackbar.make(binding.root, msg, com.google.android.material.snackbar.Snackbar.LENGTH_SHORT).show()
                if (msg == "User blocked" || msg == "Unfriended") finish()
            }
        }

        viewModel.loadUser(friendId)
    }
}
