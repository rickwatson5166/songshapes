"""
Celery Task Definitions for SongShapes Phase 3A

Defines async tasks for:
- Melody extraction (F0 detection)
- Chord detection
- Accompaniment generation (bass + drums)

Each task emits progress updates via Celery state and WebSocket.
"""

from celery import shared_task, current_task
from celery.exceptions import SoftTimeLimitExceeded
import os
import tempfile
import numpy as np
import soundfile as sf

# Import Phase 2 modules
from melody_extractor import MelodyExtractor
from chord_detector import ChordDetector
from accompaniment_generator import AccompanimentGenerator
from drum_synthesizer import DrumSynthesizer
from bass_synthesizer import BassSynthesizer
from accompaniment_mixer import AccompanimentMixer

# Global sessions storage (shared with Flask app)
sessions = {}


def update_progress(current, total, message=""):
    """
    Update Celery task progress and log message

    Args:
        current: Current progress (0-100)
        total: Total steps (100)
        message: Progress message
    """
    task_id = current_task.request.id
    state = 'PROGRESS'
    meta = {
        'current': current,
        'total': total,
        'percentage': int((current / total) * 100),
        'message': message,
        'task_id': task_id,
    }
    current_task.update_state(state=state, meta=meta)
    print(f"[{task_id}] {current}/{total}: {message}")


@shared_task(bind=True, name='celery_tasks.extract_melody_task')
def extract_melody_task(self, session_id, use_vocals_stem=True):
    """
    Extract F0 contour (melody) from vocals

    Args:
        session_id: Session identifier
        use_vocals_stem: Use vocals stem if available

    Returns:
        dict: {
            'f0_mean': float,
            'voicing_ratio': float,
            'num_frames': int,
            'f0_contour': list,
            'confidence': list,
            'times': list,
            'status': 'success',
            'message': str
        }
    """
    try:
        update_progress(10, 100, "Loading audio...")

        # Get session and audio path
        if session_id not in sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = sessions[session_id]

        # Get vocals stem or original audio
        if use_vocals_stem and 'stems' in session and 'vocals' in session['stems']:
            audio_path = session['stems']['vocals']
        else:
            audio_path = session['audio_path']

        # Load audio
        audio_data, sr = sf.read(audio_path)
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)  # Convert to mono

        update_progress(30, 100, "Computing STFT and autocorrelation...")

        # Extract melody using MelodyExtractor
        extractor = MelodyExtractor(sr=sr)
        f0_contour, confidence, times = extractor.extract_f0(audio_data)

        update_progress(70, 100, "Computing statistics...")

        # Get melody notes
        notes = extractor.get_melody_note_sequence(f0_contour, confidence)

        # Compute statistics
        voiced_frames = confidence > 0.5
        f0_mean = np.mean(f0_contour[voiced_frames]) if np.any(voiced_frames) else 0.0
        voicing_ratio = np.sum(voiced_frames) / len(confidence) if len(confidence) > 0 else 0.0
        num_frames = len(f0_contour)

        # Store in session
        session['f0_contour'] = f0_contour.tolist()
        session['confidence'] = confidence.tolist()
        session['times'] = times.tolist()
        session['melody_notes'] = notes
        session['status'] = 'melody_extracted'

        update_progress(95, 100, "Finalizing results...")

        result = {
            'f0_mean': float(f0_mean),
            'voicing_ratio': float(voicing_ratio),
            'num_frames': int(num_frames),
            'f0_contour': f0_contour.tolist()[:100],  # First 100 for preview
            'confidence': confidence.tolist()[:100],
            'times': times.tolist()[:100],
            'status': 'success',
            'message': f"Extracted melody: {f0_mean:.1f}Hz (voiced: {voicing_ratio*100:.1f}%)"
        }

        update_progress(100, 100, "Complete!")
        return result

    except SoftTimeLimitExceeded:
        return {
            'status': 'error',
            'message': 'Melody extraction timed out (>25 minutes)',
            'error': 'TIMEOUT'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Melody extraction failed: {str(e)}',
            'error': type(e).__name__
        }


@shared_task(bind=True, name='celery_tasks.detect_chords_task')
def detect_chords_task(self, session_id, use_vocals_stem=True):
    """
    Detect chord progression from vocals

    Args:
        session_id: Session identifier
        use_vocals_stem: Use vocals stem if available

    Returns:
        dict: {
            'chords': [
                {
                    'root': str,
                    'quality': str,
                    'start_time': float,
                    'end_time': float,
                    'duration': float,
                    'confidence': float
                },
                ...
            ],
            'num_chords': int,
            'status': 'success',
            'message': str
        }
    """
    try:
        update_progress(10, 100, "Loading audio...")

        # Get session and audio path
        if session_id not in sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = sessions[session_id]

        # Get vocals stem or original audio
        if use_vocals_stem and 'stems' in session and 'vocals' in session['stems']:
            audio_path = session['stems']['vocals']
        else:
            audio_path = session['audio_path']

        # Load audio
        audio_data, sr = sf.read(audio_path)
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        update_progress(40, 100, "Extracting chromagram...")

        # Detect chords using ChordDetector
        detector = ChordDetector(sr=sr)
        chords = detector.detect_chords(audio_data)

        update_progress(80, 100, "Smoothing chord progressions...")

        # Store in session
        session['chords'] = chords
        session['status'] = 'chords_detected'

        update_progress(95, 100, "Finalizing results...")

        result = {
            'chords': chords,
            'num_chords': len(chords),
            'status': 'success',
            'message': f"Detected {len(chords)} chord changes"
        }

        update_progress(100, 100, "Complete!")
        return result

    except SoftTimeLimitExceeded:
        return {
            'status': 'error',
            'message': 'Chord detection timed out (>25 minutes)',
            'error': 'TIMEOUT'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Chord detection failed: {str(e)}',
            'error': type(e).__name__
        }


@shared_task(bind=True, name='celery_tasks.generate_accompaniment_task')
def generate_accompaniment_task(self, session_id, tempo_bpm=120, key="C", character_config=None):
    """
    Generate bass + drums accompaniment

    Args:
        session_id: Session identifier
        tempo_bpm: Tempo in beats per minute
        key: Musical key (C, D, E, etc.)
        character_config: dict with bass and drums effect settings

    Returns:
        dict: {
            'accompaniment_stems': {
                'bass': path,
                'drums': path,
                'mix': path
            },
            'metadata': {
                'tempo_bpm': int,
                'key': str,
                'num_bass_notes': int,
                'num_drum_events': int,
                'articulation': str
            },
            'status': 'success',
            'message': str
        }
    """
    try:
        update_progress(10, 100, "Loading audio and melody data...")

        # Get session
        if session_id not in sessions:
            raise ValueError(f"Session not found: {session_id}")

        session = sessions[session_id]

        # Verify prerequisites
        if 'f0_contour' not in session:
            raise ValueError("Melody not extracted. Call extract-melody first.")
        if 'chords' not in session:
            raise ValueError("Chords not detected. Call detect-chords first.")

        # Get vocals stem
        if 'stems' not in session or 'vocals' not in session['stems']:
            raise ValueError("Vocals stem not found")

        audio_data, sr = sf.read(session['stems']['vocals'])
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        update_progress(25, 100, "Generating bass line...")

        # Generate accompaniment patterns
        generator = AccompanimentGenerator()
        accompaniment = generator.generate_accompaniment(
            chords=session['chords'],
            tempo_bpm=tempo_bpm,
            key=key
        )

        update_progress(40, 100, "Synthesizing drums...")

        # Synthesize drums
        drum_synth = DrumSynthesizer(sr=sr)
        drums_audio = drum_synth.synthesize_drum_track(
            drum_pattern=accompaniment['drum_events'],
            tempo_bpm=tempo_bpm,
            duration=len(audio_data) / sr
        )

        update_progress(60, 100, "Synthesizing bass...")

        # Synthesize bass
        bass_synth = BassSynthesizer(sr=sr)
        bass_audio = bass_synth.synthesize_bass_track(
            notes=accompaniment['bass_notes'],
            chords=session['chords']
        )

        update_progress(80, 100, "Mixing and applying effects...")

        # Mix and apply character effects
        mixer = AccompanimentMixer(sr=sr)
        mix_audio = mixer.mix_tracks(
            vocals=audio_data,
            bass=bass_audio,
            drums=drums_audio
        )

        # Apply character effects if provided
        if character_config:
            if 'bass' in character_config:
                bass_audio = mixer.process_stem(
                    bass_audio,
                    **character_config['bass']
                )
            if 'drums' in character_config:
                drums_audio = mixer.process_stem(
                    drums_audio,
                    **character_config['drums']
                )

        update_progress(90, 100, "Saving audio files...")

        # Save stems
        output_dir = os.path.join(tempfile.gettempdir(), f'songshapes_{session_id}')
        os.makedirs(output_dir, exist_ok=True)

        bass_path = os.path.join(output_dir, 'accompaniment_bass.wav')
        drums_path = os.path.join(output_dir, 'accompaniment_drums.wav')
        mix_path = os.path.join(output_dir, 'accompaniment_mix.wav')

        sf.write(bass_path, bass_audio, sr)
        sf.write(drums_path, drums_audio, sr)
        sf.write(mix_path, mix_audio, sr)

        # Update session
        session['accompaniment_stems'] = {
            'bass': bass_path,
            'drums': drums_path,
            'mix': mix_path
        }
        session['status'] = 'accompaniment_generated'

        update_progress(100, 100, "Complete!")

        result = {
            'accompaniment_stems': session['accompaniment_stems'],
            'metadata': {
                'tempo_bpm': tempo_bpm,
                'key': key,
                'num_bass_notes': len(accompaniment['bass_notes']),
                'num_drum_events': len(accompaniment['drum_events']),
                'articulation': accompaniment.get('articulation', 'legato')
            },
            'status': 'success',
            'message': 'Generated bass + drums accompaniment'
        }

        return result

    except SoftTimeLimitExceeded:
        return {
            'status': 'error',
            'message': 'Accompaniment generation timed out (>25 minutes)',
            'error': 'TIMEOUT'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Accompaniment generation failed: {str(e)}',
            'error': type(e).__name__
        }
