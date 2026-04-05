package com.yaap.app.ui.auth

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.lifecycleScope
import com.yaap.app.R
import com.yaap.app.databinding.FragmentLoginBinding
import com.yaap.app.utils.Result
import com.yaap.app.utils.isValidEmail
import com.yaap.app.utils.isValidPassword
import com.yaap.app.utils.showSnackbarError
import com.yaap.app.utils.textString
import kotlinx.coroutines.launch

class LoginFragment : Fragment() {

    private var _binding: FragmentLoginBinding? = null
    private val binding get() = _binding!!
    private val viewModel: AuthViewModel by activityViewModels()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentLoginBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupValidation()
        setupClickListeners()
        observeState()
    }

    private fun setupValidation() {
        binding.etEmail.setOnFocusChangeListener { _, hasFocus ->
            if (!hasFocus) {
                val email = binding.etEmail.textString()
                if (email.isNotEmpty() && !email.isValidEmail())
                    binding.tilEmail.error = "Invalid email address"
                else binding.tilEmail.error = null
            }
            updateSubmitButton()
        }
        binding.etPassword.setOnFocusChangeListener { _, hasFocus ->
            if (!hasFocus) {
                val pwd = binding.etPassword.textString()
                if (pwd.isNotEmpty() && !pwd.isValidPassword())
                    binding.tilPassword.error = "Min ${com.yaap.app.utils.Constants.MIN_PASSWORD_LENGTH} characters"
                else binding.tilPassword.error = null
            }
            updateSubmitButton()
        }
        binding.etEmail.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { updateSubmitButton() }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
        binding.etPassword.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { updateSubmitButton() }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
    }

    private fun updateSubmitButton() {
        val emailOk = binding.etEmail.textString().isValidEmail()
        val pwdOk = binding.etPassword.textString().isValidPassword()
        binding.btnLogin.isEnabled = emailOk && pwdOk
    }

    private fun setupClickListeners() {
        binding.btnLogin.setOnClickListener {
            viewModel.login(binding.etEmail.textString(), binding.etPassword.textString())
        }
        binding.btnForgotPassword.setOnClickListener {
            val email = binding.etEmail.textString()
            if (email.isValidEmail()) {
                viewModel.resetPasswordRequest(email)
                com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
                    .setTitle("Password Reset")
                    .setMessage("If an account exists for $email, you will receive reset instructions shortly.")
                    .setPositiveButton("OK", null)
                    .show()
            } else {
                binding.tilEmail.error = "Enter your email first"
            }
        }
        binding.btnGoogleSignIn.setOnClickListener {
            (activity as? AuthActivity)?.let { /* Google Sign-In handled in AuthActivity */ }
            launchGoogleSignIn()
        }
    }

    private fun launchGoogleSignIn() {
        // Google Sign-In requires GoogleSignInClient setup with web_client_id from google-services.json
        // This is a placeholder — wire up in AuthActivity with proper GoogleSignInClient
        binding.root.showSnackbarError("Configure google-services.json to enable Google Sign-In")
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.authState.collect { state ->
                when (state) {
                    is Result.Loading -> {
                        binding.btnLogin.isEnabled = false
                        binding.progressBar.visibility = View.VISIBLE
                    }
                    is Result.Success -> {
                        binding.progressBar.visibility = View.GONE
                        viewModel.resetState()
                        (activity as? AuthActivity)?.navigatePerNextStep(state.data.nextStep)
                    }
                    is Result.Error -> {
                        binding.progressBar.visibility = View.GONE
                        binding.btnLogin.isEnabled = true
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

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
}
