package com.yaap.app.ui.chat

import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.yaap.app.data.api.ChatWebSocket
import com.yaap.app.data.local.entity.MessageEntity
import com.yaap.app.data.repository.ChatRepository
import com.yaap.app.databinding.ActivityChatBinding
import com.yaap.app.databinding.ItemMessageReceivedBinding
import com.yaap.app.databinding.ItemMessageSentBinding
import com.yaap.app.utils.Constants
import com.yaap.app.utils.Result
import com.yaap.app.utils.TokenManager
import com.yaap.app.utils.toMessageTimestamp
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.json.JSONArray
import org.json.JSONObject
import javax.inject.Inject

private const val TAG = "ChatActivity"

// ────────────────────────────────────────────────────────────────────
//  ChatActivityViewModel
// ────────────────────────────────────────────────────────────────────
class ChatActivityViewModel(
    private val repo: ChatRepository,
    private val tokenManager: TokenManager,
    private val conversationId: String,
    private val okHttpClient: okhttp3.OkHttpClient
) : ViewModel() {

    val messages: Flow<List<MessageEntity>> = repo.observeMessages(conversationId)

    private val _wsEvents = MutableSharedFlow<JSONObject>(replay = 0, extraBufferCapacity = 64)
    val wsEvents: SharedFlow<JSONObject> = _wsEvents

    private var chatWs: ChatWebSocket? = null
    private var typingJob: Job? = null
    var nextCursor: String? = null

    fun connectWebSocket() {
        val token = tokenManager.getAccessToken() ?: return
        chatWs = ChatWebSocket(okHttpClient, conversationId, token).also {
            it.connect()
            viewModelScope.launch {
                it.messages.collect { json -> _wsEvents.emit(json) }
            }
        }
    }

    fun sendMessage(content: String) {
        if (content.isBlank()) return
        chatWs?.sendMessage(content)
    }

    fun notifyTypingStart() {
        chatWs?.sendTypingStart()
        typingJob?.cancel()
        typingJob = viewModelScope.launch {
            delay(Constants.TYPING_STOP_DELAY_MS)
            chatWs?.sendTypingStop()
        }
    }

    fun markRead(messageId: String) = chatWs?.sendMarkRead(messageId)

    fun deleteMessage(messageId: String, forEveryone: Boolean) =
        chatWs?.sendDeleteMessage(messageId, if (forEveryone) "everyone" else "me")

    fun loadMoreHistory() {
        val cursor = nextCursor ?: return
        chatWs?.loadHistory(cursor)
    }

    fun translateMessage(messageId: String, language: String) {
        viewModelScope.launch { repo.translateMessage(messageId, language) }
    }

    fun disconnectWebSocket() {
        chatWs?.disconnect()
        chatWs = null
    }

    // ── Real-time persistence helpers ─────────────────────────────────

    /** Insert a single message from a WebSocket event into Room DB */
    fun insertMessage(entity: MessageEntity) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                repo.insertMessage(entity)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to insert message: ${e.message}")
            }
        }
    }

    /** Batch insert messages from history load into Room DB */
    fun insertMessages(entities: List<MessageEntity>) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                repo.insertMessages(entities)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to insert messages: ${e.message}")
            }
        }
    }

    /** Update translation for a message (called when backend pushes translated content) */
    fun updateTranslation(messageId: String, translation: String) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                repo.updateMessageTranslation(messageId, translation)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to update translation: ${e.message}")
            }
        }
    }

    /** Mark a message as deleted in Room DB */
    fun markMessageDeleted(messageId: String) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                repo.markMessageDeleted(messageId)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to mark deleted: ${e.message}")
            }
        }
    }

    /** Update message status (e.g. read receipt) */
    fun updateMessageStatus(messageId: String, status: String) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                repo.updateMessageStatus(messageId, status)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to update status: ${e.message}")
            }
        }
    }

    override fun onCleared() {
        disconnectWebSocket()
        super.onCleared()
    }
}

// ────────────────────────────────────────────────────────────────────
//  ChatActivity
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class ChatActivity : AppCompatActivity() {

    private lateinit var binding: ActivityChatBinding

    @Inject lateinit var repo: ChatRepository
    @Inject lateinit var tokenManager: TokenManager
    @Inject lateinit var okHttpClient: okhttp3.OkHttpClient

    private lateinit var viewModel: ChatActivityViewModel
    private lateinit var adapter: MessageAdapter
    private var currentUserId: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityChatBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val conversationId = intent.getStringExtra(Constants.EXTRA_CONVERSATION_ID) ?: run { finish(); return }
        currentUserId = tokenManager.decodeJwtClaims()?.userId ?: ""

        viewModel = ViewModelProvider(this, object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>) =
                ChatActivityViewModel(repo, tokenManager, conversationId, okHttpClient) as T
        })[ChatActivityViewModel::class.java]

        setupRecyclerView()
        setupInputBar()
        setupToolbar()
        observeState()

        viewModel.connectWebSocket()
    }

    private fun setupRecyclerView() {
        adapter = MessageAdapter(currentUserId)
        val layoutManager = LinearLayoutManager(this).apply { stackFromEnd = true }
        binding.rvMessages.layoutManager = layoutManager
        binding.rvMessages.adapter = adapter

        binding.rvMessages.addOnScrollListener(object : RecyclerView.OnScrollListener() {
            override fun onScrolled(rv: RecyclerView, dx: Int, dy: Int) {
                if (!rv.canScrollVertically(-1)) viewModel.loadMoreHistory()
            }
        })
    }

    private fun setupInputBar() {
        binding.etMessage.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                binding.btnSend.isEnabled = !s.isNullOrBlank()
                if (!s.isNullOrBlank()) viewModel.notifyTypingStart()
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
        binding.btnSend.setOnClickListener {
            val text = binding.etMessage.text.toString().trim()
            if (text.isNotEmpty()) {
                viewModel.sendMessage(text)
                binding.etMessage.setText("")
            }
        }
    }

    private fun setupToolbar() {
        binding.btnBack.setOnClickListener { finish() }
        binding.btnCall.setOnClickListener {
            startActivity(Intent(this, com.yaap.app.ui.call.CallActivity::class.java))
        }
    }

    private fun observeState() {
        // Observe Room DB — reactive list that auto-updates when messages are inserted/updated
        lifecycleScope.launch {
            viewModel.messages.collect { messages ->
                adapter.submitList(messages.reversed())
                if (messages.isNotEmpty()) binding.rvMessages.scrollToPosition(messages.size - 1)
            }
        }

        // Process WebSocket events and persist to Room DB
        lifecycleScope.launch {
            viewModel.wsEvents.collect { json ->
                handleWebSocketEvent(json)
            }
        }
    }

    /**
     * Central handler for all WebSocket events.
     * Parses the JSON payload and persists changes into Room DB,
     * which triggers the reactive Flow to update the UI automatically.
     */
    private fun handleWebSocketEvent(json: JSONObject) {
        val type = json.optString("type")
        val payload = json.optJSONObject("payload")

        Log.d(TAG, "WS event: $type")

        when (type) {
            "chat.message_new" -> {
                // Parse the new message and insert into Room DB
                if (payload != null) {
                    val entity = parseMessagePayload(payload)
                    if (entity != null) {
                        viewModel.insertMessage(entity)
                        // Auto-mark as read if the message is from the other user
                        if (entity.senderId != currentUserId) {
                            viewModel.markRead(entity.id)
                        }
                    }
                }
                binding.typingIndicator.visibility = View.GONE
            }

            "chat.history" -> {
                // Parse the messages array and insert all into Room DB
                if (payload != null) {
                    val messagesArray = payload.optJSONArray("messages")
                    if (messagesArray != null) {
                        val entities = parseMessageArray(messagesArray)
                        if (entities.isNotEmpty()) {
                            viewModel.insertMessages(entities)
                        }
                    }
                    val cursor = payload.optString("next_cursor").takeIf {
                        it.isNotBlank() && it != "null"
                    }
                    viewModel.nextCursor = cursor
                }
            }

            "chat.message_translated" -> {
                // Real-time translation pushed by backend after Celery task completes
                if (payload != null) {
                    val messageId = payload.optString("message_id")
                    val translatedContent = payload.optString("translated_content")
                    if (messageId.isNotBlank() && translatedContent.isNotBlank()) {
                        viewModel.updateTranslation(messageId, translatedContent)
                    }
                }
            }

            "chat.message_deleted" -> {
                if (payload != null) {
                    val messageId = payload.optString("message_id")
                    if (messageId.isNotBlank()) {
                        viewModel.markMessageDeleted(messageId)
                    }
                }
            }

            "chat.read_receipt" -> {
                if (payload != null) {
                    val messageId = payload.optString("message_id")
                    if (messageId.isNotBlank()) {
                        viewModel.updateMessageStatus(messageId, "read")
                    }
                }
            }

            "chat.typing_start" -> {
                binding.typingIndicator.visibility = View.VISIBLE
            }

            "chat.typing_stop" -> {
                binding.typingIndicator.visibility = View.GONE
            }

            "error" -> {
                val code = payload?.optString("code") ?: "UNKNOWN"
                val message = payload?.optString("message") ?: "Unknown error"
                Log.e(TAG, "WS error: $code — $message")
            }
        }
    }

    /**
     * Parse a single message JSON object (from chat.message_new) into a MessageEntity.
     * Backend payload shape:
     *   {"id":"...", "conversation_id":"...", "sender":{"id":"...","display_name":"..."},
     *    "content":"...", "original_language":"...", "status":"...",
     *    "deleted_for_everyone":false, "created_at":"...", "updated_at":"..."}
     */
    private fun parseMessagePayload(msg: JSONObject): MessageEntity? {
        return try {
            val senderId = msg.optJSONObject("sender")?.optString("id")
                ?: msg.optString("sender_id")
            MessageEntity(
                id = msg.getString("id"),
                conversationId = msg.getString("conversation_id"),
                senderId = senderId,
                content = msg.optString("content", ""),
                translation = null,
                status = msg.optString("status", "sent"),
                createdAt = msg.getString("created_at"),
                deleted = msg.optBoolean("deleted_for_everyone", false)
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse message payload: ${e.message}")
            null
        }
    }

    /** Parse an array of message JSON objects (from chat.history) into MessageEntity list. */
    private fun parseMessageArray(array: JSONArray): List<MessageEntity> {
        val entities = mutableListOf<MessageEntity>()
        for (i in 0 until array.length()) {
            val msg = array.optJSONObject(i) ?: continue
            parseMessagePayload(msg)?.let { entities.add(it) }
        }
        return entities
    }

    override fun onDestroy() {
        viewModel.disconnectWebSocket()
        super.onDestroy()
    }
}

// ────────────────────────────────────────────────────────────────────
//  MessageAdapter - two ViewHolder types (sent / received)
// ────────────────────────────────────────────────────────────────────
class MessageAdapter(private val currentUserId: String) :
    ListAdapter<MessageEntity, RecyclerView.ViewHolder>(MSG_DIFF) {

    private val VIEW_SENT = 1
    private val VIEW_RECEIVED = 2

    override fun getItemViewType(position: Int) =
        if (getItem(position).senderId == currentUserId) VIEW_SENT else VIEW_RECEIVED

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
        val inflater = LayoutInflater.from(parent.context)
        return if (viewType == VIEW_SENT) {
            SentVH(ItemMessageSentBinding.inflate(inflater, parent, false))
        } else {
            ReceivedVH(ItemMessageReceivedBinding.inflate(inflater, parent, false))
        }
    }

    override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
        val item = getItem(position)
        when (holder) {
            is SentVH -> holder.bind(item)
            is ReceivedVH -> holder.bind(item)
        }
    }

    class SentVH(private val b: ItemMessageSentBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(msg: MessageEntity) {
            b.tvContent.text = if (msg.deleted) "This message was deleted." else msg.content
            b.tvTimestamp.text = msg.createdAt.toMessageTimestamp()
            b.tvContent.alpha = if (msg.deleted) 0.5f else 1f
            b.root.setOnLongClickListener {
                // TODO: show context menu (Copy / Delete for me / Delete for everyone)
                true
            }
        }
    }

    class ReceivedVH(private val b: ItemMessageReceivedBinding) : RecyclerView.ViewHolder(b.root) {
        fun bind(msg: MessageEntity) {
            b.tvContent.text = if (msg.deleted) "This message was deleted." else
                (msg.translation ?: msg.content)
            b.tvTimestamp.text = msg.createdAt.toMessageTimestamp()
            b.tvContent.alpha = if (msg.deleted) 0.5f else 1f
            b.tvOriginal.visibility = if (msg.translation != null) View.VISIBLE else View.GONE
            b.tvOriginal.setOnClickListener {
                android.app.AlertDialog.Builder(b.root.context)
                    .setTitle("Original message")
                    .setMessage(msg.content)
                    .setPositiveButton("Close", null)
                    .show()
            }
        }
    }

    companion object {
        val MSG_DIFF = object : DiffUtil.ItemCallback<MessageEntity>() {
            override fun areItemsTheSame(a: MessageEntity, b: MessageEntity) = a.id == b.id
            override fun areContentsTheSame(a: MessageEntity, b: MessageEntity) = a == b
        }
    }
}
