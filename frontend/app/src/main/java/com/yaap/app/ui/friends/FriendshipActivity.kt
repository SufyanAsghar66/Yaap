package com.yaap.app.ui.friends

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import androidx.lifecycle.ViewModel
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.google.android.material.tabs.TabLayoutMediator
import com.yaap.app.R
import com.yaap.app.data.repository.FriendRepository
import com.yaap.app.data.repository.UserRepository
import com.yaap.app.databinding.*
import com.yaap.app.model.FriendRequest
import com.yaap.app.model.Friendship
import com.yaap.app.model.UserSearchResult
import com.yaap.app.utils.*
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import javax.inject.Inject

// ────────────────────────────────────────────────────────────────────
//  FriendshipViewModel (shared)
// ────────────────────────────────────────────────────────────────────
@HiltViewModel
class FriendshipViewModel @Inject constructor(
    private val friendRepo: FriendRepository,
    private val userRepo: UserRepository
) : ViewModel() {

    private val _friends = MutableStateFlow<List<Friendship>>(emptyList())
    val friends: StateFlow<List<Friendship>> = _friends.asStateFlow()

    private val _receivedRequests = MutableStateFlow<List<FriendRequest>>(emptyList())
    val receivedRequests: StateFlow<List<FriendRequest>> = _receivedRequests.asStateFlow()

    private val _searchResults = MutableStateFlow<List<UserSearchResult>>(emptyList())
    val searchResults: StateFlow<List<UserSearchResult>> = _searchResults.asStateFlow()

    private val _event = MutableSharedFlow<String>()
    val event: SharedFlow<String> = _event

    fun loadFriends() = viewModelScope.launch {
        when (val r = friendRepo.getFriends()) {
            is Result.Success -> _friends.value = r.data
            is Result.Error -> _event.emit(r.message)
            else -> {}
        }
    }

    fun loadRequests() = viewModelScope.launch {
        when (val r = friendRepo.getReceivedRequests()) {
            is Result.Success -> _receivedRequests.value = r.data
            is Result.Error -> _event.emit(r.message)
            else -> {}
        }
    }

    fun searchUsers(query: String) = viewModelScope.launch {
        if (query.length < 2) { _searchResults.value = emptyList(); return@launch }
        when (val r = userRepo.searchUsers(query)) {
            is Result.Success -> _searchResults.value = r.data
            else -> {}
        }
    }

    fun acceptRequest(id: String) = viewModelScope.launch {
        when (friendRepo.acceptRequest(id)) {
            is Result.Success -> { loadRequests(); loadFriends() }
            is Result.Error -> _event.emit("Failed to accept request")
            else -> {}
        }
    }

    fun declineRequest(id: String) = viewModelScope.launch {
        friendRepo.declineRequest(id)
        loadRequests()
    }

    fun sendFriendRequest(toUserId: String) = viewModelScope.launch {
        when (friendRepo.sendFriendRequest(toUserId)) {
            is Result.Success -> _event.emit("Friend request sent!")
            is Result.Error -> _event.emit("Failed to send request")
            else -> {}
        }
    }

    fun unfriend(friendshipId: String) = viewModelScope.launch {
        friendRepo.unfriend(friendshipId)
        loadFriends()
    }
}

// ────────────────────────────────────────────────────────────────────
//  FriendshipActivity
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class FriendshipActivity : AppCompatActivity() {

    private lateinit var binding: ActivityFriendshipBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFriendshipBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val tabs = listOf("Friends", "Requests", "Search")
        binding.viewPager.adapter = object : FragmentStateAdapter(this) {
            override fun getItemCount() = 3
            override fun createFragment(position: Int): Fragment = when (position) {
                0 -> FriendsTabFragment()
                1 -> RequestsTabFragment()
                else -> SearchTabFragment()
            }
        }
        TabLayoutMediator(binding.tabLayout, binding.viewPager) { tab, pos -> tab.text = tabs[pos] }.attach()
        binding.btnBack.setOnClickListener { finish() }

        // Open to requested tab if coming from notification
        val startTab = intent.getIntExtra(Constants.EXTRA_FRIENDSHIP_TAB, 0)
        binding.viewPager.setCurrentItem(startTab, false)
    }
}

// ────────────────────────────────────────────────────────────────────
//  FriendsTabFragment
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class FriendsTabFragment : Fragment() {
    private var _binding: FragmentFriendsTabBinding? = null
    private val binding get() = _binding!!
    private val viewModel: FriendshipViewModel by viewModels({ requireActivity() })

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, s: Bundle?) =
        FragmentFriendsTabBinding.inflate(i, c, false).also { _binding = it }.root

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val adapter = FriendAdapter(
            onTap = { friendship ->
                startActivity(android.content.Intent(requireContext(), FriendProfileActivity::class.java)
                    .putExtra(Constants.EXTRA_FRIEND_ID, friendship.friend.id))
            },
            onUnfriend = { friendship -> viewModel.unfriend(friendship.id) }
        )
        binding.rvFriends.layoutManager = LinearLayoutManager(requireContext())
        binding.rvFriends.adapter = adapter

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.friends.collect { list ->
                adapter.submitList(list)
                binding.emptyState.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
            }
        }
        viewModel.loadFriends()
    }

    override fun onDestroyView() { super.onDestroyView(); _binding = null }
}

// ────────────────────────────────────────────────────────────────────
//  RequestsTabFragment
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class RequestsTabFragment : Fragment() {
    private var _binding: FragmentRequestsTabBinding? = null
    private val binding get() = _binding!!
    private val viewModel: FriendshipViewModel by viewModels({ requireActivity() })

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, s: Bundle?) =
        FragmentRequestsTabBinding.inflate(i, c, false).also { _binding = it }.root

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val adapter = RequestAdapter(
            onAccept = { req -> viewModel.acceptRequest(req.id) },
            onDecline = { req -> viewModel.declineRequest(req.id) }
        )
        binding.rvRequests.layoutManager = LinearLayoutManager(requireContext())
        binding.rvRequests.adapter = adapter

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.receivedRequests.collect { list ->
                adapter.submitList(list)
                binding.emptyState.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
            }
        }
        viewModel.loadRequests()
    }

    override fun onDestroyView() { super.onDestroyView(); _binding = null }
}

// ────────────────────────────────────────────────────────────────────
//  SearchTabFragment
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class SearchTabFragment : Fragment() {
    private var _binding: FragmentSearchTabBinding? = null
    private val binding get() = _binding!!
    private val viewModel: FriendshipViewModel by viewModels({ requireActivity() })
    private val queryFlow = MutableStateFlow("")

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, s: Bundle?) =
        FragmentSearchTabBinding.inflate(i, c, false).also { _binding = it }.root

    @OptIn(FlowPreview::class)
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        val adapter = SearchResultAdapter { result ->
            if (result.friendshipStatus == "none") viewModel.sendFriendRequest(result.id)
        }
        binding.rvResults.layoutManager = LinearLayoutManager(requireContext())
        binding.rvResults.adapter = adapter

        binding.etSearch.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { queryFlow.value = s.toString() }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })

        viewLifecycleOwner.lifecycleScope.launch {
            queryFlow.debounce(Constants.SEARCH_DEBOUNCE_MS).collect { q -> viewModel.searchUsers(q) }
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.searchResults.collect { list -> adapter.submitList(list) }
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.event.collect { msg ->
                com.google.android.material.snackbar.Snackbar.make(binding.root, msg, com.google.android.material.snackbar.Snackbar.LENGTH_SHORT).show()
            }
        }
    }

    override fun onDestroyView() { super.onDestroyView(); _binding = null }
}

// ────────────────────────────────────────────────────────────────────
//  Adapters
// ────────────────────────────────────────────────────────────────────
class FriendAdapter(
    private val onTap: (Friendship) -> Unit,
    private val onUnfriend: (Friendship) -> Unit
) : ListAdapter<Friendship, FriendAdapter.VH>(object : DiffUtil.ItemCallback<Friendship>() {
    override fun areItemsTheSame(a: Friendship, b: Friendship) = a.id == b.id
    override fun areContentsTheSame(a: Friendship, b: Friendship) = a == b
}) {
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(ItemFriendBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) = holder.bind(getItem(position), onTap, onUnfriend)

    class VH(private val b: ItemFriendBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(item: Friendship, onTap: (Friendship) -> Unit, onUnfriend: (Friendship) -> Unit) {
            b.ivAvatar.loadAvatar(item.friend.avatarUrl, item.friend.displayName.take(1))
            b.tvName.text = item.friend.displayName
            b.tvLocalTime.text = item.friend.timezone?.let { getCurrentTimeInTimezone(it) } ?: ""
            b.onlineIndicator.visibility = if (item.friend.isOnline) View.VISIBLE else View.GONE
            b.root.setOnClickListener { onTap(item) }
            b.btnUnfriend.setOnClickListener { onUnfriend(item) }
        }
    }
}

class RequestAdapter(
    private val onAccept: (FriendRequest) -> Unit,
    private val onDecline: (FriendRequest) -> Unit
) : ListAdapter<FriendRequest, RequestAdapter.VH>(object : DiffUtil.ItemCallback<FriendRequest>() {
    override fun areItemsTheSame(a: FriendRequest, b: FriendRequest) = a.id == b.id
    override fun areContentsTheSame(a: FriendRequest, b: FriendRequest) = a == b
}) {
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(ItemRequestBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) = holder.bind(getItem(position), onAccept, onDecline)

    class VH(private val b: ItemRequestBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(item: FriendRequest, onAccept: (FriendRequest) -> Unit, onDecline: (FriendRequest) -> Unit) {
            b.ivAvatar.loadAvatar(item.fromUser.avatarUrl, item.fromUser.displayName.take(1))
            b.tvName.text = item.fromUser.displayName
            b.tvMessage.text = item.message ?: ""
            b.tvMessage.visibility = if (item.message.isNullOrBlank()) View.GONE else View.VISIBLE
            b.btnAccept.setOnClickListener { onAccept(item) }
            b.btnDecline.setOnClickListener { onDecline(item) }
        }
    }
}

class SearchResultAdapter(
    private val onAction: (UserSearchResult) -> Unit
) : ListAdapter<UserSearchResult, SearchResultAdapter.VH>(object : DiffUtil.ItemCallback<UserSearchResult>() {
    override fun areItemsTheSame(a: UserSearchResult, b: UserSearchResult) = a.id == b.id
    override fun areContentsTheSame(a: UserSearchResult, b: UserSearchResult) = a == b
}) {
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) =
        VH(ItemSearchResultBinding.inflate(LayoutInflater.from(parent.context), parent, false))

    override fun onBindViewHolder(holder: VH, position: Int) = holder.bind(getItem(position), onAction)

    class VH(private val b: ItemSearchResultBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(item: UserSearchResult, onAction: (UserSearchResult) -> Unit) {
            b.ivAvatar.loadAvatar(item.avatarUrl, item.displayName.take(1))
            b.tvName.text = item.displayName
            b.tvMutual.text = if (item.mutualFriends > 0) "${item.mutualFriends} mutual friends" else ""
            val (btnText, enabled) = when (item.friendshipStatus) {
                "requested" -> "Requested" to false
                "friends" -> "Friends" to false
                else -> "Add Friend" to true
            }
            b.btnAdd.text = btnText
            b.btnAdd.isEnabled = enabled
            b.btnAdd.setOnClickListener { if (enabled) onAction(item) }
        }
    }
}
