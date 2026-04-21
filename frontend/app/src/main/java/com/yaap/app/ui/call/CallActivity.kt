package com.yaap.app.ui.call

import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.os.Bundle
import android.util.Base64
import android.view.View
import android.view.WindowManager
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import com.google.android.material.snackbar.Snackbar
import com.yaap.app.data.repository.CallRepository
import com.yaap.app.databinding.ActivityCallBinding
import com.yaap.app.utils.Constants
import com.yaap.app.utils.Result
import com.yaap.app.utils.TokenManager
import com.yaap.app.utils.loadAvatar
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import javax.inject.Inject

// ── Call States ──────────────────────────────────────────────────────
sealed class CallState {
    object Idle : CallState()
    object Ringing : CallState()
    object Incoming : CallState()
    object Connecting : CallState()
    object Active : CallState()
    data class Ended(val reason: String) : CallState()
    data class Error(val message: String) : CallState()
}

// ── ViewModel ────────────────────────────────────────────────────────
@HiltViewModel
class CallViewModel @Inject constructor(
    private val repo: CallRepository,
    private val tokenManager: TokenManager,
    private val okHttpClient: OkHttpClient
) : ViewModel() {

    private val _callState = MutableStateFlow<CallState>(CallState.Idle)
    val callState: StateFlow<CallState> = _callState.asStateFlow()

    private val _transcript = MutableStateFlow("")
    val transcript: StateFlow<String> = _transcript.asStateFlow()

    private val _translation = MutableStateFlow("")
    val translation: StateFlow<String> = _translation.asStateFlow()

    private val _duration = MutableStateFlow(0L)
    val duration: StateFlow<Long> = _duration.asStateFlow()

    var roomId: String = ""
        private set

    private var signalingWs: WebSocket? = null
    private var translationWs: WebSocket? = null
    private var audioRecord: AudioRecord? = null
    private var audioTrack: AudioTrack? = null
    private var recordingJob: Job? = null
    private var durationJob: Job? = null
    private var timeoutJob: Job? = null
    private var isMuted = false

    // ── Outgoing ─────────────────────────────────────────────────────
    fun initiateCall(calleeId: String) {
        viewModelScope.launch {
            _callState.value = CallState.Ringing
            when (val r = repo.initiateCall(calleeId)) {
                is Result.Success -> {
                    roomId = r.data.room["id"] as? String ?: r.data.room["room_id"] as? String ?: ""
                    connectSignaling(roomId, isCaller = true)
                }
                is Result.Error -> _callState.value = CallState.Error(r.message)
                else -> {}
            }
            timeoutJob = launch {
                delay(Constants.CALL_TIMEOUT_MS)
                if (_callState.value is CallState.Ringing) {
                    signalingWs?.send("""{"type":"call_missed","payload":{}}""")
                    _callState.value = CallState.Ended("No answer")
                }
            }
        }
    }

    // ── Incoming ─────────────────────────────────────────────────────
    fun prepareIncoming(room: String) {
        roomId = room
        _callState.value = CallState.Incoming
    }

    fun acceptIncoming() {
        viewModelScope.launch { connectSignaling(roomId, isCaller = false) }
    }

    fun declineIncoming() {
        viewModelScope.launch {
            repo.declineCall(roomId)
            signalingWs?.send("""{"type":"call_decline","payload":{}}""")
            _callState.value = CallState.Ended("Declined")
        }
    }

    // ── Signaling ────────────────────────────────────────────────────
    private fun connectSignaling(room: String, isCaller: Boolean) {
        val token = tokenManager.getAccessToken() ?: return
        val url = "${Constants.WS_BASE_URL}/ws/calls/$room/?token=$token"
        signalingWs = okHttpClient.newWebSocket(
            Request.Builder().url(url).build(),
            object : WebSocketListener() {
                override fun onOpen(ws: WebSocket, response: Response) {
                    // WebRTC peer connection setup goes here once AAR is added
                }
                override fun onMessage(ws: WebSocket, text: String) {
                    handleSignalingMessage(JSONObject(text))
                }
                override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                    _callState.value = CallState.Error("Signaling connection lost")
                }
            }
        )
    }

    private fun handleSignalingMessage(json: JSONObject) {
        when (json.optString("type")) {
            "signaling.declined" -> {
                timeoutJob?.cancel()
                _callState.value = CallState.Ended("Call declined")
            }
            "signaling.peer_left", "signaling.ended" -> {
                _callState.value = CallState.Ended("Call ended")
            }
            "signaling.answer" -> {
                timeoutJob?.cancel()
                _callState.value = CallState.Active
                startDurationTimer()
                startTranslationPipeline()
            }
            "signaling.offer" -> {
                _callState.value = CallState.Active
                startDurationTimer()
                startTranslationPipeline()
            }
            "transcript" -> _transcript.value = json.optString("text")
            "translation" -> _translation.value = json.optString("text")
        }
    }

    // ── Translation pipeline ─────────────────────────────────────────
    private fun startTranslationPipeline() {
        val token = tokenManager.getAccessToken() ?: return
        val url = "${Constants.WS_BASE_URL}/ws/translate/$roomId/caller_audio/?token=$token"
        translationWs = okHttpClient.newWebSocket(
            Request.Builder().url(url).build(),
            object : WebSocketListener() {
                override fun onOpen(ws: WebSocket, response: Response) {
                    startAudioStreaming()
                }
                override fun onMessage(ws: WebSocket, text: String) {
                    handleTranslationMessage(JSONObject(text))
                }
            }
        )
    }

    @android.annotation.SuppressLint("MissingPermission")
    private fun startAudioStreaming() {
        val bufferSize = maxOf(
            AudioRecord.getMinBufferSize(
                Constants.AUDIO_SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            ),
            Constants.AUDIO_FRAME_SIZE
        )
        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            Constants.AUDIO_SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize
        ).also { it.startRecording() }

        recordingJob = viewModelScope.launch(Dispatchers.IO) {
            val buffer = ByteArray(Constants.AUDIO_FRAME_SIZE)
            while (isActive && _callState.value is CallState.Active) {
                val read = audioRecord?.read(buffer, 0, Constants.AUDIO_FRAME_SIZE) ?: break
                if (read > 0 && !isMuted) {
                    translationWs?.send(buffer.copyOf(read).toByteString())
                }
            }
        }
    }

    private fun handleTranslationMessage(json: JSONObject) {
        when (json.optString("type")) {
            "translated_audio" -> {
                val audioB64 = json.optString("audio_b64")
                if (audioB64.isNotBlank()) playTranslatedAudio(audioB64)
                _translation.value = json.optString("target_text")
            }
            "transcript" -> _transcript.value = json.optString("text")
            "translation" -> _translation.value = json.optString("text")
        }
    }

    private fun playTranslatedAudio(base64Audio: String) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val bytes = Base64.decode(base64Audio, Base64.DEFAULT)
                val pcm = if (bytes.size > 44) bytes.drop(44).toByteArray() else bytes
                if (audioTrack == null) {
                    val minBuf = AudioTrack.getMinBufferSize(
                        Constants.AUDIO_SAMPLE_RATE,
                        AudioFormat.CHANNEL_OUT_MONO,
                        AudioFormat.ENCODING_PCM_16BIT
                    )
                    audioTrack = AudioTrack(
                        AudioManager.STREAM_VOICE_CALL,
                        Constants.AUDIO_SAMPLE_RATE,
                        AudioFormat.CHANNEL_OUT_MONO,
                        AudioFormat.ENCODING_PCM_16BIT,
                        minBuf,
                        AudioTrack.MODE_STREAM
                    ).also { it.play() }
                }
                audioTrack?.write(pcm, 0, pcm.size)
            } catch (e: Exception) { /* ignore */ }
        }
    }

    // ── Controls ─────────────────────────────────────────────────────
    fun toggleMute() { isMuted = !isMuted }

    fun endCall() {
        viewModelScope.launch {
            signalingWs?.send("""{"type":"call_end","payload":{}}""")
            repo.endCall(roomId)
            cleanup()
            _callState.value = CallState.Ended("Call ended")
        }
    }

    private fun startDurationTimer() {
        durationJob = viewModelScope.launch {
            while (_callState.value is CallState.Active) {
                delay(1000)
                _duration.value++
            }
        }
    }

    private fun cleanup() {
        recordingJob?.cancel()
        durationJob?.cancel()
        timeoutJob?.cancel()
        audioRecord?.stop(); audioRecord?.release(); audioRecord = null
        audioTrack?.stop(); audioTrack?.release(); audioTrack = null
        signalingWs?.close(1000, "Call ended"); signalingWs = null
        translationWs?.close(1000, "Call ended"); translationWs = null
    }

    override fun onCleared() { cleanup(); super.onCleared() }
}

// ── Activity ─────────────────────────────────────────────────────────
@AndroidEntryPoint
class CallActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCallBinding
    private val viewModel: CallViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCallBinding.inflate(layoutInflater)
        setContentView(binding.root)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val roomId      = intent.getStringExtra(Constants.EXTRA_ROOM_ID)
        val friendId    = intent.getStringExtra(Constants.EXTRA_FRIEND_ID)
        val isIncoming  = intent.getBooleanExtra(Constants.EXTRA_IS_INCOMING, false)
        val callerName  = intent.getStringExtra(Constants.EXTRA_CALLER_NAME) ?: ""
        val callerAvatar = intent.getStringExtra(Constants.EXTRA_CALLER_AVATAR)

        if (isIncoming && roomId != null) {
            binding.tvCallerName.text = callerName
            binding.ivCallerAvatar.loadAvatar(callerAvatar, callerName.take(1))
            viewModel.prepareIncoming(roomId)
        } else if (friendId != null) {
            viewModel.initiateCall(friendId)
        }

        setupControls()
        observeState()
    }

    private fun setupControls() {
        binding.btnEndCall.setOnClickListener { viewModel.endCall() }
        binding.btnAccept.setOnClickListener  { viewModel.acceptIncoming() }
        binding.btnDecline.setOnClickListener { viewModel.declineIncoming() }
        binding.btnMute.setOnClickListener {
            viewModel.toggleMute()
            binding.btnMute.alpha = if (binding.btnMute.alpha == 1f) 0.5f else 1f
        }
        binding.btnSpeaker.setOnClickListener {
            val am = getSystemService(AudioManager::class.java)
            am.isSpeakerphoneOn = !am.isSpeakerphoneOn
            binding.btnSpeaker.alpha = if (am.isSpeakerphoneOn) 1f else 0.5f
        }
    }

    private fun observeState() {
        lifecycleScope.launch {
            viewModel.callState.collect { state ->
                when (state) {
                    is CallState.Idle       -> {}
                    is CallState.Ringing    -> {
                        binding.tvStatus.text = "Ringing…"
                        binding.incomingControls.visibility = View.GONE
                        binding.activeControls.visibility   = View.GONE
                        binding.outgoingControls.visibility = View.VISIBLE
                    }
                    is CallState.Incoming   -> {
                        binding.tvStatus.text = "Incoming call…"
                        binding.incomingControls.visibility = View.VISIBLE
                        binding.outgoingControls.visibility = View.GONE
                        binding.activeControls.visibility   = View.GONE
                    }
                    is CallState.Connecting -> binding.tvStatus.text = "Connecting…"
                    is CallState.Active     -> {
                        binding.tvStatus.text = "Connected"
                        binding.incomingControls.visibility = View.GONE
                        binding.outgoingControls.visibility = View.GONE
                        binding.activeControls.visibility   = View.VISIBLE
                        binding.translationCard.visibility  = View.VISIBLE
                    }
                    is CallState.Ended      -> showEndedAndFinish(state.reason)
                    is CallState.Error      -> {
                        binding.tvStatus.text = state.message
                        Snackbar.make(binding.root, state.message, Snackbar.LENGTH_LONG).show()
                        finishAfterDelay()
                    }
                }
            }
        }
        lifecycleScope.launch {
            viewModel.duration.collect { secs ->
                binding.tvDuration.text = String.format("%02d:%02d", secs / 60, secs % 60)
            }
        }
        lifecycleScope.launch {
            viewModel.transcript.collect { text ->
                if (text.isNotBlank()) {
                    binding.tvTranscript.text = text
                    binding.tvTranscript.animate().alpha(1f).setDuration(300).start()
                }
            }
        }
        lifecycleScope.launch {
            viewModel.translation.collect { text ->
                if (text.isNotBlank()) {
                    binding.tvTranslation.text = text
                    binding.tvTranslation.animate().alpha(1f).setDuration(300).start()
                }
            }
        }
    }

    private fun showEndedAndFinish(reason: String) {
        Snackbar.make(binding.root, reason, Snackbar.LENGTH_SHORT).show()
        finishAfterDelay()
    }

    private fun finishAfterDelay() {
        lifecycleScope.launch { delay(1500); finish() }
    }
}