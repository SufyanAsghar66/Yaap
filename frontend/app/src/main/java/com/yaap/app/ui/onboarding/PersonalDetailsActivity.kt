package com.yaap.app.ui.onboarding

import android.app.DatePickerDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import com.yaap.app.data.repository.UserRepository
import com.yaap.app.databinding.ActivityPersonalDetailsBinding
import com.yaap.app.model.UpdateProfileRequest
import com.yaap.app.utils.Result
import com.yaap.app.utils.loadAvatar
import com.yaap.app.utils.textString
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.util.*
import javax.inject.Inject

@HiltViewModel
class PersonalDetailsViewModel @Inject constructor(
    private val repo: UserRepository
) : ViewModel() {
    private val _saveState = MutableStateFlow<Result<*>>(Result.Idle)
    val saveState: StateFlow<Result<*>> = _saveState.asStateFlow()

    private val _avatarUrl = MutableStateFlow<String?>(null)
    val avatarUrl: StateFlow<String?> = _avatarUrl.asStateFlow()

    fun uploadAvatar(uri: Uri, contentResolver: android.content.ContentResolver) {
        viewModelScope.launch {
            val bytes = contentResolver.openInputStream(uri)?.readBytes() ?: return@launch
            val requestBody = bytes.toRequestBody("image/jpeg".toMediaType())
            val part = MultipartBody.Part.createFormData("avatar", "avatar.jpg", requestBody)
            val result = repo.uploadAvatar(part)
            if (result is Result.Success) _avatarUrl.value = result.data.avatarUrl
        }
    }

    fun save(
        displayName: String,
        bio: String,
        countryCode: String,
        dateOfBirth: String,
        timezone: String
    ) {
        viewModelScope.launch {
            _saveState.value = Result.Loading
            _saveState.value = repo.updateProfile(
                UpdateProfileRequest(
                    displayName = displayName,
                    bio = bio.takeIf { it.isNotEmpty() },
                    countryCode = countryCode.takeIf { it.isNotEmpty() },
                    dateOfBirth = dateOfBirth.takeIf { it.isNotEmpty() },
                    timezone = timezone
                )
            )
        }
    }
}

@AndroidEntryPoint
class PersonalDetailsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityPersonalDetailsBinding
    private val viewModel: PersonalDetailsViewModel by viewModels()
    private var selectedDob: String = ""

    private val galleryLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        uri ?: return@registerForActivityResult
        binding.ivAvatar.loadAvatar(uri.toString())
        viewModel.uploadAvatar(uri, contentResolver)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPersonalDetailsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Auto-populate timezone
        binding.etTimezone.setText(TimeZone.getDefault().id)

        // Avatar tap
        binding.ivAvatar.setOnClickListener { showAvatarPicker() }
        binding.ivCameraOverlay.setOnClickListener { showAvatarPicker() }

        // Date of birth picker
        binding.etDob.setOnClickListener {
            val cal = Calendar.getInstance()
            DatePickerDialog(this, { _, year, month, day ->
                selectedDob = String.format("%04d-%02d-%02d", year, month + 1, day)
                binding.etDob.setText(selectedDob)
            }, cal.get(Calendar.YEAR) - 25, cal.get(Calendar.MONTH), cal.get(Calendar.DAY_OF_MONTH)).show()
        }

        // Bio char counter
        binding.etBio.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                binding.tvBioCount.text = "${s?.length ?: 0}/${com.yaap.app.utils.Constants.BIO_MAX_CHARS}"
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })

        binding.btnContinue.setOnClickListener {
            val name = binding.etDisplayName.textString()
            if (name.length < 2) { binding.tilDisplayName.error = "Name too short"; return@setOnClickListener }
            viewModel.save(
                displayName = name,
                bio = binding.etBio.textString(),
                countryCode = binding.etCountry.textString(),
                dateOfBirth = selectedDob,
                timezone = TimeZone.getDefault().id
            )
        }

        lifecycleScope.launch {
            viewModel.saveState.collect { state ->
                when (state) {
                    is Result.Loading -> { binding.btnContinue.isEnabled = false; binding.progressBar.visibility = View.VISIBLE }
                    is Result.Success<*> -> {
                        binding.progressBar.visibility = View.GONE
                        startActivity(Intent(this@PersonalDetailsActivity, LanguageSelectionActivity::class.java))
                        finish()
                    }
                    is Result.Error -> {
                        binding.progressBar.visibility = View.GONE
                        binding.btnContinue.isEnabled = true
                        com.google.android.material.snackbar.Snackbar.make(binding.root, state.message, com.google.android.material.snackbar.Snackbar.LENGTH_LONG).show()
                    }
                    else -> { binding.progressBar.visibility = View.GONE }
                }
            }
        }
    }

    private fun showAvatarPicker() {
        com.google.android.material.bottomsheet.BottomSheetDialog(this).apply {
            val sheet = layoutInflater.inflate(com.yaap.app.R.layout.bottom_sheet_avatar, null)
            setContentView(sheet)
            sheet.findViewById<android.widget.TextView>(com.yaap.app.R.id.tvGallery).setOnClickListener {
                dismiss()
                galleryLauncher.launch("image/*")
            }
            show()
        }
    }
}
