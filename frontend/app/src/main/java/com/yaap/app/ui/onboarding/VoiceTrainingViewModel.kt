package com.yaap.app.ui.onboarding

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yaap.app.data.repository.VoiceRepository
import com.yaap.app.model.VoiceSentence
import com.yaap.app.utils.Constants
import com.yaap.app.utils.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import javax.inject.Inject

sealed class VoiceTrainingState {
    object Loading : VoiceTrainingState()
    data class Ready(val sentences: List<VoiceSentence>, val currentIndex: Int) : VoiceTrainingState()
    object Recording : VoiceTrainingState()
    data class Recorded(val audioFile: File) : VoiceTrainingState()
    object Uploading : VoiceTrainingState()
    object Training : VoiceTrainingState()
    object Complete : VoiceTrainingState()
    data class Error(val message: String) : VoiceTrainingState()
}

@HiltViewModel
class VoiceTrainingViewModel @Inject constructor(
    private val repo: VoiceRepository
) : ViewModel() {

    private val _state = MutableStateFlow<VoiceTrainingState>(VoiceTrainingState.Loading)
    val state: StateFlow<VoiceTrainingState> = _state.asStateFlow()

    private val _amplitude = MutableStateFlow(0)
    val amplitude: StateFlow<Int> = _amplitude.asStateFlow()

    private val _noiseWarning = MutableSharedFlow<Unit>()
    val noiseWarning: SharedFlow<Unit> = _noiseWarning

    var sentences: List<VoiceSentence> = emptyList()
    var currentIndex = 0
    val uploadedIndices = mutableSetOf<Int>()

    private var audioRecord: AudioRecord? = null
    private var recordingJob: Job? = null
    private var tempAudioFile: File? = null
    private val audioBuffer = ByteArrayOutputStream()

    fun loadSentences() {
        viewModelScope.launch {
            _state.value = VoiceTrainingState.Loading
            when (val result = repo.getSentences()) {
                is Result.Success -> {
                    sentences = result.data.sentences
                    _state.value = VoiceTrainingState.Ready(sentences, currentIndex)
                }
                is Result.Error -> _state.value = VoiceTrainingState.Error(result.message)
                else -> {}
            }
        }
    }

    @android.annotation.SuppressLint("MissingPermission")
    fun startRecording(cacheDir: File) {
        val bufferSize = maxOf(
            AudioRecord.getMinBufferSize(Constants.AUDIO_SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT),
            Constants.AUDIO_FRAME_SIZE
        )
        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            Constants.AUDIO_SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize
        )
        audioBuffer.reset()
        audioRecord?.startRecording()
        _state.value = VoiceTrainingState.Recording

        recordingJob = viewModelScope.launch(Dispatchers.IO) {
            val buffer = ShortArray(Constants.AUDIO_FRAME_SIZE / 2)
            val byteBuffer = ByteBuffer.allocate(Constants.AUDIO_FRAME_SIZE).order(ByteOrder.LITTLE_ENDIAN)
            var elapsed = 0
            while (isActive && elapsed < Constants.MAX_RECORDING_SECONDS * 1000) {
                val read = audioRecord?.read(buffer, 0, buffer.size) ?: break
                if (read > 0) {
                    byteBuffer.clear()
                    for (i in 0 until read) byteBuffer.putShort(buffer[i])
                    audioBuffer.write(byteBuffer.array(), 0, read * 2)
                    val maxAmp = buffer.take(read).maxOrNull()?.toInt() ?: 0
                    _amplitude.value = maxAmp
                    elapsed += (read * 1000 / Constants.AUDIO_SAMPLE_RATE)
                }
            }
            // Auto-stop after max time
            withContext(Dispatchers.Main) { stopRecording(cacheDir) }
        }
    }

    fun stopRecording(cacheDir: File) {
        recordingJob?.cancel()
        audioRecord?.stop()
        audioRecord?.release()
        audioRecord = null
        _amplitude.value = 0

        val pcmData = audioBuffer.toByteArray()
        if (pcmData.size < 16000) { // less than 0.5s
            _state.value = VoiceTrainingState.Error("Recording too short. Please speak the full sentence.")
            _state.value = VoiceTrainingState.Ready(sentences, currentIndex)
            return
        }

        val file = File(cacheDir, "voice_sample_$currentIndex.wav")
        writeWav(file, pcmData)
        tempAudioFile = file
        _state.value = VoiceTrainingState.Recorded(file)
    }

    fun acceptRecording() {
        val file = tempAudioFile ?: return
        val sentence = sentences.getOrNull(currentIndex) ?: return

        viewModelScope.launch {
            _state.value = VoiceTrainingState.Uploading
            val requestBody = file.readBytes().toRequestBody("audio/wav".toMediaType())
            val part = MultipartBody.Part.createFormData("audio", file.name, requestBody)

            when (val result = repo.uploadSample(part, currentIndex, sentence.id)) {
                is Result.Success -> {
                    if (result.data.noiseWarning) _noiseWarning.emit(Unit)
                    uploadedIndices.add(currentIndex)
                    currentIndex++
                    if (currentIndex >= sentences.size) {
                        trainVoice()
                    } else {
                        _state.value = VoiceTrainingState.Ready(sentences, currentIndex)
                    }
                }
                is Result.Error -> {
                    _state.value = VoiceTrainingState.Error(result.message)
                    _state.value = VoiceTrainingState.Ready(sentences, currentIndex)
                }
                else -> {}
            }
        }
    }

    fun reRecord(cacheDir: File) {
        viewModelScope.launch {
            if (uploadedIndices.contains(currentIndex)) {
                repo.deleteSample(currentIndex)
                uploadedIndices.remove(currentIndex)
            }
            tempAudioFile?.delete()
            tempAudioFile = null
            _state.value = VoiceTrainingState.Ready(sentences, currentIndex)
        }
    }

    private fun trainVoice() {
        viewModelScope.launch {
            _state.value = VoiceTrainingState.Training
            repo.trainVoice()
            // Completion is signaled via presence WebSocket (voice.training_update)
            // Poll as fallback
            pollTrainingStatus()
        }
    }

    private suspend fun pollTrainingStatus() {
        repeat(60) { // poll up to 5 minutes
            delay(5000)
            when (val result = repo.getVoiceStatus()) {
                is Result.Success -> {
                    if (result.data.voiceTrained) {
                        _state.value = VoiceTrainingState.Complete
                        return
                    }
                }
                else -> {}
            }
        }
        _state.value = VoiceTrainingState.Error("Training timed out. Please try again.")
    }

    private fun writeWav(file: File, pcmData: ByteArray) {
        val totalDataLen = pcmData.size + 36
        val byteRate = Constants.AUDIO_SAMPLE_RATE * 2
        FileOutputStream(file).use { out ->
            fun writeInt(value: Int) = out.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(value).array())
            fun writeShort(value: Short) = out.write(ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort(value).array())
            out.write("RIFF".toByteArray())
            writeInt(totalDataLen)
            out.write("WAVE".toByteArray())
            out.write("fmt ".toByteArray())
            writeInt(16)
            writeShort(1)  // PCM
            writeShort(1)  // mono
            writeInt(Constants.AUDIO_SAMPLE_RATE)
            writeInt(byteRate)
            writeShort(2)  // block align
            writeShort(16) // bits per sample
            out.write("data".toByteArray())
            writeInt(pcmData.size)
            out.write(pcmData)
        }
    }

    override fun onCleared() {
        audioRecord?.release()
        super.onCleared()
    }
}