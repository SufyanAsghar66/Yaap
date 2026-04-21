package com.yaap.app.ui.onboarding

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModel
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import android.view.LayoutInflater
import android.view.ViewGroup
import com.yaap.app.data.repository.UserRepository
import com.yaap.app.databinding.ActivityLanguageSelectionBinding
import com.yaap.app.databinding.ItemLanguageBinding
import com.yaap.app.model.Language
import com.yaap.app.utils.Result
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

// ────────────────────────────────────────────────────────────────────
//  LanguageSelectionViewModel
// ────────────────────────────────────────────────────────────────────
@HiltViewModel
class LanguageSelectionViewModel @Inject constructor(
    private val repo: UserRepository
) : ViewModel() {
    private val _languages = MutableStateFlow<List<Language>>(emptyList())
    val languages: StateFlow<List<Language>> = _languages.asStateFlow()

    private val _selectedCode = MutableStateFlow<String?>(null)
    val selectedCode: StateFlow<String?> = _selectedCode.asStateFlow()

    private val _saveState = MutableStateFlow<Result<*>>(Result.Idle)
    val saveState: StateFlow<Result<*>> = _saveState.asStateFlow()

    fun load() {
        viewModelScope.launch {
            when (val r = repo.getLanguages()) {
                is Result.Success -> _languages.value = r.data
                else -> {}
            }
        }
    }

    fun selectLanguage(code: String) { _selectedCode.value = code }

    fun save() {
        val code = _selectedCode.value ?: return
        viewModelScope.launch {
            _saveState.value = Result.Loading
            _saveState.value = repo.updateLanguage(code)
        }
    }
}

// ────────────────────────────────────────────────────────────────────
//  LanguageSelectionActivity
// ────────────────────────────────────────────────────────────────────
@AndroidEntryPoint
class LanguageSelectionActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLanguageSelectionBinding
    private val viewModel: LanguageSelectionViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLanguageSelectionBinding.inflate(layoutInflater)
        setContentView(binding.root)
        onBackPressedDispatcher.addCallback(this, object : androidx.activity.OnBackPressedCallback(true) {
            override fun handleOnBackPressed() { /* Disabled — must complete step */ }
        })

        val adapter = LanguageAdapter { code -> viewModel.selectLanguage(code) }
        binding.rvLanguages.layoutManager = GridLayoutManager(this, 2)
        binding.rvLanguages.adapter = adapter

        lifecycleScope.launch {
            viewModel.languages.collect { langs -> adapter.submitList(langs) }
        }
        lifecycleScope.launch {
            viewModel.selectedCode.collect { code ->
                adapter.setSelected(code)
                binding.btnContinue.isEnabled = code != null
            }
        }
        lifecycleScope.launch {
            viewModel.saveState.collect { state ->
                when (state) {
                    is Result.Loading -> binding.btnContinue.isEnabled = false
                    is Result.Success<*> -> {
                        startActivity(Intent(this@LanguageSelectionActivity, com.yaap.app.ui.main.MainActivity::class.java).apply {
                            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP
                        })
                        finish()
                    }
                    is Result.Error -> {
                        binding.btnContinue.isEnabled = true
                        com.google.android.material.snackbar.Snackbar.make(binding.root, state.message, com.google.android.material.snackbar.Snackbar.LENGTH_LONG).show()
                    }
                    else -> {}
                }
            }
        }

        binding.btnContinue.setOnClickListener { viewModel.save() }
        viewModel.load()
    }
}

// ────────────────────────────────────────────────────────────────────
//  LanguageAdapter
// ────────────────────────────────────────────────────────────────────
class LanguageAdapter(
    private val onSelected: (String) -> Unit
) : RecyclerView.Adapter<LanguageAdapter.ViewHolder>() {

    private var items: List<Language> = emptyList()
    private var selectedCode: String? = null

    fun submitList(list: List<Language>) { items = list; notifyDataSetChanged() }
    fun setSelected(code: String?) { selectedCode = code; notifyDataSetChanged() }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemLanguageBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(items[position], items[position].code == selectedCode, onSelected)
    }

    class ViewHolder(private val binding: ItemLanguageBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(language: Language, isSelected: Boolean, onClick: (String) -> Unit) {
            binding.tvFlag.text = language.flagEmoji
            binding.tvName.text = language.name
            binding.tvNativeName.text = language.nativeName
            binding.root.isSelected = isSelected
            if (isSelected) {
                binding.ivCheck.visibility = View.VISIBLE
                binding.root.setBackgroundResource(com.yaap.app.R.drawable.bg_language_selected)
            } else {
                binding.ivCheck.visibility = View.GONE
                binding.root.setBackgroundResource(com.yaap.app.R.drawable.bg_card)
            }
            binding.root.setOnClickListener { onClick(language.code) }
        }
    }
}
