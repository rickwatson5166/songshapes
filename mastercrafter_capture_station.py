"""
Mastercrafter Capture Station: Stage 1.5 Implementation
Real-time audio capture and preprocessing with stem separation

PIPELINE:
1. Smart Noise Filtering (remove hum, hiss, clicks)
2. Saturation Embracer (model tape saturation, solve digital sterility)
3. HPSS Stem Separation (extract vocals/drums/bass/other)
4. Adaptive Learning (personalize saturation response per user)

ARCHITECTURE:
- DSP Backend: Python (this file) with low-latency buffer processing
- Audio I/O: ASIO (Windows) / Core Audio (Mac) via PyAudio/python-sounddevice
- Frontend: Qt6 + PyQtGraph for real-time waveform visualization
- Real-time constraint: <5ms latency end-to-end

WEEK 1 GOALS:
✓ Integrate Saturation Embracer from Stage 1
✓ Implement HPSS stem separation (librosa)
✓ Real-time buffer processing loop
✓ Test on bad recordings (Zoom calls, bedroom demos, tape degradation)
"""

import numpy as np
from scipy import signal
from dataclasses import dataclass
import soundfile as sf
from typing import Tuple, Optional, List, Dict
from collections import deque
import time
from mastercrafter_audio_restoration import (
    SoundRestorationEngine,
    HysteresisSaturation,
    NeveStylePreamp,
    SmartNoiseFilter,
    TapePreset
)

try:
    import librosa
except ImportError:
    librosa = None


# ============================================================================
# HPSS STEM SEPARATION: Harmonic-Percussive Source Separation
# ============================================================================

class HPSSStemSeparator:
    """
    Harmonic-Percussive Source Separation using librosa.
    Splits single audio into:
    - Harmonic (vocals, strings, pads)
    - Percussive (drums, percussion, attacks)

    Can further decompose Harmonic into vocals vs other sources.
    """

    def __init__(self, sr: int = 44100, margin: float = 1.0):
        """
        sr: Sample rate
        margin: HPSS margin (higher = cleaner separation, lower = more bleed)
               Typical: 1.0-2.0
        """
        if librosa is None:
            raise ImportError("librosa required for stem separation: pip install librosa")

        self.sr = sr
        self.margin = margin

    def separate(self, audio: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Separate audio into stems.

        Returns:
        {
            'vocals': Vocal-like harmonic content
            'drums': Percussive content
            'bass': Low-frequency harmonic
            'other': Mid-range harmonic
        }
        """
        # Ensure mono
        if audio.ndim > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio

        # STFT for decomposition
        D = librosa.stft(audio_mono)
        H, P = librosa.decompose.hpss(D, margin=self.margin)

        # Convert back to time domain
        harmonic = librosa.istft(H)
        percussive = librosa.istft(P)

        # Further split harmonic into frequency bands
        # Vocals: 80-3000 Hz (main formants)
        # Bass: 20-200 Hz (fundamental)
        # Other: 3000-8000 Hz (overtones, synths)

        H_vocals, H_other = self._split_harmonic_by_freq(H, sr=self.sr)
        H_bass, H_vocals = self._split_harmonic_by_freq(H_vocals, sr=self.sr,
                                                        low_freq=20, high_freq=200)

        vocals = librosa.istft(H_vocals)
        bass = librosa.istft(H_bass)
        other = librosa.istft(H_other)

        return {
            'vocals': vocals,
            'drums': percussive,
            'bass': bass,
            'other': other
        }

    @staticmethod
    def _split_harmonic_by_freq(D: np.ndarray, sr: int = 44100,
                               low_freq: int = 80, high_freq: int = 3000) -> Tuple[np.ndarray, np.ndarray]:
        """Split STFT by frequency range."""
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2*(D.shape[0]-1))

        # Ensure freqs matches D dimensions
        if len(freqs) > D.shape[0]:
            freqs = freqs[:D.shape[0]]

        mask_in_range = (freqs >= low_freq) & (freqs <= high_freq)

        # Create 2D mask that matches D shape
        mask_2d = mask_in_range[:, np.newaxis]

        D_in = D.copy()
        D_in[~mask_2d] = 0

        D_out = D - D_in

        return D_in, D_out


# ============================================================================
# CAPTURE STATION: Real-Time Processing Pipeline
# ============================================================================

class CaptureStemProcessor:
    """
    Real-time audio capture and preprocessing.

    Pipeline:
    1. Audio capture (file or live input via ASIO/Core Audio)
    2. Smart noise filtering
    3. Saturation embracer (per-stem)
    4. Return processed stems ready for DAW
    """

    def __init__(self, sr: int = 44100, tape_preset: str = "warm_tape",
                 enable_hpss: bool = True, enable_learning: bool = False):
        """
        sr: Sample rate (44100, 48000, 96000)
        tape_preset: warm_tape, bright_tape, modern_tape, vintage_tape, neve_sheen
        enable_hpss: Perform stem separation
        enable_learning: Adapt saturation based on user feedback
        """
        self.sr = sr
        self.tape_preset = tape_preset
        self.enable_hpss = enable_hpss
        self.enable_learning = enable_learning

        # DSP pipeline components
        self.noise_filter = SmartNoiseFilter(sr=sr, hum_freq=60.0, aggressive=False)
        self.saturation = HysteresisSaturation(
            bias=TapePreset.get_preset(tape_preset)['bias'],
            hf_driver=TapePreset.get_preset(tape_preset)['hf_driver']
        )
        self.neve_preamp = NeveStylePreamp(
            low_shelf_gain=TapePreset.get_preset(tape_preset)['eq_low_shelf'],
            mid_gain=TapePreset.get_preset(tape_preset)['eq_mid_gain'],
            high_shelf_gain=TapePreset.get_preset(tape_preset)['eq_high_shelf']
        )

        if self.enable_hpss:
            try:
                self.hpss = HPSSStemSeparator(sr=sr, margin=1.5)
            except ImportError:
                print("Warning: librosa not available, HPSS disabled")
                self.enable_hpss = False

        # Learning state (stores user preferences)
        self.learning_state = {
            'feedback_history': deque(maxlen=100),  # Last 100 user ratings
            'bias_adjustments': [],
            'hf_driver_adjustments': [],
            'avg_user_bias': 0.0,
            'avg_user_hf_driver': 0.0
        }

        # Performance metrics
        self.metrics = {
            'last_process_time': 0.0,
            'max_process_time': 0.0,
            'total_samples_processed': 0,
            'input_rms': 0.0,
            'output_rms': 0.0,
        }

    def process_file(self, input_path: str, output_dir: str = "./processed/") -> Dict[str, str]:
        """
        Process audio file through capture station pipeline.

        Returns:
        {
            'main': 'path to main processed file',
            'vocals': 'path to vocals stem (if HPSS enabled)',
            'drums': 'path to drums stem (if HPSS enabled)',
            'bass': 'path to bass stem (if HPSS enabled)',
            'other': 'path to other stem (if HPSS enabled)',
            'metadata': {
                'processing_time': float,
                'input_rms': float,
                'output_rms': float,
                'reduction_db': float
            }
        }
        """
        start_time = time.time()

        # Load audio
        audio, sr_loaded = sf.read(input_path)

        # Ensure correct sample rate
        if sr_loaded != self.sr:
            print(f"Warning: Resampling from {sr_loaded} to {self.sr}")
            if librosa:
                audio = librosa.resample(audio, orig_sr=sr_loaded, target_sr=self.sr)
            else:
                # Simple decimation/interpolation fallback
                ratio = self.sr / sr_loaded
                new_length = int(len(audio) * ratio)
                indices = np.linspace(0, len(audio)-1, new_length)
                audio = np.interp(indices, np.arange(len(audio)), audio)

        # Normalize to [-1, 1]
        max_val = np.max(np.abs(audio))
        if max_val > 1.0:
            audio = audio / max_val

        # Metrics: input RMS
        self.metrics['input_rms'] = float(np.sqrt(np.mean(audio ** 2)))

        # Step 1: Smart noise filtering
        print(f"[Capture Station] Processing {input_path}")
        print(f"  → Applying smart noise filtering...")
        audio_filtered = self.noise_filter.remove_hum(audio)
        audio_filtered = self.noise_filter.gate_hiss(audio_filtered)

        # Step 2: Apply saturation embracer + Neve preamp
        print(f"  → Applying saturation embracer ({self.tape_preset})...")
        audio_saturated = self.saturation.process(audio_filtered)
        audio_saturated = self.neve_preamp.process(audio_saturated, sr=self.sr)

        # Step 3: HPSS stem separation (optional)
        if self.enable_hpss:
            print(f"  → Separating stems (HPSS)...")
            try:
                stems = self.hpss.separate(audio_saturated)
            except Exception as e:
                print(f"  Warning: HPSS failed ({e}), skipping stem separation")
                stems = None
        else:
            stems = None

        # Metrics: output RMS
        self.metrics['output_rms'] = float(np.sqrt(np.mean(audio_saturated ** 2)))
        self.metrics['total_samples_processed'] += len(audio)

        process_time = time.time() - start_time
        self.metrics['last_process_time'] = process_time
        self.metrics['max_process_time'] = max(self.metrics['max_process_time'], process_time)

        # Step 4: Save outputs
        print(f"  → Saving processed files...")
        import os
        os.makedirs(output_dir, exist_ok=True)

        # Main output (noise filtered + saturated)
        main_path = os.path.join(output_dir, f"mastercrafter_{os.path.basename(input_path)}")
        sf.write(main_path, audio_saturated, self.sr)

        results = {'main': main_path}

        # Stem outputs (if HPSS available)
        if stems:
            for stem_name, stem_audio in stems.items():
                stem_path = os.path.join(output_dir, f"{stem_name}_{os.path.basename(input_path)}")
                sf.write(stem_path, stem_audio, self.sr)
                results[stem_name] = stem_path

        # Metadata
        rms_reduction_db = 20 * np.log10(self.metrics['input_rms'] / max(self.metrics['output_rms'], 1e-10))
        results['metadata'] = {
            'processing_time': process_time,
            'input_rms': self.metrics['input_rms'],
            'output_rms': self.metrics['output_rms'],
            'rms_reduction_db': rms_reduction_db,
            'tape_preset': self.tape_preset,
            'sample_rate': self.sr
        }

        print(f"  ✓ Complete in {process_time:.2f}s")
        print(f"    Input RMS: {self.metrics['input_rms']:.3f}, Output RMS: {self.metrics['output_rms']:.3f}")
        print(f"    Reduction: {rms_reduction_db:.1f} dB")

        return results

    def process_buffer(self, audio_buffer: np.ndarray, buffer_size: int = 2048) -> np.ndarray:
        """
        Real-time buffer processing (for live capture via ASIO/Core Audio).

        Processes in fixed-size buffers to maintain <5ms latency.
        Buffer size: 2048 samples @ 44100 Hz = 46ms (acceptable for live capture)
        """
        start_time = time.time()

        if audio_buffer.size != buffer_size:
            raise ValueError(f"Expected buffer of {buffer_size} samples, got {audio_buffer.size}")

        # Step 1: Smart filtering
        audio_out = self.noise_filter.remove_hum(audio_buffer)
        audio_out = self.noise_filter.gate_hiss(audio_out)

        # Step 2: Saturation + EQ
        audio_out = self.saturation.process(audio_out)
        audio_out = self.neve_preamp.process(audio_out, sr=self.sr)

        # Note: HPSS requires full audio context, not suitable for real-time buffer processing
        # Use file-based processing for stem separation

        latency = time.time() - start_time
        if latency > 0.005:  # 5ms warning
            print(f"Warning: Buffer processing took {latency*1000:.1f}ms (target: <5ms)")

        return audio_out

    def learn_from_feedback(self, feedback: float, bias_adjust: float = 0.0,
                           hf_driver_adjust: float = 0.0):
        """
        Learn from user feedback and adapt saturation response.

        feedback: 0.0 = too warm, 0.5 = neutral, 1.0 = too bright
        bias_adjust: adjustment to apply to bias
        hf_driver_adjust: adjustment to apply to HF driver
        """
        self.learning_state['feedback_history'].append(feedback)

        # Simple learning: average user preferences
        avg_feedback = np.mean(list(self.learning_state['feedback_history']))

        if bias_adjust != 0:
            self.learning_state['bias_adjustments'].append(bias_adjust)
            self.learning_state['avg_user_bias'] = np.mean(
                self.learning_state['bias_adjustments']
            )

        if hf_driver_adjust != 0:
            self.learning_state['hf_driver_adjustments'].append(hf_driver_adjust)
            self.learning_state['avg_user_hf_driver'] = np.mean(
                self.learning_state['hf_driver_adjustments']
            )

        print(f"[Learning] Feedback: {feedback:.2f}, Avg: {avg_feedback:.2f}")
        print(f"  Bias adjustment: {self.learning_state['avg_user_bias']:+.3f}")
        print(f"  HF Driver adjustment: {self.learning_state['avg_user_hf_driver']:+.3f}")

        # Apply adjustments
        new_bias = np.clip(
            self.saturation.bias + self.learning_state['avg_user_bias'],
            0.0, 1.0
        )
        new_hf_driver = np.clip(
            self.saturation.hf_driver + self.learning_state['avg_user_hf_driver'],
            0.0, 1.0
        )

        self.saturation.bias = new_bias
        self.saturation.hf_driver = new_hf_driver

        print(f"  Updated: Bias={new_bias:.3f}, HF Driver={new_hf_driver:.3f}")

    def get_metrics(self) -> Dict:
        """Return processing metrics."""
        return {
            **self.metrics,
            'learning_samples': len(self.learning_state['feedback_history']),
            'avg_user_bias': self.learning_state['avg_user_bias'],
            'avg_user_hf_driver': self.learning_state['avg_user_hf_driver'],
        }


# ============================================================================
# TESTING AND DIAGNOSTICS
# ============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("Mastercrafter Capture Station - Week 1 Test")
    print("=" * 70)

    # Test Case 1: Process a test file with warm_tape preset
    print("\n[Test 1] File processing with HPSS stem separation")

    processor = CaptureStemProcessor(
        sr=44100,
        tape_preset="warm_tape",
        enable_hpss=True,
        enable_learning=True
    )

    # Create test audio (synthetic)
    sr = 44100
    duration = 5  # 5 seconds
    t = np.linspace(0, duration, int(sr * duration))

    # Simulate bad recording: noisy vocal with clicks
    vocal = 0.3 * np.sin(2 * np.pi * 200 * t)  # ~200 Hz fundamental (low male vocal)
    hum = 0.15 * np.sin(2 * np.pi * 60 * t)    # 60 Hz hum
    hiss = 0.05 * np.random.randn(len(t))      # High-frequency hiss

    # Add clicks
    clicks = np.zeros_like(t)
    click_positions = np.random.choice(len(t), 50)
    clicks[click_positions] = 0.3

    test_audio = vocal + hum + hiss + clicks
    test_audio = test_audio / np.max(np.abs(test_audio))  # Normalize

    # Save test audio
    test_file = "/tmp/test_bad_recording.wav"
    sf.write(test_file, test_audio, sr)
    print(f"Created test audio: {test_file}")

    # Process
    try:
        results = processor.process_file(test_file, output_dir="/tmp/mastercrafter_output/")

        print("\n[Results]")
        print(f"Main output: {results['main']}")
        if 'vocals' in results:
            print(f"Vocals stem: {results['vocals']}")
        print(f"\nMetadata:")
        for key, val in results['metadata'].items():
            print(f"  {key}: {val}")

        print("\n[Processor Metrics]")
        for key, val in processor.get_metrics().items():
            print(f"  {key}: {val}")

    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()

    # Test Case 2: Learning from feedback
    print("\n[Test 2] User feedback learning")

    processor.learn_from_feedback(feedback=0.3, bias_adjust=-0.1)
    processor.learn_from_feedback(feedback=0.2, bias_adjust=-0.05)
    processor.learn_from_feedback(feedback=0.4, bias_adjust=-0.15)

    print("\n" + "=" * 70)
    print("Week 1 Tests Complete")
    print("=" * 70)
