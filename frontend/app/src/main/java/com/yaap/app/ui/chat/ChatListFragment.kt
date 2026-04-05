package com.yaap.app.ui.chat

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.ViewModel
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.yaap.app.data.local.entity.ConversationEntity
import com.yaap.app.data.repository.ChatRepository
import com.yaap.app.databinding.FragmentChatListBinding
import com.yaap.app.databinding.ItemConversationBinding
import com.yaap.app.utils.Constants
import com.yaap.app.utils.Result
import com.yaap.app.utils.getCurrentTimeInTimezone
import com.yaap.app.utils.loadAvatar
import com.yaap.app.utils.toMessageTimestamp
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

// ────────────────────────────────────────────────────────────────────
//  ChatListViewModel
// ────────────────────────────────────────────────────────────────────
@HiltViewModel
class ChatListViewModel @Inject constructor(
    private val repo: ChatRepository
) : ViewModel() {

    val conversations: Flow<List<ConversationEntity>> = repo.observeConversations()

    private val _refreshState = MutableStateFlow<Result<*>>(Result.Idle)
    val refreshState: StateFlow<Result<*>> = _refreshState.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _refreshState.value = Result.Loading
            _refreshState.value = repo.refreshConversations()
        }
    }

    fun startConversation(userId: String, onSuccess: (String) -> Unit) {
        viewModelScope.launch {
            when (val result = repo.startConversation(userId)) {
                is Result.Success -> onSuccess(result.data.id)
                else -> {}
            }
        }
    }
}

// ────────────────────────────────────────────────────────────────────
//  ChatListFragment
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class ChatListFragment : Fragment() {

    private var _binding: FragmentChatListBinding? = null
    private val binding get() = _binding!!
    private val viewModel: ChatListViewModel by viewModels()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, s: Bundle?): View {
        _binding = FragmentChatListBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val adapter = ConversationAdapter { conv ->
            startActivity(
                Intent(requireContext(), ChatActivity::class.java)
                    .putExtra(Constants.EXTRA_CONVERSATION_ID, conv.id)
            )
        }

        binding.rvConversations.layoutManager = LinearLayoutManager(requireContext())
        binding.rvConversations.adapter = adapter

        binding.swipeRefresh.setOnRefreshListener { viewModel.refresh() }

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.conversations.collect { list ->
                adapter.submitList(list)
                binding.emptyState.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
            }
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.refreshState.collect { state ->
                binding.swipeRefresh.isRefreshing = state is Result.Loading
            }
        }
    }

    override fun onDestroyView() { super.onDestroyView(); _binding = null }
}

// ────────────────────────────────────────────────────────────────────
//  ConversationAdapter
// ────────────────────────────────────────────────────────────────────
class ConversationAdapter(
    private val onClick: (ConversationEntity) -> Unit
) : ListAdapter<ConversationEntity, ConversationAdapter.VH>(DIFF) {

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val binding = ItemConversationBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return VH(binding)
    }

    override fun onBindViewHolder(holder: VH, position: Int) = holder.bind(getItem(position), onClick)

    class VH(private val b: ItemConversationBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(item: ConversationEntity, onClick: (ConversationEntity) -> Unit) {
            b.ivAvatar.loadAvatar(item.otherUserAvatar, item.otherUserName.take(1))
            b.tvName.text = item.otherUserName
            b.tvLastMessage.text = item.lastMessageTranslation ?: item.lastMessageContent ?: ""
            b.tvTimestamp.text = item.lastMessageTimestamp?.toMessageTimestamp() ?: ""
            b.tvLocalTime.text = item.otherUserTimezone?.let { getCurrentTimeInTimezone(it) } ?: ""
            b.tvFlag.text = countryToFlag(item.otherUserCountryCode)
            b.onlineIndicator.visibility = if (item.otherUserOnline) View.VISIBLE else View.GONE
            if (item.unreadCount > 0) {
                b.tvUnread.visibility = View.VISIBLE
                b.tvUnread.text = item.unreadCount.toString()
            } else {
                b.tvUnread.visibility = View.GONE
            }
            b.root.setOnClickListener { onClick(item) }
        }

        private fun countryToFlag(code: String?): String {
            if (code.isNullOrLength2Not()) return ""

            val safeCode = code ?: return ""

            return safeCode.uppercase().map { char ->
                char.code - 0x41 + 0x1F1E6
            }.joinToString("") { String(Character.toChars(it)) }
        }

        private fun String?.isNullOrLength2Not() = this == null || this.length != 2
    }

    companion object {
        val DIFF = object : DiffUtil.ItemCallback<ConversationEntity>() {
            override fun areItemsTheSame(a: ConversationEntity, b: ConversationEntity) = a.id == b.id
            override fun areContentsTheSame(a: ConversationEntity, b: ConversationEntity) = a == b
        }
    }
}
