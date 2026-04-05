package com.yaap.app.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.yaap.app.data.repository.AuthRepository
import com.yaap.app.model.AuthResponse
import com.yaap.app.model.PasswordStrengthResponse
import com.yaap.app.utils.Result
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val repo: AuthRepository
) : ViewModel() {

    private val _authState = MutableStateFlow<Result<AuthResponse>>(Result.Idle)
    val authState: StateFlow<Result<AuthResponse>> = _authState.asStateFlow()

    private val _otpRequestState = MutableStateFlow<Result<Unit>>(Result.Idle)
    val otpRequestState: StateFlow<Result<Unit>> = _otpRequestState.asStateFlow()

    private val _passwordStrength = MutableStateFlow<PasswordStrengthResponse?>(null)
    val passwordStrength: StateFlow<PasswordStrengthResponse?> = _passwordStrength.asStateFlow()

    fun login(email: String, password: String) {
        viewModelScope.launch {
            _authState.value = Result.Loading
            val result = repo.login(email, password)
            if (result is Result.Success) {
                repo.saveTokens(result.data.accessToken, result.data.refreshToken)
            }
            _authState.value = result
        }
    }

    fun signup(email: String, password: String, fullName: String) {
        viewModelScope.launch {
            _authState.value = Result.Loading
            val result = repo.signup(email, password, fullName)
            if (result is Result.Success) {
                repo.saveTokens(result.data.accessToken, result.data.refreshToken)
            }
            _authState.value = result
        }
    }

    fun requestOtp(email: String) {
        viewModelScope.launch {
            _otpRequestState.value = Result.Loading
            val result = repo.requestOtp(email)
            _otpRequestState.value = if (result is Result.Success) Result.Success(Unit)
            else Result.Error((result as Result.Error).message)
        }
    }

    fun verifyOtp(email: String, otp: String) {
        viewModelScope.launch {
            _authState.value = Result.Loading
            val result = repo.verifyOtp(email, otp)
            if (result is Result.Success) {
                repo.saveTokens(result.data.accessToken, result.data.refreshToken)
            }
            _authState.value = result
        }
    }

    fun googleAuth(idToken: String) {
        viewModelScope.launch {
            _authState.value = Result.Loading
            val result = repo.googleAuth(idToken)
            if (result is Result.Success) {
                repo.saveTokens(result.data.accessToken, result.data.refreshToken)
            }
            _authState.value = result
        }
    }

    fun checkPasswordStrength(password: String) {
        viewModelScope.launch {
            val result = repo.checkPasswordStrength(password)
            if (result is Result.Success) _passwordStrength.value = result.data
        }
    }

    fun resetPasswordRequest(email: String) {
        viewModelScope.launch { repo.resetPassword(email) }
    }

    fun resetState() { _authState.value = Result.Idle }
}
