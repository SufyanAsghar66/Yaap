package com.yaap.app.ui.settings

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
import com.yaap.app.data.api.WebSocketManager
import com.yaap.app.data.repository.AuthRepository
import com.yaap.app.data.repository.UserRepository
import com.yaap.app.databinding.FragmentSettingsBinding
import com.yaap.app.model.User
import com.yaap.app.ui.auth.AuthActivity
import com.yaap.app.utils.Result
import com.yaap.app.utils.loadAvatar
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

// ────────────────────────────────────────────────────────────────────
//  SettingsViewModel
// ────────────────────────────────────────────────────────────────────
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val userRepo: UserRepository,
    private val authRepo: AuthRepository,
    private val wsManager: WebSocketManager
) : ViewModel() {

    private val _profile = MutableStateFlow<User?>(null)
    val profile: StateFlow<User?> = _profile.asStateFlow()

    private val _logoutState = MutableStateFlow<Result<*>>(Result.Idle)
    val logoutState: StateFlow<Result<*>> = _logoutState.asStateFlow()

    init { loadProfile() }

    fun loadProfile() = viewModelScope.launch {
        when (val r = userRepo.getMyProfile()) {
            is Result.Success -> _profile.value = r.data
            else -> {}
        }
    }

    fun logout() = viewModelScope.launch {
        _logoutState.value = Result.Loading
        authRepo.logout()
        authRepo.clearTokens()
        wsManager.disconnect()
        _logoutState.value = Result.Success(Unit)
    }

    fun updatePrivacy(lastSeenMode: String? = null, readReceipts: Boolean? = null, onlineStatus: Boolean? = null) {
        viewModelScope.launch {
            // PATCH /users/me/ with privacy fields — build request from non-null params
            // For now, call updateProfile with current values; extend UpdateProfileRequest as needed
        }
    }
}

// ────────────────────────────────────────────────────────────────────
//  SettingsFragment
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class SettingsFragment : Fragment() {

    private var _binding: FragmentSettingsBinding? = null
    private val binding get() = _binding!!
    private val viewModel: SettingsViewModel by viewModels()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, s: Bundle?): View {
        _binding = FragmentSettingsBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        observeProfile()
        setupClickListeners()
        observeLogout()
    }

    private fun observeProfile() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.profile.collect { user ->
                user ?: return@collect
                binding.ivAvatar.loadAvatar(user.avatarUrl, user.displayName.take(1))
                binding.tvDisplayName.text = user.displayName
                binding.tvEmail.text = user.email
                binding.tvAppVersion.text = "YAAP v${com.yaap.app.BuildConfig.VERSION_NAME}"
            }
        }
    }

    private fun setupClickListeners() {
        binding.rowEditName.setOnClickListener { showEditNameDialog() }
        binding.rowEditBio.setOnClickListener { showEditBioDialog() }
        binding.rowChangeLanguage.setOnClickListener {
            startActivity(android.content.Intent(requireContext(), com.yaap.app.ui.onboarding.LanguageSelectionActivity::class.java))
        }
        binding.rowReRecordVoice.setOnClickListener {
            startActivity(android.content.Intent(requireContext(), com.yaap.app.ui.onboarding.VoiceTrainingActivity::class.java))
        }
        binding.switchReadReceipts.setOnCheckedChangeListener { _, isChecked ->
            viewModel.updatePrivacy(readReceipts = isChecked)
        }
        binding.switchOnlineStatus.setOnCheckedChangeListener { _, isChecked ->
            viewModel.updatePrivacy(onlineStatus = isChecked)
        }
        binding.btnLogout.setOnClickListener { showLogoutConfirmation() }
    }

    private fun showLogoutConfirmation() {
        com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
            .setTitle("Log Out")
            .setMessage("Are you sure you want to log out?")
            .setPositiveButton("Log Out") { _, _ -> viewModel.logout() }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showEditNameDialog() {
        val input = android.widget.EditText(requireContext()).apply {
            setText(viewModel.profile.value?.displayName)
            hint = "Display name"
        }
        com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
            .setTitle("Edit Name")
            .setView(input)
            .setPositiveButton("Save") { _, _ ->
                val newName = input.text.toString().trim()
                if (newName.length >= 2) {
                    viewLifecycleOwner.lifecycleScope.launch {
                        // call PATCH /users/me/ with new displayName
                    }
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showEditBioDialog() {
        val input = android.widget.EditText(requireContext()).apply {
            setText(viewModel.profile.value?.bio)
            hint = "Bio (max 160 characters)"
            filters = arrayOf(android.text.InputFilter.LengthFilter(160))
        }
        com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
            .setTitle("Edit Bio")
            .setView(input)
            .setPositiveButton("Save") { _, _ -> /* PATCH /users/me/ with bio */ }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun observeLogout() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.logoutState.collect { state ->
                when (state) {
                    is Result.Success<*> -> {
                        startActivity(Intent(requireContext(), AuthActivity::class.java).apply {
                            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
                        })
                    }
                    is Result.Error -> {
                        com.google.android.material.snackbar.Snackbar
                            .make(binding.root, state.message, com.google.android.material.snackbar.Snackbar.LENGTH_SHORT).show()
                    }
                    else -> {}
                }
            }
        }
    }

    override fun onDestroyView() { super.onDestroyView(); _binding = null }
}
