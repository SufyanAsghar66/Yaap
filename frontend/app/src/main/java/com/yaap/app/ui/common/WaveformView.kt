package com.yaap.app.ui.common

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import androidx.core.content.ContextCompat
import com.yaap.app.R
import kotlin.math.max
import kotlin.random.Random

/**
 * Custom View that renders animated waveform bars driven by AudioRecord amplitude.
 * Call [updateAmplitude] periodically (every 50ms) to animate.
 */
class WaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private val barCount = 30
    private val barWidthFraction = 0.6f   // bar width relative to slot width
    private val minHeightFraction = 0.08f  // minimum bar height fraction
    private val amplitudes = FloatArray(barCount) { minHeightFraction }
    private val targetAmplitudes = FloatArray(barCount) { minHeightFraction }

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = ContextCompat.getColor(context, R.color.color_secondary)
        style = Paint.Style.FILL
    }

    private val cornerRadius = context.resources.displayMetrics.density * 4f

    fun updateAmplitude(rawAmplitude: Int, maxAmplitude: Int = 32767) {
        val normalised = (rawAmplitude.toFloat() / maxAmplitude).coerceIn(0f, 1f)
        // Shift bars left and add new value at end
        for (i in 0 until barCount - 1) {
            targetAmplitudes[i] = targetAmplitudes[i + 1]
        }
        targetAmplitudes[barCount - 1] = max(minHeightFraction, normalised)
        // Smooth animation
        for (i in 0 until barCount) {
            amplitudes[i] += (targetAmplitudes[i] - amplitudes[i]) * 0.4f
        }
        invalidate()
    }

    /** Call when idle to gently animate random small motion */
    fun showIdleAnimation() {
        for (i in 0 until barCount) {
            targetAmplitudes[i] = Random.nextFloat() * 0.15f + minHeightFraction
        }
        invalidate()
    }

    /** Reset all bars to minimum */
    fun reset() {
        amplitudes.fill(minHeightFraction)
        targetAmplitudes.fill(minHeightFraction)
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width == 0 || height == 0) return

        val slotWidth = width.toFloat() / barCount
        val barWidth = slotWidth * barWidthFraction

        amplitudes.forEachIndexed { index, amp ->
            val barHeight = amp * height
            val left = index * slotWidth + (slotWidth - barWidth) / 2
            val top = (height - barHeight) / 2
            val right = left + barWidth
            val bottom = top + barHeight
            canvas.drawRoundRect(left, top, right, bottom, cornerRadius, cornerRadius, paint)
        }
    }
}
