package com.yaap.app.ui.onboarding

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaPlayer
import android.os.Bundle
import android.os.CountDownTimer
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.yaap.app.R
import com.yaap.app.databinding.ActivityVoiceTrainingBinding
import com.yaap.app.ui.main.MainActivity
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@AndroidEntryPoint
class VoiceTrainingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityVoiceTrainingBinding
    private val viewModel: VoiceTrainingViewModel by viewModels()
    private var mediaPlayer: MediaPlayer? = null
    private var amplitudeJob: Job? = null

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startRecording()
        else showPermissionRationaleDialog()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityVoiceTrainingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupClickListeners()
        observeState()
        viewModel.loadSentences()
    }

    private fun setupClickListeners() {
        binding.btnRecord.setOnClickListener { requestRecordPermission() }
        binding.btnStop.setOnClickListener {
            amplitudeJob?.cancel()
            viewModel.stopRecording(cacheDir)
        }
        binding.btnPlay.setOnClickListener { playRecording() }
        binding.btnReRecord.setOnClickListener {
            mediaPlayer?.stop()
            viewModel.reRecord(cacheDir)
        }
        binding.btnAccept.setOnClickListener { viewModel.acceptRecording() }
    }

    private fun observeState() {
        lifecycleScope.launch {
            viewModel.state.collect { state ->
                when (state) {
                    is VoiceTrainingState.Loading -> showLoadingUi()
                    is VoiceTrainingState.Ready -> showReadyUi(state)
                    is VoiceTrainingState.Recording -> showRecordingUi()
                    is VoiceTrainingState.Recorded -> showRecordedUi()
                    is VoiceTrainingState.Uploading -> showUploadingUi()
                    is VoiceTrainingState.Training -> showTrainingUi()
                    is VoiceTrainingState.Complete -> navigateToMain()
                    is VoiceTrainingState.Error -> showError(state.message)
                }
            }
        }

        lifecycleScope.launch {
            viewModel.noiseWarning.collect {
                com.google.android.material.snackbar.Snackbar.make(
                    binding.root,
                    "Background noise detected — try a quieter location",
                    com.google.android.material.snackbar.Snackbar.LENGTH_LONG
                ).show()
            }
        }
    }

    private fun showLoadingUi() {
        binding.progressBar.visibility = View.VISIBLE
        binding.contentGroup.visibility = View.GONE
    }

    private fun showReadyUi(state: VoiceTrainingState.Ready) {
        binding.progressBar.visibility = View.GONE
        binding.contentGroup.visibility = View.VISIBLE
        binding.trainingProgressBar.visibility = View.GONE

        updateStepDots(state.currentIndex)
        val sentence = state.sentences.getOrNull(state.currentIndex)
        binding.tvSentence.text = sentence?.text ?: ""
        binding.tvStepLabel.text = "Step ${state.currentIndex + 1} of ${state.sentences.size}"

        binding.btnRecord.visibility = View.VISIBLE
        binding.btnStop.visibility = View.GONE
        binding.btnPlay.visibility = View.GONE
        binding.btnReRecord.visibility = View.GONE
        binding.btnAccept.visibility = View.GONE
        binding.waveformView.reset()
        binding.uploadProgress.visibility = View.GONE
    }

    private fun showRecordingUi() {
        binding.btnRecord.visibility = View.GONE
        binding.btnStop.visibility = View.VISIBLE
        binding.btnPlay.visibility = View.GONE
        binding.btnReRecord.visibility = View.GONE
        binding.btnAccept.visibility = View.GONE

        // Poll amplitude
        amplitudeJob = lifecycleScope.launch {
            while (true) {
                binding.waveformView.updateAmplitude(viewModel.amplitude.value)
                delay(com.yaap.app.utils.Constants.WAVEFORM_POLL_INTERVAL_MS)
            }
        }
    }

    private fun showRecordedUi() {
        amplitudeJob?.cancel()
        binding.btnRecord.visibility = View.GONE
        binding.btnStop.visibility = View.GONE
        binding.btnPlay.visibility = View.VISIBLE
        binding.btnReRecord.visibility = View.VISIBLE
        binding.btnAccept.visibility = View.VISIBLE
        binding.waveformView.reset()
    }

    private fun showUploadingUi() {
        binding.btnAccept.isEnabled = false
        binding.uploadProgress.visibility = View.VISIBLE
    }

    private fun showTrainingUi() {
        binding.contentGroup.visibility = View.GONE
        binding.trainingProgressBar.visibility = View.VISIBLE
        binding.tvTrainingLabel.visibility = View.VISIBLE
        binding.tvTrainingLabel.text = "Processing your voice…"
    }

    private fun showError(message: String) {
        com.google.android.material.snackbar.Snackbar.make(binding.root, message, com.google.android.material.snackbar.Snackbar.LENGTH_LONG).show()
    }

    private fun updateStepDots(currentStep: Int) {
        val dots = listOf(binding.dot1, binding.dot2, binding.dot3, binding.dot4, binding.dot5)
        dots.forEachIndexed { index, dot ->
            dot.setBackgroundResource(
                when {
                    index < currentStep -> R.drawable.dot_filled
                    index == currentStep -> R.drawable.dot_active
                    else -> R.drawable.dot_outline
                }
            )
        }
    }

    private fun requestRecordPermission() {
        when {
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED ->
                showCountdownThenRecord()
            shouldShowRequestPermissionRationale(Manifest.permission.RECORD_AUDIO) ->
                showPermissionRationaleDialog()
            else -> permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun showCountdownThenRecord() {
        binding.btnRecord.isEnabled = false
        lifecycleScope.launch {
            for (i in 3 downTo 1) {
                binding.tvCountdown.visibility = View.VISIBLE
                binding.tvCountdown.text = i.toString()
                delay(1000)
            }
            binding.tvCountdown.visibility = View.GONE
            binding.btnRecord.isEnabled = true
            startRecording()
        }
    }

    private fun startRecording() {
        viewModel.startRecording(cacheDir)
    }

    private fun playRecording() {
        val file = cacheDir.resolve("voice_sample_${viewModel.currentIndex}.wav")
        if (!file.exists()) return
        mediaPlayer?.release()
        mediaPlayer = MediaPlayer().apply {
            setDataSource(file.absolutePath)
            prepare()
            start()
        }
    }

    private fun showPermissionRationaleDialog() {
        com.google.android.material.dialog.MaterialAlertDialogBuilder(this)
            .setTitle("Microphone Permission")
            .setMessage("YAAP needs microphone access to record your voice for the AI cloning feature. Your voice data is used only to personalise call translation.")
            .setPositiveButton("Grant") { _, _ -> permissionLauncher.launch(Manifest.permission.RECORD_AUDIO) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun navigateToMain() {
        startActivity(Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        })
        finish()
    }

    override fun onDestroy() {
        mediaPlayer?.release()
        super.onDestroy()
    }
}
