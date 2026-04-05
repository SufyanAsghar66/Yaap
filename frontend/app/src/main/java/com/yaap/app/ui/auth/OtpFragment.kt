package com.yaap.app.ui.auth

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.lifecycleScope
import com.yaap.app.databinding.FragmentOtpBinding
import com.yaap.app.utils.Result
import com.yaap.app.utils.isValidEmail
import com.yaap.app.utils.showSnackbarError
import com.yaap.app.utils.textString
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class OtpFragment : Fragment() {
    private var _binding: FragmentOtpBinding? = null
    private val binding get() = _binding!!
    private val viewModel: AuthViewModel by activityViewModels()
    private var timerJob: Job? = null
    private var currentEmail: String = ""
    private val otpBoxes: List<EditText> by lazy {
        listOf(
            binding.otpBox1, binding.otpBox2, binding.otpBox3,
            binding.otpBox4, binding.otpBox5, binding.otpBox6
        )
    }

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, s: Bundle?): View {
        _binding = FragmentOtpBinding.inflate(inflater, container, false)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        setupOtpBoxes()
        setupClickListeners()
        observeState()
        binding.otpContainer.visibility = View.GONE
    }

    private fun setupOtpBoxes() {
        otpBoxes.forEachIndexed { index, box ->
            box.addTextChangedListener(object : android.text.TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                    if (s?.length == 1 && index < otpBoxes.size - 1) {
                        otpBoxes[index + 1].requestFocus()
                    }
                    // Auto-submit on last digit
                    if (index == otpBoxes.size - 1 && s?.length == 1) {
                        val otp = otpBoxes.joinToString("") { it.textString() }
                        if (otp.length == 6) viewModel.verifyOtp(currentEmail, otp)
                    }
                }
                override fun afterTextChanged(s: android.text.Editable?) {}
            })
            // Handle backspace to go to previous box
            box.setOnKeyListener { _, keyCode, event ->
                if (keyCode == android.view.KeyEvent.KEYCODE_DEL &&
                    event.action == android.view.KeyEvent.ACTION_DOWN &&
                    box.textString().isEmpty() && index > 0) {
                    otpBoxes[index - 1].requestFocus()
                    otpBoxes[index - 1].setText("")
                    true
                } else false
            }
        }
    }

    private fun setupClickListeners() {
        binding.btnSendCode.setOnClickListener {
            val email = binding.etEmail.textString()
            if (!email.isValidEmail()) {
                binding.tilEmail.error = "Enter a valid email"
                return@setOnClickListener
            }
            currentEmail = email
            viewModel.requestOtp(email)
        }

        binding.btnResendCode.setOnClickListener {
            if (currentEmail.isNotEmpty()) viewModel.requestOtp(currentEmail)
        }
    }

    private fun startCountdown() {
        timerJob?.cancel()
        val totalSeconds = 10 * 60 // 10 minutes
        timerJob = viewLifecycleOwner.lifecycleScope.launch {
            var remaining = totalSeconds
            while (remaining > 0) {
                val mins = remaining / 60
                val secs = remaining % 60
                binding.tvCountdown.text = String.format("%02d:%02d", mins, secs)
                delay(1000)
                remaining--
            }
            binding.tvCountdown.text = "Code expired"
            binding.btnResendCode.isEnabled = true
        }
    }

    private fun observeState() {
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.otpRequestState.collect { state ->
                when (state) {
                    is Result.Success -> {
                        binding.otpContainer.visibility = View.VISIBLE
                        binding.btnResendCode.isEnabled = false
                        startCountdown()
                        otpBoxes[0].requestFocus()
                    }
                    is Result.Error -> binding.root.showSnackbarError(state.message)
                    else -> {}
                }
            }
        }

        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.authState.collect { state ->
                when (state) {
                    is Result.Loading -> binding.progressBar.visibility = View.VISIBLE
                    is Result.Success -> {
                        binding.progressBar.visibility = View.GONE
                        viewModel.resetState()
                        (activity as? AuthActivity)?.navigatePerNextStep(state.data.nextStep)
                    }
                    is Result.Error -> {
                        binding.progressBar.visibility = View.GONE
                        binding.root.showSnackbarError(state.message)
                        viewModel.resetState()
                    }
                    else -> binding.progressBar.visibility = View.GONE
                }
            }
        }
    }

    override fun onDestroyView() {
        timerJob?.cancel()
        super.onDestroyView()
        _binding = null
    }
}
