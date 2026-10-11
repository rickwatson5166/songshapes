#!/usr/bin/env python3
"""
Mastercrafter Stage 3 Orchestrator
Convert accompaniment data to audio waveforms
Synthesize drums, bass, pads and mix into final accompaniment audio
"""

import numpy as np
import soundfile as sf
from mastercrafter_drum_synthesizer import DrumSynthesizer
from mastercrafter_bass_synthesizer import BassSynthesizer
from mastercrafter_pad_synthesizer import PadSynthesizer


class Stage3AudioSynthesis:
    """Complete Stage 3: Convert accompaniment data to audio"""

    def __init__(self, sr=44100):
        self.sr = sr
        self.drum_synthesizer = DrumSynthesizer(sr=sr)
        self.bass_synthesizer = BassSynthesizer(sr=sr)
        self.pad_synthesizer = PadSynthesizer(sr=sr)

    def synthesize_accompaniment(self, accompaniment_data, verbosity=1):
        """
        Synthesize complete accompaniment from accompaniment data.

        Input: Dict from Stage 2 with:
            - bass: bass line data
            - drums: drum pattern data
            - pads: pad voicing data
            - tempo: tempo info
            - key: key info
            - style: style info
            - duration_seconds: total duration (optional, inferred from accompaniment)

        Output: Dict with audio tracks and mixed accompaniment
        """

        if verbosity >= 1:
            print("\n╔════════════════════════════════════════════════╗")
            print("║  STAGE 3: AUDIO SYNTHESIS                     ║")
            print("╚════════════════════════════════════════════════╝\n")

        # Extract accompaniment components
        bass_data = accompaniment_data.get('bass', {})
        drum_data = accompaniment_data.get('drums', {})
        pad_data = accompaniment_data.get('pads', {})
        tempo_info = accompaniment_data.get('tempo', {'tempo_bpm': 120})
        key_info = accompaniment_data.get('key', {'key': 'C major'})

        tempo_bpm = tempo_info.get('tempo_bpm', 120)

        # Calculate duration from accompaniment timing
        duration_seconds = self._calculate_duration(bass_data, drum_data, pad_data)

        if verbosity >= 1:
            print(f"Duration: {duration_seconds:.2f}s")
            print(f"Tempo: {tempo_bpm} BPM")
            print(f"Key: {key_info.get('key', 'Unknown')}")

        # ─────────────────────────────────────────────────
        # Step 1: Synthesize Drums
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 1: Drum Synthesis")
            print("─" * 50)

        drum_result = self.drum_synthesizer.synthesize_drum_pattern(
            drum_data, duration_seconds, tempo_bpm
        )

        if verbosity >= 1:
            print(f"✓ Drums synthesized:")
            print(f"  {len(drum_data.get('kick', {}).get('timing', []))} kicks")
            print(f"  {len(drum_data.get('snare', {}).get('timing', []))} snares")
            print(f"  {len(drum_data.get('hi_hat', {}).get('timing', []))} hi-hats")

        # ─────────────────────────────────────────────────
        # Step 2: Synthesize Bass
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 2: Bass Synthesis")
            print("─" * 50)

        bass_result = self.bass_synthesizer.synthesize_bass_line(
            bass_data, duration_seconds, tempo_bpm
        )

        if verbosity >= 1:
            print(f"✓ Bass synthesized:")
            print(f"  {bass_result['num_notes']} notes")

        # ─────────────────────────────────────────────────
        # Step 3: Synthesize Pads
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 3: Pad Synthesis")
            print("─" * 50)

        pad_result = self.pad_synthesizer.synthesize_pad_voicing(
            pad_data, duration_seconds, tempo_bpm
        )

        if verbosity >= 1:
            print(f"✓ Pads synthesized:")
            print(f"  {pad_result['num_voices']} voices")

        # ─────────────────────────────────────────────────
        # Step 4: Mix Tracks
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 4: Mixing")
            print("─" * 50)

        # Get audio from each synthesizer
        drum_audio = drum_result['combined_audio']
        bass_audio = bass_result['audio']
        pad_audio = pad_result['audio']

        # Ensure all have same length
        max_len = max(len(drum_audio), len(bass_audio), len(pad_audio))

        drum_audio = np.pad(drum_audio, (0, max_len - len(drum_audio)))
        bass_audio = np.pad(bass_audio, (0, max_len - len(bass_audio)))
        pad_audio = np.pad(pad_audio, (0, max_len - len(pad_audio)))

        # Mix with level balance
        # Drums are most prominent, bass second, pads subtle background
        mixed_audio = (
            0.7 * drum_audio +      # Drums: prominent
            0.6 * bass_audio +      # Bass: strong
            0.2 * pad_audio         # Pads: subtle background
        )

        # Normalize to prevent clipping
        max_val = np.abs(mixed_audio).max()
        if max_val > 0:
            mixed_audio = 0.95 * mixed_audio / max_val

        if verbosity >= 1:
            print(f"✓ Mixed audio:")
            print(f"  Drum level: 0.7")
            print(f"  Bass level: 0.6")
            print(f"  Pad level: 0.2")
            print(f"  Mixed peak: {np.abs(mixed_audio).max():.3f}")

        # ─────────────────────────────────────────────────
        # Compile result
        # ─────────────────────────────────────────────────

        result = {
            'drums': {
                'audio': drum_audio,
                'description': drum_result['description']
            },
            'bass': {
                'audio': bass_audio,
                'description': bass_result['description']
            },
            'pads': {
                'audio': pad_audio,
                'description': pad_result['description']
            },
            'mixed': {
                'audio': mixed_audio,
                'description': 'Mixed drums + bass + pads'
            },
            'sr': self.sr,
            'duration_seconds': duration_seconds,
            'tempo_bpm': tempo_bpm,
            'key': key_info.get('key', 'Unknown')
        }

        if verbosity >= 1:
            print("\n" + "="*50)
            print("STAGE 3 COMPLETE: Audio Synthesis")
            print("="*50)
            print(f"\nOutput:")
            print(f"  Duration: {duration_seconds:.2f}s")
            print(f"  Sample rate: {self.sr} Hz")
            print(f"  Drums: {len(drum_audio)} samples")
            print(f"  Bass: {len(bass_audio)} samples")
            print(f"  Pads: {len(pad_audio)} samples")
            print(f"  Mixed: {len(mixed_audio)} samples")
            print(f"\nReady to mix with original recording or export")

        return result

    def _calculate_duration(self, bass_data, drum_data, pad_data):
        """Calculate duration from accompaniment timing"""

        max_time = 0.0

        # Check bass timing
        bass_timing = bass_data.get('timing', [])
        bass_durations = bass_data.get('durations', [])
        if len(bass_timing) > 0 and len(bass_durations) > 0:
            max_time = max(max_time, bass_timing[-1] + bass_durations[-1])

        # Check drum timing
        combined_timing = drum_data.get('combined', {}).get('timing', [])
        if len(combined_timing) > 0:
            # Assume drums last ~0.5 seconds after last hit
            max_time = max(max_time, combined_timing[-1] + 0.5)

        # Check pad timing
        pad_timing = pad_data.get('combined', {}).get('timing', [])
        pad_durations = pad_data.get('combined', {}).get('durations', [])
        if len(pad_timing) > 0 and len(pad_durations) > 0:
            max_time = max(max_time, pad_timing[-1] + pad_durations[-1])

        # Minimum 2 seconds, reasonable maximum
        return max(2.0, min(max_time, 30.0))

    def export_accompaniment(self, result, output_format='wav', output_file=None):
        """
        Export accompaniment to audio file.

        Args:
            result: output from synthesize_accompaniment()
            output_format: 'wav', 'mp3', or 'flac'
            output_file: path to save (if None, creates temp file)

        Returns:
            path to saved file
        """

        if output_file is None:
            output_file = f'/tmp/accompaniment_{output_format}.{output_format}'

        # Export mixed track
        mixed_audio = result['mixed']['audio']
        sr = result['sr']

        sf.write(output_file, mixed_audio, sr, subtype='PCM_16')

        return output_file

    def export_stems(self, result, output_dir='/tmp'):
        """
        Export individual stems (drums, bass, pads) as separate files.

        Args:
            result: output from synthesize_accompaniment()
            output_dir: directory to save stems

        Returns:
            dict with paths to each stem
        """

        sr = result['sr']

        stems = {}

        # Drums
        drum_file = f'{output_dir}/accompaniment_drums.wav'
        sf.write(drum_file, result['drums']['audio'], sr, subtype='PCM_16')
        stems['drums'] = drum_file

        # Bass
        bass_file = f'{output_dir}/accompaniment_bass.wav'
        sf.write(bass_file, result['bass']['audio'], sr, subtype='PCM_16')
        stems['bass'] = bass_file

        # Pads
        pad_file = f'{output_dir}/accompaniment_pads.wav'
        sf.write(pad_file, result['pads']['audio'], sr, subtype='PCM_16')
        stems['pads'] = pad_file

        # Mixed
        mixed_file = f'{output_dir}/accompaniment_mixed.wav'
        sf.write(mixed_file, result['mixed']['audio'], sr, subtype='PCM_16')
        stems['mixed'] = mixed_file

        return stems


# ─────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────

def create_test_accompaniment_data():
    """Create synthetic accompaniment data for testing"""

    import numpy as np

    # Simulate Stage 2 output
    beat_interval = 0.5  # 120 BPM

    # Bass
    bass_data = {
        'notes': [36, 36, 41, 41, 43, 43],
        'timing': [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        'dynamics': [0.7, 0.6, 0.7, 0.6, 0.7, 0.6],
        'durations': [0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
    }

    # Drums
    kick_timing = []
    kick_dynamics = []
    for measure in range(4):
        kick_timing.extend([
            measure * 2 + 0 * beat_interval,
            measure * 2 + 1.5 * beat_interval,
            measure * 2 + 2 * beat_interval,
            measure * 2 + 3.5 * beat_interval
        ])
        kick_dynamics.extend([0.85, 0.65, 0.85, 0.65])

    snare_timing = []
    snare_dynamics = []
    for measure in range(4):
        snare_timing.extend([
            measure * 2 + 1 * beat_interval,
            measure * 2 + 3 * beat_interval
        ])
        snare_dynamics.extend([0.8, 0.8])

    hi_hat_timing = []
    hi_hat_dynamics = []
    for measure in range(4):
        for beat in range(4):
            for eighth in range(2):
                hi_hat_timing.append(measure * 2 + beat * beat_interval + eighth * beat_interval / 2)
                hi_hat_dynamics.append(0.6 + np.random.rand() * 0.2)

    drum_data = {
        'kick': {
            'notes': [36] * len(kick_timing),
            'timing': kick_timing,
            'dynamics': kick_dynamics,
            'durations': [0.15] * len(kick_timing)
        },
        'snare': {
            'notes': [38] * len(snare_timing),
            'timing': snare_timing,
            'dynamics': snare_dynamics,
            'durations': [0.15] * len(snare_timing)
        },
        'hi_hat': {
            'notes': [42] * len(hi_hat_timing),
            'timing': hi_hat_timing,
            'dynamics': hi_hat_dynamics,
            'durations': [0.1] * len(hi_hat_timing)
        },
        'combined': {
            'notes': [36] * len(kick_timing) + [38] * len(snare_timing) + [42] * len(hi_hat_timing),
            'timing': kick_timing + snare_timing + hi_hat_timing,
            'dynamics': kick_dynamics + snare_dynamics + hi_hat_dynamics,
            'durations': [0.15] * len(kick_timing) + [0.15] * len(snare_timing) + [0.1] * len(hi_hat_timing)
        }
    }

    # Pads
    pad_notes = [48, 52, 55, 64, 67, 76] * 4
    pad_timing = []
    pad_dynamics = []
    pad_durations = []

    chord_starts = [0.0, 2.0, 4.0, 6.0]
    for chord_start in chord_starts:
        for voice_idx in range(6):
            pad_timing.append(chord_start)
            pad_dynamics.append(0.4 + (voice_idx / 6) * 0.2)
            pad_durations.append(2.1)

    pad_data = {
        'sustain': {'notes': [], 'timing': [], 'dynamics': [], 'durations': []},
        'arpeggio': {'notes': [], 'timing': [], 'dynamics': [], 'durations': []},
        'combined': {
            'notes': pad_notes,
            'timing': pad_timing,
            'dynamics': pad_dynamics,
            'durations': pad_durations
        }
    }

    accompaniment = {
        'bass': bass_data,
        'drums': drum_data,
        'pads': pad_data,
        'tempo': {'tempo_bpm': 120, 'time_signature': '4/4'},
        'key': {'key': 'C major'},
        'style': {'articulation': 'legato', 'timing': 'straight'}
    }

    return accompaniment


if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  STAGE 3 ORCHESTRATOR INTEGRATION TEST       ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test accompaniment data
    print("[Creating synthetic accompaniment data...]")
    accompaniment = create_test_accompaniment_data()

    # Run Stage 3
    orchestrator = Stage3AudioSynthesis(sr=44100)
    result = orchestrator.synthesize_accompaniment(accompaniment, verbosity=1)

    # Export stems
    print("\n" + "="*50)
    print("Exporting stems...")
    print("="*50)

    stems = orchestrator.export_stems(result)
    print(f"\n✓ Stems exported:")
    for stem_type, filepath in stems.items():
        print(f"  {stem_type}: {filepath}")

    print("\n✓ Stage 3 complete! Ready for mix with original recording")
