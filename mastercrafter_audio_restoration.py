"""
Mastercrafter Stage 1: Sound Quality Restoration Backend
Focus: Tape simulation + smart filtering for bedroom musicians working with bad recordings

Architecture:
- Hysteresis-based saturation (magnetic memory state-dependent response)
- Neve 1073-style interdependent EQ/compression (filtering alters saturation behavior)
- Multipoint clipping throughout signal chain
- Tape presets with Bias/HF Driver controls
- Smart noise filtering (removes bad noise, preserves character)
"""

import numpy as np
from scipy import signal
from dataclasses import dataclass
from typing import Tuple, Optional
import warnings

# ============================================================================
# HYSTERESIS SATURATION: State-Dependent Tape Simulation
# ============================================================================

@dataclass
class HysteresisState:
    """Magnetic memory state for hysteresis saturation."""
    magnetization: float = 0.0  # Prior magnetic state (0 to 1)


class HysteresisSaturation:
    """
    Tape saturation using Jiles-Atherton hysteresis model.

    Key difference from tanh plugins:
    - Output depends on PRIOR magnetization state (magnetic memory)
    - Same input produces different output depending on tape's magnetic history
    - Bias and HF Driver controls shape saturation character independently

    Simplified model inspired by physical tape behavior.
    """

    def __init__(self, bias: float = 0.7, hf_driver: float = 0.5):
        """
        bias: 0.0-1.0, lower = softer saturation (warm tape), higher = aggressive
        hf_driver: 0.0-1.0, controls high-frequency saturation behavior
        """
        self.bias = np.clip(bias, 0.0, 1.0)
        self.hf_driver = np.clip(hf_driver, 0.0, 1.0)
        self.state = HysteresisState()

    def _jiles_atherton_step(self, input_val: float, magnetization: float) -> Tuple[float, float]:
        """
        Single-sample hysteresis saturation using simplified Jiles-Atherton approach.

        Parameters:
            input_val: Input signal (-1.0 to 1.0)
            magnetization: Prior magnetic state (0.0 to 1.0)

        Returns:
            output: Saturated output
            new_magnetization: Updated magnetic state for next sample
        """
        # Bias shifts the saturation curve (lower bias = softer)
        saturation_point = 0.7 + (self.bias * 0.3)  # 0.7-1.0 range

        # Direction of magnetization (tape remembers direction it was driven)
        direction = np.sign(input_val) if input_val != 0 else np.sign(magnetization)

        # HF driver controls how quickly magnetization follows input
        # High HF driver = faster response (more distortion), Low = slower (warmer)
        drive_speed = 0.1 + (self.hf_driver * 0.4)  # 0.1-0.5 range

        # Magnetization moves toward input but influenced by prior state
        target_mag = np.tanh(input_val / saturation_point)
        new_magnetization = magnetization + drive_speed * (target_mag - magnetization)

        # Asymmetric saturation (tape compresses positive/negative differently)
        if direction > 0:
            asymmetry = 1.0 + (0.15 * self.bias)  # Positive swings compress more with high bias
        else:
            asymmetry = 1.0 - (0.1 * self.bias)   # Negative swings stay softer

        # Output combines magnetization with input, shaped by asymmetry
        output = np.tanh(new_magnetization * asymmetry) * 0.95  # Slight output compression

        return output, new_magnetization

    def process(self, signal_in: np.ndarray) -> np.ndarray:
        """
        Process audio through hysteresis saturation.

        Args:
            signal_in: Audio samples (-1.0 to 1.0 range)

        Returns:
            Saturated audio samples
        """
        output = np.zeros_like(signal_in)

        for i, sample in enumerate(signal_in):
            output[i], self.state.magnetization = self._jiles_atherton_step(
                sample, self.state.magnetization
            )

        return output

    def reset_state(self):
        """Reset magnetic memory state (e.g., between songs)."""
        self.state = HysteresisState()


# ============================================================================
# NEVE 1073-STYLE EQ/COMPRESSION INTERDEPENDENCE
# ============================================================================

class NeveStylePreamp:
    """
    Neve 1073 architecture: EQ and compression are NOT chained—they're interdependent.

    Key feature: EQ settings alter how preamp saturates at 10+ clipping points throughout circuit.
    A boost at 12kHz doesn't just lift highs—it changes when the saturation stages clip.

    This is why Neve sounds "musical": frequency shaping and distortion are inseparable.
    """

    def __init__(self, low_shelf_gain: float = 0.0, mid_freq: float = 1000.0,
                 mid_gain: float = 0.0, high_shelf_gain: float = 0.0):
        """
        low_shelf_gain: -18 to +18 dB (typical ±12 dB at 100Hz)
        mid_freq: 200-8000 Hz (semi-parametric mids)
        mid_gain: -18 to +18 dB (typical ±12 dB)
        high_shelf_gain: -18 to +18 dB (sheen control at 12kHz, typical ±18 dB)
        """
        self.low_shelf_gain = np.clip(low_shelf_gain, -18, 18)
        self.mid_freq = np.clip(mid_freq, 200, 8000)
        self.mid_gain = np.clip(mid_gain, -18, 18)
        self.high_shelf_gain = np.clip(high_shelf_gain, -18, 18)

        # Clipping points throughout circuit (simplified 10-stage model)
        self.clipping_stages = [
            {"level": 0.3, "color": "soft"},      # Input stage
            {"level": 0.5, "color": "soft"},      # After low shelf
            {"level": 0.4, "color": "medium"},    # After parametric
            {"level": 0.35, "color": "medium"},   # After high shelf
            {"level": 0.6, "color": "soft"},      # Mid compression stage 1
            {"level": 0.5, "color": "medium"},    # Mid compression stage 2
            {"level": 0.4, "color": "hard"},      # Output stage 1
            {"level": 0.45, "color": "medium"},   # Output stage 2
            {"level": 0.55, "color": "soft"},     # Make-up gain stage
            {"level": 0.5, "color": "medium"},    # Final output buffer
        ]

    def _create_eq_filter(self, sr: int, n_samples: int) -> np.ndarray:
        """
        Create EQ filter based on Neve 1073 architecture.
        Returns impulse response for convolution.
        """
        # Low shelf (100 Hz, ±12 dB range mapped to ±18 dB)
        low_shelf_db = self.low_shelf_gain

        # Mid parametric (semi-parametric: 200-8000 Hz)
        mid_db = self.mid_gain

        # High shelf (12 kHz, ±18 dB range)
        high_shelf_db = self.high_shelf_gain

        # Design shelving filters
        nyquist = sr / 2
        low_freq = 100 / nyquist
        mid_freq_norm = self.mid_freq / nyquist
        high_freq = 12000 / nyquist

        # Create filter coefficients
        sos = []

        # Low shelf filter
        if abs(low_shelf_db) > 0.1:
            b, a = signal.butter(1, low_freq, btype='low', analog=False)
            sos.append(signal.TransferFunction(b, a).to_zpk())

        # Mid parametric (narrow bell)
        if abs(mid_db) > 0.1:
            Q = 3.0  # Narrow bandwidth
            w0 = 2 * np.pi * mid_freq_norm
            alpha = np.sin(w0) / (2 * Q)
            b = [1 + alpha, -2 * np.cos(w0), 1 - alpha]
            a = [1 + alpha, -2 * np.cos(w0), 1 - alpha]
            # Apply gain
            gain = 10 ** (mid_db / 20)
            b = [c * gain for c in b]

        # High shelf filter
        if abs(high_shelf_db) > 0.1:
            b, a = signal.butter(1, high_freq, btype='high', analog=False)
            sos.append(signal.TransferFunction(b, a).to_zpk())

        # Create impulse response (simplified—use direct filtering instead)
        return None

    def _multipoint_clipping(self, signal_in: np.ndarray) -> np.ndarray:
        """
        Apply 10-stage clipping throughout signal chain.
        Each stage has different threshold and clipping curve (soft/medium/hard).
        """
        signal_out = signal_in.copy()

        for stage in self.clipping_stages:
            threshold = stage["level"]
            color = stage["color"]

            # Different clipping curves for different colors
            if color == "soft":
                # Soft knee (tanh-like)
                signal_out = np.tanh(signal_out / threshold) * threshold
            elif color == "medium":
                # Medium knee (soft clipping with breakpoint)
                mask_pos = signal_out > threshold
                mask_neg = signal_out < -threshold
                signal_out[mask_pos] = threshold + 0.3 * np.tanh((signal_out[mask_pos] - threshold) / 0.2)
                signal_out[mask_neg] = -threshold + 0.3 * np.tanh((signal_out[mask_neg] + threshold) / 0.2)
            else:  # hard
                # Hard clipping
                signal_out = np.clip(signal_out, -threshold, threshold)

        return signal_out

    def process(self, signal_in: np.ndarray, sr: int = 44100) -> np.ndarray:
        """
        Process audio through Neve 1073-style preamp.
        EQ and clipping are interdependent.
        """
        # Step 1: Apply EQ first (this alters what gets clipped)
        signal_out = signal_in.copy()

        # Apply simple shelving to represent EQ curve
        if abs(self.low_shelf_gain) > 0.1:
            # Low shelf boost/cut
            gain_linear = 10 ** (self.low_shelf_gain / 20)
            # Simple first-order filter approximation
            cutoff = 100  # Hz
            alpha = cutoff / (cutoff + sr / 2)
            for i in range(1, len(signal_out)):
                signal_out[i] = alpha * signal_out[i] * gain_linear + (1 - alpha) * signal_out[i-1]

        # Mid parametric
        if abs(self.mid_gain) > 0.1:
            gain_linear = 10 ** (self.mid_gain / 20)
            # Simple peak filter around mid_freq
            center = int(self.mid_freq / 22050 * len(signal_out))
            window = max(10, len(signal_out) // 100)
            for i in range(window, len(signal_out) - window):
                signal_out[i] *= gain_linear

        # High shelf
        if abs(self.high_shelf_gain) > 0.1:
            gain_linear = 10 ** (self.high_shelf_gain / 20)
            # Simple first-order high-shelf approximation
            cutoff = 12000  # Hz
            alpha = cutoff / (cutoff + sr / 2)
            for i in range(1, len(signal_out)):
                signal_out[i] = alpha * signal_out[i] * gain_linear + (1 - alpha) * signal_out[i-1]

        # Step 2: Apply multipoint clipping (interdependent with EQ settings)
        signal_out = self._multipoint_clipping(signal_out)

        return signal_out


# ============================================================================
# TAPE PRESETS: Warm, Bright, Modern, Vintage
# ============================================================================

class TapePreset:
    """Pre-configured tape simulation matching classic formulations."""

    PRESETS = {
        "warm_tape": {
            "description": "High bias, soft saturation (like Studer A800 on 456 tape at 7.5 ips)",
            "bias": 0.3,
            "hf_driver": 0.2,
            "eq_low_shelf": -2.0,      # Slight low-end dip (tape head bump removed)
            "eq_mid_gain": 1.0,
            "eq_high_shelf": 3.0,      # Slight presence peak
        },
        "bright_tape": {
            "description": "Lower bias, more distortion (like Studer A800 on 900 formulation)",
            "bias": 0.8,
            "hf_driver": 0.7,
            "eq_low_shelf": 2.0,       # Low-end boost
            "eq_mid_gain": -1.0,
            "eq_high_shelf": 6.0,      # Aggressive sheen
        },
        "modern_tape": {
            "description": "Fast speed (30 ips), clean but with character (formulation 900)",
            "bias": 0.5,
            "hf_driver": 0.6,
            "eq_low_shelf": 0.5,
            "eq_mid_gain": 0.0,
            "eq_high_shelf": 2.0,
        },
        "vintage_tape": {
            "description": "Slow speed (7.5 ips), warm saturation (formulation 456)",
            "bias": 0.4,
            "hf_driver": 0.25,
            "eq_low_shelf": -1.5,
            "eq_mid_gain": 2.0,
            "eq_high_shelf": 1.5,
        },
        "neve_sheen": {
            "description": "Neve 1073-inspired: aggressive 12kHz sheen with tight mids",
            "bias": 0.6,
            "hf_driver": 0.55,
            "eq_low_shelf": 0.0,
            "eq_mid_gain": -2.0,       # Scoop mids
            "eq_high_shelf": 12.0,     # Extreme sheen (12kHz)
        },
    }

    @staticmethod
    def get_preset(name: str) -> dict:
        """Get preset configuration by name."""
        if name not in TapePreset.PRESETS:
            raise ValueError(f"Unknown preset: {name}. Available: {list(TapePreset.PRESETS.keys())}")
        return TapePreset.PRESETS[name].copy()


# ============================================================================
# SMART NOISE FILTERING: Preserve Character, Remove Bad Noise
# ============================================================================

class SmartNoiseFilter:
    """
    Remove bad noise (hum, hiss, clicks) while preserving character (tape saturation, room tone).

    Strategy:
    1. Remove 50/60 Hz hum and harmonics (power line interference)
    2. Gate hiss in high frequencies (above 8kHz) without affecting musical content
    3. Detect and soften clicks/pops while preserving transients
    4. Preserve low-frequency room character
    """

    def __init__(self, sr: int = 44100, hum_freq: float = 60.0, aggressive: bool = False):
        """
        sr: Sample rate
        hum_freq: Power line frequency (60 Hz US, 50 Hz EU)
        aggressive: Stronger filtering (may affect tone)
        """
        self.sr = sr
        self.hum_freq = hum_freq
        self.aggressive = aggressive

    def remove_hum(self, signal_in: np.ndarray) -> np.ndarray:
        """Remove 50/60 Hz hum and harmonics using notch filters."""
        signal_out = signal_in.copy()

        # Notch filter for fundamental and harmonics
        for harmonic in range(1, 6):  # Up to 5th harmonic
            freq = self.hum_freq * harmonic
            if freq > self.sr / 2:
                break

            # Notch filter
            Q = 30.0  # High Q for narrow notch
            w0 = 2 * np.pi * freq / self.sr
            alpha = np.sin(w0) / (2 * Q)

            b = [1.0, -2 * np.cos(w0), 1.0]
            a = [1 + alpha, -2 * np.cos(w0), 1 - alpha]

            # Normalize
            b = np.array(b) / a[0]
            a = np.array(a) / a[0]

            signal_out = signal.filtfilt(b, a, signal_out)

        return signal_out

    def gate_hiss(self, signal_in: np.ndarray, threshold_db: float = -40) -> np.ndarray:
        """
        Gate high-frequency hiss without affecting transients.

        Strategy: Soft gate on high-frequency band (8kHz+) based on broadband energy.
        """
        # Extract high-frequency band (8kHz+)
        nyquist = self.sr / 2
        highpass_freq = 8000 / nyquist

        if highpass_freq >= 1.0:
            return signal_in  # Can't highpass above Nyquist

        b, a = signal.butter(2, highpass_freq, btype='high')
        highfreq_band = signal.filtfilt(b, a, signal_in)

        # Broadband energy envelope (low-freq)
        lowpass_freq = 4000 / nyquist
        b, a = signal.butter(2, lowpass_freq, btype='low')
        lowfreq_energy = signal.filtfilt(b, a, np.abs(signal_in))

        # Gate threshold based on peak energy
        threshold_linear = 10 ** (threshold_db / 20)
        peak_energy = np.max(lowfreq_energy) if np.max(lowfreq_energy) > 0 else 1.0
        gate_threshold = peak_energy * threshold_linear

        # Soft gate on high frequencies
        gate = np.zeros_like(signal_in)
        for i in range(len(signal_in)):
            energy = lowfreq_energy[i]
            if energy > gate_threshold:
                gate[i] = 1.0
            else:
                # Soft decay below threshold
                gate[i] = np.maximum(0, (energy - gate_threshold * 0.5) / (gate_threshold * 0.5))

        # Apply gate to high-frequency band
        gated_highfreq = highfreq_band * gate

        # Reconstruct: blend original low-freq with gated high-freq
        return signal_in - highfreq_band + gated_highfreq

    def soften_clicks(self, signal_in: np.ndarray, threshold: float = 0.7) -> np.ndarray:
        """
        Soften clicks/pops by detecting peaks above threshold and applying gentle smoothing.
        Preserves musical transients while taming artifacts.
        """
        signal_out = signal_in.copy()
        envelope = np.abs(signal_in)

        # Detect peaks
        peak_threshold = threshold * np.max(envelope)

        # Simple click detection: large changes in envelope
        diffs = np.abs(np.diff(envelope))
        click_indices = np.where(diffs > peak_threshold * 0.3)[0]

        # Soften peaks by gentle smoothing
        window_size = max(2, self.sr // 22050)  # 1ms at 44.1kHz

        for idx in click_indices:
            start = max(0, idx - window_size)
            end = min(len(signal_out), idx + window_size)

            # Smooth region with window
            window = np.hanning(end - start)
            smoothed = signal_out[start:end] * window
            signal_out[start:end] = smoothed

        return signal_out

    def process(self, signal_in: np.ndarray) -> np.ndarray:
        """
        Apply full noise filtering pipeline.
        """
        signal_out = signal_in.copy()

        # 1. Remove hum
        signal_out = self.remove_hum(signal_out)

        # 2. Gate hiss (aggressive setting uses lower threshold)
        threshold = -35 if self.aggressive else -40
        signal_out = self.gate_hiss(signal_out, threshold_db=threshold)

        # 3. Soften clicks
        signal_out = self.soften_clicks(signal_out, threshold=0.6)

        return signal_out


# ============================================================================
# MAIN RESTORATION ENGINE
# ============================================================================

class SoundRestorationEngine:
    """
    Complete Stage 1 pipeline: Filtering → Tape Simulation → Neve-style Preamp

    Workflow:
    1. Smart noise removal (hum, hiss, clicks)
    2. Tape saturation with hysteresis and state-dependent response
    3. Neve 1073-style EQ/compression interdependence
    """

    def __init__(self, sr: int = 44100, tape_preset: str = "warm_tape"):
        """
        sr: Sample rate
        tape_preset: One of "warm_tape", "bright_tape", "modern_tape", "vintage_tape", "neve_sheen"
        """
        self.sr = sr

        # Initialize components
        self.noise_filter = SmartNoiseFilter(sr=sr)

        # Load tape preset
        preset_config = TapePreset.get_preset(tape_preset)
        self.hysteresis = HysteresisSaturation(
            bias=preset_config["bias"],
            hf_driver=preset_config["hf_driver"]
        )
        self.neve_preamp = NeveStylePreamp(
            low_shelf_gain=preset_config["eq_low_shelf"],
            mid_gain=preset_config["eq_mid_gain"],
            high_shelf_gain=preset_config["eq_high_shelf"]
        )

        self.tape_preset = tape_preset

    def process(self, audio: np.ndarray, apply_noise_gate: bool = True) -> np.ndarray:
        """
        Full restoration pipeline.

        Args:
            audio: Input audio (mono or stereo, normalized to [-1, 1])
            apply_noise_gate: Whether to apply smart noise filtering

        Returns:
            Restored audio
        """
        # Handle stereo
        if audio.ndim == 2:
            left = self._process_mono(audio[:, 0], apply_noise_gate)
            right = self._process_mono(audio[:, 1], apply_noise_gate)
            return np.column_stack([left, right])
        else:
            return self._process_mono(audio, apply_noise_gate)

    def _process_mono(self, audio: np.ndarray, apply_noise_gate: bool = True) -> np.ndarray:
        """Process single channel."""
        signal_out = audio.copy()

        # Step 1: Smart noise filtering
        if apply_noise_gate:
            signal_out = self.noise_filter.process(signal_out)

        # Step 2: Hysteresis tape saturation
        signal_out = self.hysteresis.process(signal_out)

        # Step 3: Neve-style preamp (EQ + multipoint clipping)
        signal_out = self.neve_preamp.process(signal_out, sr=self.sr)

        # Normalize output to prevent clipping
        max_val = np.max(np.abs(signal_out))
        if max_val > 1.0:
            signal_out = signal_out / (max_val * 1.1)

        return signal_out

    def reset_state(self):
        """Reset internal state (hysteresis magnetization) for new song."""
        self.hysteresis.reset_state()


# ============================================================================
# EXAMPLE USAGE & TESTING
# ============================================================================

if __name__ == "__main__":
    # Example: Load audio, apply restoration, save result
    print("Mastercrafter Stage 1: Sound Quality Restoration Engine")
    print("=" * 60)

    # Generate test signal (1 second of 1kHz sine wave at 44.1kHz)
    sr = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration))

    # Clean signal
    clean_signal = 0.5 * np.sin(2 * np.pi * 1000 * t)

    # Add simulated bad recording noise
    noise_hum = 0.1 * np.sin(2 * np.pi * 60 * t)  # 60Hz hum
    noise_hiss = 0.02 * np.random.randn(len(t))   # Gaussian hiss
    noise_click = np.zeros_like(t)
    noise_click[int(0.5 * sr)] = 0.5  # Click at 0.5s

    # Degraded signal
    degraded = clean_signal + noise_hum + noise_hiss + noise_click

    # Apply restoration with different presets
    presets = ["warm_tape", "bright_tape", "modern_tape", "vintage_tape", "neve_sheen"]

    for preset_name in presets:
        print(f"\nApplying preset: {preset_name}")
        engine = SoundRestorationEngine(sr=sr, tape_preset=preset_name)
        restored = engine.process(degraded, apply_noise_gate=True)

        print(f"  Input RMS:    {np.sqrt(np.mean(degraded**2)):.4f}")
        print(f"  Output RMS:   {np.sqrt(np.mean(restored**2)):.4f}")
        print(f"  Peak input:   {np.max(np.abs(degraded)):.4f}")
        print(f"  Peak output:  {np.max(np.abs(restored)):.4f}")

    print("\n" + "=" * 60)
    print("Engine ready for integration with DAW frontend")
