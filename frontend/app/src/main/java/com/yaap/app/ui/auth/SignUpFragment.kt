package com.yaap.app.ui.auth

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.lifecycleScope
import com.yaap.app.R
import com.yaap.app.databinding.FragmentSignupBinding
import com.yaap.app.utils.Result
import com.yaap.app.utils.isValidEmail
import com.yaap.app.utils.isValidPassword
import com.yaap.app.utils.showSnackbarError
import com.yaap.app.utils.textString
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch

class SignUpFragment : Fragment() {
    private var _binding: FragmentSignupBinding? = null
    private val binding get() = _binding!!
    private val viewModel: AuthViewModel by activityViewModels()
    private val passwordFlow = MutableStateFlow("")

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, s: Bundle?): View {
        _binding = FragmentSignupBinding.inflate(inflater, container, false)
        return binding.root
    }

    @OptIn(FlowPreview::class)
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // ── DEV ONLY: prefill test data — remove before production ──
        prefillTestData()
        // ────────────────────────────────────────────────────────────

        // Debounced password strength check
        viewLifecycleOwner.lifecycleScope.launch {
            passwordFlow.debounce(300).collect { pwd ->
                if (pwd.length >= 3) viewModel.checkPasswordStrength(pwd)
            }
        }

        binding.etPassword.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                passwordFlow.value = s.toString()
                checkPasswordMatch()
                updateSubmitButton()
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
        binding.etConfirmPassword.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                checkPasswordMatch()
                updateSubmitButton()
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })

        binding.btnCreateAccount.setOnClickListener {
            viewModel.signup(
                binding.etEmail.textString(),
                binding.etPassword.textString(),
                binding.etFullName.textString()
            )
        }

        // Observe password strength
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.passwordStrength.collect { strength ->
                strength ?: return@collect
                updateStrengthBar(strength.score)
            }
        }

        // Observe auth state
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.authState.collect { state ->
                when (state) {
                    is Result.Loading -> {
                        binding.btnCreateAccount.isEnabled = false
                        binding.progressBar.visibility = View.VISIBLE
                    }
                    is Result.Success -> {
                        binding.progressBar.visibility = View.GONE
                        viewModel.resetState()
                        (activity as? AuthActivity)?.navigatePerNextStep(state.data.nextStep)
                    }
                    is Result.Error -> {
                        binding.progressBar.visibility = View.GONE
                        binding.btnCreateAccount.isEnabled = true
                        binding.root.showSnackbarError(state.message)
                        viewModel.resetState()
                    }
                    else -> {
                        binding.progressBar.visibility = View.GONE
                        updateSubmitButton()
                    }
                }
            }
        }
    }

    /**
     * DEV ONLY — prefills all signup fields with valid test data so you
     * can tap "Create Account" immediately without typing anything.
     * Delete this function and its call before going to production.
     */
    private fun prefillTestData() {
        val testPassword = "Test@1234"
        binding.etFullName.setText("Test User")
        binding.etEmail.setText("testuser@yaap.dev")
        binding.etPassword.setText(testPassword)
        binding.etConfirmPassword.setText(testPassword)
        // Trigger validation so the button enables immediately
        updateSubmitButton()
        checkPasswordMatch()
    }

    private fun checkPasswordMatch() {
        val pwd = binding.etPassword.textString()
        val confirm = binding.etConfirmPassword.textString()
        if (confirm.isNotEmpty()) {
            if (pwd == confirm) {
                binding.tilConfirmPassword.error = null
                binding.ivPasswordMatch.setImageResource(android.R.drawable.presence_online)
            } else {
                binding.tilConfirmPassword.error = "Passwords don't match"
                binding.ivPasswordMatch.setImageResource(android.R.drawable.presence_busy)
            }
        }
    }

    private fun updateStrengthBar(score: Int) {
        val bars = listOf(
            binding.strengthBar1,
            binding.strengthBar2,
            binding.strengthBar3,
            binding.strengthBar4
        )
        val colors = listOf(
            R.color.color_danger,
            R.color.color_warning,
            R.color.color_secondary,
            R.color.color_success
        )
        bars.forEachIndexed { index, view ->
            val colorRes = if (index < score) colors.getOrElse(score - 1) { R.color.color_muted_text }
            else R.color.color_border
            view.setBackgroundColor(ContextCompat.getColor(requireContext(), colorRes))
        }
    }

    private fun updateSubmitButton() {
        val nameOk = binding.etFullName.textString().length >= 2
        val emailOk = binding.etEmail.textString().isValidEmail()
        val pwdOk = binding.etPassword.textString().isValidPassword()
        val confirmOk = binding.etPassword.textString() == binding.etConfirmPassword.textString()
        binding.btnCreateAccount.isEnabled = nameOk && emailOk && pwdOk && confirmOk
    }

    override fun onDestroyView() { super.onDestroyView(); _binding = null }
}


/*import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.lifecycleScope
import com.yaap.app.R
import com.yaap.app.databinding.FragmentSignupBinding
import com.yaap.app.utils.Result
import com.yaap.app.utils.isValidEmail
import com.yaap.app.utils.isValidPassword
import com.yaap.app.utils.showSnackbarError
import com.yaap.app.utils.textString
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.launch

class SignUpFragment : Fragment() {
    private var _binding: FragmentSignupBinding? = null
    private val binding get() = _binding!!
    private val viewModel: AuthViewModel by activityViewModels()
    private val passwordFlow = MutableStateFlow("")

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, s: Bundle?): View {
        _binding = FragmentSignupBinding.inflate(inflater, container, false)
        return binding.root
    }

    @OptIn(FlowPreview::class)
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // Debounced password strength check
        viewLifecycleOwner.lifecycleScope.launch {
            passwordFlow.debounce(300).collect { pwd ->
                if (pwd.length >= 3) viewModel.checkPasswordStrength(pwd)
            }
        }

        binding.etPassword.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                passwordFlow.value = s.toString()
                checkPasswordMatch()
                updateSubmitButton()
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
        binding.etConfirmPassword.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                checkPasswordMatch()
                updateSubmitButton()
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })

        binding.btnCreateAccount.setOnClickListener {
            viewModel.signup(
                binding.etEmail.textString(),
                binding.etPassword.textString(),
                binding.etFullName.textString()
            )
        }

        // Observe password strength
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.passwordStrength.collect { strength ->
                strength ?: return@collect
                updateStrengthBar(strength.score)
            }
        }

        // Observe auth state
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.authState.collect { state ->
                when (state) {
                    is Result.Loading -> {
                        binding.btnCreateAccount.isEnabled = false
                        binding.progressBar.visibility = View.VISIBLE
                    }
                    is Result.Success -> {
                        binding.progressBar.visibility = View.GONE
                        viewModel.resetState()
                        (activity as? AuthActivity)?.navigatePerNextStep(state.data.nextStep)
                    }
                    is Result.Error -> {
                        binding.progressBar.visibility = View.GONE
                        binding.btnCreateAccount.isEnabled = true
                        binding.root.showSnackbarError(state.message)
                        viewModel.resetState()
                    }
                    else -> {
                        binding.progressBar.visibility = View.GONE
                        updateSubmitButton()
                    }
                }
            }
        }
    }

    private fun checkPasswordMatch() {
        val pwd = binding.etPassword.textString()
        val confirm = binding.etConfirmPassword.textString()
        if (confirm.isNotEmpty()) {
            if (pwd == confirm) {
                binding.tilConfirmPassword.error = null
                binding.ivPasswordMatch.setImageResource(android.R.drawable.presence_online)
            } else {
                binding.tilConfirmPassword.error = "Passwords don't match"
                binding.ivPasswordMatch.setImageResource(android.R.drawable.presence_busy)
            }
        }
    }

    private fun updateStrengthBar(score: Int) {
        val bars = listOf(
            binding.strengthBar1,
            binding.strengthBar2,
            binding.strengthBar3,
            binding.strengthBar4
        )
        val colors = listOf(
            R.color.color_danger,
            R.color.color_warning,
            R.color.color_secondary,
            R.color.color_success
        )
        bars.forEachIndexed { index, view ->
            val colorRes = if (index < score) colors.getOrElse(score - 1) { R.color.color_muted_text }
            else R.color.color_border
            view.setBackgroundColor(ContextCompat.getColor(requireContext(), colorRes))
        }
    }

    private fun updateSubmitButton() {
        val nameOk = binding.etFullName.textString().length >= 2
        val emailOk = binding.etEmail.textString().isValidEmail()
        val pwdOk = binding.etPassword.textString().isValidPassword()
        val confirmOk = binding.etPassword.textString() == binding.etConfirmPassword.textString()
        binding.btnCreateAccount.isEnabled = nameOk && emailOk && pwdOk && confirmOk
    }

    override fun onDestroyView() { super.onDestroyView(); _binding = null }
} */
