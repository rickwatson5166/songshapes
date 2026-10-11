#!/usr/bin/env python3
"""
SongShapes Flask Application
Web UI for audio regeneration, stem separation, and accompaniment generation

Run: python3 app.py
Open: http://localhost:5000
"""

import os
import json
import tempfile
import uuid
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify, session
from werkzeug.utils import secure_filename
from audio_processor import AudioProcessor
import numpy as np
import soundfile as sf

# Phase 2 imports
try:
    from melody_extractor import MelodyExtractor
    from chord_detector import ChordDetector
    from accompaniment_generator import AccompanimentGenerator
    from drum_synthesizer import DrumSynthesizer
    from bass_synthesizer import BassSynthesizer
    from accompaniment_mixer import AccompanimentMixer
    PHASE2_AVAILABLE = True
except ImportError:
    PHASE2_AVAILABLE = False
    print("⚠️  Warning: Phase 2 modules not available. Some features will be disabled.")

# Phase 3A imports (Async processing)
PHASE3A_AVAILABLE = False
try:
    from flask_socketio import SocketIO, emit
    from celery import Celery
    from celery.result import AsyncResult
    from celery_config import celery
    import celery_tasks
    PHASE3A_AVAILABLE = True
except ImportError:
    PHASE3A_AVAILABLE = False
    print("⚠️  Warning: Phase 3A modules (Celery, Redis, SocketIO) not available. Async processing disabled.")

app = Flask(__name__, template_folder='templates')
app.secret_key = 'songshapes_secret_key_2026'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Initialize SocketIO for async progress updates
socketio = None
if PHASE3A_AVAILABLE:
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Allowed file types
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'ogg', 'm4a'}

# Global processor sessions (shared with Celery tasks)
PROCESSOR_SESSIONS = {}

# Make sessions available to celery_tasks module
if PHASE3A_AVAILABLE:
    celery_tasks.sessions = PROCESSOR_SESSIONS


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_session_processor(session_id):
    """Get or create processor for session"""
    if session_id not in PROCESSOR_SESSIONS:
        PROCESSOR_SESSIONS[session_id] = {
            'processor': AudioProcessor(),
            'audio_path': None,
            'output_dir': None,
            'stems': {},
            'status': 'ready',
            'message': '',
            # Phase 2 data
            'vocals_stem_path': None,
            'f0_contour': None,
            'confidence': None,
            'times': None,
            'chords': None,
            'accompaniment': None,
            'accompaniment_stems': {},
        }
    return PROCESSOR_SESSIONS[session_id]


# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def index():
    """Serve main UI"""
    return render_template('songshapes.html')


@app.route('/api/upload', methods=['POST'])
def upload_audio():
    """
    Handle audio file upload and process

    Returns:
        {
            'status': 'success' | 'error',
            'session_id': uuid,
            'duration': float (seconds),
            'sample_rate': int,
            'message': str
        }
    """
    try:
        # Check file was uploaded
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'status': 'error', 'message': f'File type not allowed. Use: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

        # Generate session ID
        session_id = str(uuid.uuid4())[:8]

        # Save uploaded file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{filename}")
        file.save(upload_path)

        # Get processor
        sess = get_session_processor(session_id)
        sess['audio_path'] = upload_path

        # Load and analyze audio
        processor = sess['processor']
        try:
            audio, sr = processor.load_audio(upload_path)

            sess['status'] = 'loaded'
            sess['message'] = 'Audio loaded successfully'

            return jsonify({
                'status': 'success',
                'session_id': session_id,
                'duration': len(audio) / sr,
                'sample_rate': sr,
                'message': 'Audio uploaded successfully'
            })

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to load audio: {str(e)}'
            }), 400

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Upload failed: {str(e)}'
        }), 500


@app.route('/api/separate', methods=['POST'])
def separate_stems():
    """
    Separate audio into stems (vocal, drums, bass/pads)

    Request:
        {
            'session_id': str,
            'character_config': { optional character settings }
        }

    Returns:
        {
            'status': 'success' | 'error',
            'stems': { 'vocals': path, 'percussion': path, ... },
            'message': str
        }
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        character_config = data.get('character_config')

        if not session_id or session_id not in PROCESSOR_SESSIONS:
            return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

        sess = get_session_processor(session_id)

        if not sess['audio_path']:
            return jsonify({'status': 'error', 'message': 'No audio loaded'}), 400

        # Create output directory
        output_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"songshapes_{session_id}")
        os.makedirs(output_dir, exist_ok=True)
        sess['output_dir'] = output_dir

        # Run processing pipeline
        processor = sess['processor']
        result = processor.process_full_pipeline(
            sess['audio_path'],
            output_dir,
            character_config=character_config
        )

        if result['status'] == 'success':
            sess['stems'] = result['stems']
            sess['status'] = 'separated'
            sess['message'] = result['message']

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Separation failed: {str(e)}'
        }), 500


@app.route('/api/state', methods=['GET'])
def get_state():
    """
    Get current processing state

    Query params:
        session_id: str

    Returns:
        {
            'status': str,
            'message': str,
            'stems': { stem_name: path },
            'audio_loaded': bool,
            'stems_ready': bool
        }
    """
    session_id = request.args.get('session_id')

    if not session_id or session_id not in PROCESSOR_SESSIONS:
        return jsonify({
            'status': 'error',
            'message': 'No active session',
            'audio_loaded': False,
            'stems_ready': False
        })

    sess = get_session_processor(session_id)

    return jsonify({
        'status': sess['status'],
        'message': sess['message'],
        'stems': sess['stems'],
        'audio_loaded': bool(sess['audio_path']),
        'stems_ready': bool(sess['stems'])
    })


@app.route('/api/download/<stem_name>/<session_id>', methods=['GET'])
def download_stem(stem_name, session_id):
    """Download processed stem"""
    try:
        if session_id not in PROCESSOR_SESSIONS:
            return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

        sess = get_session_processor(session_id)
        stems = sess['stems']

        if stem_name not in stems:
            return jsonify({'status': 'error', 'message': f'Stem not found: {stem_name}'}), 404

        stem_path = stems[stem_name]

        if not os.path.exists(stem_path):
            return jsonify({'status': 'error', 'message': 'Stem file not found'}), 404

        return send_file(
            stem_path,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=f'{session_id}_{stem_name}.wav'
        )

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/regenerate', methods=['POST'])
def regenerate_stems():
    """
    Regenerate stems with character effects applied

    Request:
        {
            'session_id': str,
            'character_config': {
                'vocals': {'eq_low': float, 'eq_mid': float, 'eq_high': float, 'compression': float, 'saturation': float, 'reverb': float},
                'percussion': {...},
                'bass_pads': {...}
            }
        }

    Returns:
        {
            'status': 'success' | 'error',
            'stems': { 'vocals': path, 'percussion': path, ... },
            'message': str
        }
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        character_config = data.get('character_config')

        if not session_id or session_id not in PROCESSOR_SESSIONS:
            return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

        sess = get_session_processor(session_id)

        if not sess['audio_path']:
            return jsonify({'status': 'error', 'message': 'No audio loaded'}), 400

        if not sess['stems']:
            return jsonify({'status': 'error', 'message': 'Audio not yet separated. Separate stems first.'}), 400

        # Convert character_config from frontend format to processor format
        # Frontend sends: { stem_name: { 'eq_low': val, ... } }
        # Processor expects: { stem_name: { 'eq_low': val, ... } }
        # They match! No conversion needed.

        # Re-run processing pipeline with new character config
        processor = sess['processor']
        result = processor.process_full_pipeline(
            sess['audio_path'],
            sess['output_dir'],
            character_config=character_config
        )

        if result['status'] == 'success':
            sess['stems'] = result['stems']
            sess['message'] = result['message']

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Regeneration failed: {str(e)}'
        }), 500


# ============================================================================
# Phase 2: Accompaniment Generation Endpoints
# ============================================================================

@app.route('/api/extract-melody', methods=['POST'])
def extract_melody():
    """
    Extract F0 (fundamental frequency) from vocals stem

    Request:
        {
            'session_id': str,
            'use_vocals_stem': bool (default: use separated vocals if available, else original audio)
        }

    Returns:
        {
            'status': 'success' | 'error',
            'f0_mean': float (Hz, mean of voiced frames),
            'voicing_ratio': float (0-1, fraction of voiced frames),
            'num_frames': int,
            'message': str
        }
    """
    if not PHASE2_AVAILABLE:
        return jsonify({'status': 'error', 'message': 'Phase 2 modules not available'}), 501

    try:
        data = request.get_json()
        session_id = data.get('session_id')
        use_vocals_stem = data.get('use_vocals_stem', True)

        if not session_id or session_id not in PROCESSOR_SESSIONS:
            return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

        sess = get_session_processor(session_id)

        # Determine which audio to extract F0 from
        if use_vocals_stem and sess['stems'] and 'vocals' in sess['stems']:
            audio_path = sess['stems']['vocals']
        elif sess['audio_path']:
            audio_path = sess['audio_path']
        else:
            return jsonify({'status': 'error', 'message': 'No audio loaded'}), 400

        # Load audio
        audio, sr = sf.read(audio_path)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Extract F0
        extractor = MelodyExtractor(sr=sr)
        f0_contour, confidence, times = extractor.extract_f0(audio)

        # Store in session
        sess['f0_contour'] = f0_contour
        sess['confidence'] = confidence
        sess['times'] = times
        sess['vocals_stem_path'] = audio_path

        # Compute statistics
        voiced_frames = f0_contour > 0
        f0_mean = np.mean(f0_contour[voiced_frames]) if np.any(voiced_frames) else 0
        voicing_ratio = np.sum(voiced_frames) / len(f0_contour)

        sess['status'] = 'melody_extracted'
        sess['message'] = f'Extracted melody: {f0_mean:.0f}Hz (voiced: {voicing_ratio*100:.1f}%)'

        return jsonify({
            'status': 'success',
            'f0_mean': float(f0_mean),
            'voicing_ratio': float(voicing_ratio),
            'num_frames': len(f0_contour),
            'message': sess['message']
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Melody extraction failed: {str(e)}'
        }), 500


@app.route('/api/detect-chords', methods=['POST'])
def detect_chords():
    """
    Detect chord progression from vocals stem

    Request:
        {
            'session_id': str,
            'use_vocals_stem': bool (default: true)
        }

    Returns:
        {
            'status': 'success' | 'error',
            'chords': [
                {'root': str, 'quality': str, 'start_time': float, 'duration': float, 'confidence': float},
                ...
            ],
            'message': str
        }
    """
    if not PHASE2_AVAILABLE:
        return jsonify({'status': 'error', 'message': 'Phase 2 modules not available'}), 501

    try:
        data = request.get_json()
        session_id = data.get('session_id')
        use_vocals_stem = data.get('use_vocals_stem', True)

        if not session_id or session_id not in PROCESSOR_SESSIONS:
            return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

        sess = get_session_processor(session_id)

        # Determine which audio to detect chords from
        if use_vocals_stem and sess['stems'] and 'vocals' in sess['stems']:
            audio_path = sess['stems']['vocals']
        elif sess['audio_path']:
            audio_path = sess['audio_path']
        else:
            return jsonify({'status': 'error', 'message': 'No audio loaded'}), 400

        # Load audio
        audio, sr = sf.read(audio_path)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Detect chords
        detector = ChordDetector(sr=sr)
        chords, times = detector.detect_chords(audio)

        # Store in session
        sess['chords'] = chords

        sess['status'] = 'chords_detected'
        sess['message'] = f'Detected {len(chords)} chord changes'

        return jsonify({
            'status': 'success',
            'chords': [
                {
                    'root': c['root'],
                    'quality': c['quality'],
                    'start_time': float(c['start_time']),
                    'end_time': float(c['end_time']),
                    'duration': float(c['duration']),
                    'confidence': float(c['confidence'])
                }
                for c in chords
            ],
            'message': sess['message']
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Chord detection failed: {str(e)}'
        }), 500


@app.route('/api/generate-accompaniment', methods=['POST'])
def generate_accompaniment():
    """
    Generate bass + drums accompaniment locked to melody and chords

    Request:
        {
            'session_id': str,
            'tempo_bpm': int (default: 120),
            'key': str (default: 'C'),
            'character_config': {
                'bass': {'eq_low': float, 'eq_mid': float, 'eq_high': float, 'compression': float, 'saturation': float, 'reverb': float},
                'drums': {...}
            } (optional)
        }

    Returns:
        {
            'status': 'success' | 'error',
            'accompaniment_stems': {
                'bass': path,
                'drums': path,
                'mix': path  (mix of all three: vocals + bass + drums)
            },
            'metadata': {
                'tempo_bpm': int,
                'key': str,
                'num_bass_notes': int,
                'num_drum_events': int,
                'articulation': str
            },
            'message': str
        }
    """
    if not PHASE2_AVAILABLE:
        return jsonify({'status': 'error', 'message': 'Phase 2 modules not available'}), 501

    try:
        data = request.get_json()
        session_id = data.get('session_id')
        tempo_bpm = data.get('tempo_bpm', 120)
        key = data.get('key', 'C')
        character_config = data.get('character_config', {})

        if not session_id or session_id not in PROCESSOR_SESSIONS:
            return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

        sess = get_session_processor(session_id)

        # Check if we have chords and F0 data
        if not sess['chords']:
            return jsonify({'status': 'error', 'message': 'No chords detected. Run detect-chords first.'}), 400

        if sess['f0_contour'] is None:
            return jsonify({'status': 'error', 'message': 'No melody extracted. Run extract-melody first.'}), 400

        # Load vocals
        if not sess['vocals_stem_path']:
            return jsonify({'status': 'error', 'message': 'No vocals stem available'}), 400

        vocals, sr = sf.read(sess['vocals_stem_path'])
        if vocals.ndim > 1:
            vocals = np.mean(vocals, axis=1)

        # Generate accompaniment
        melody_data = {
            'f0_contour': sess['f0_contour'],
            'confidence': sess['confidence']
        }

        acc_gen = AccompanimentGenerator(sr=sr)
        accompaniment = acc_gen.generate(melody_data, sess['chords'], tempo_bpm=tempo_bpm, key=key)

        # Synthesize
        drum_synth = DrumSynthesizer(sr=sr)
        bass_synth = BassSynthesizer(sr=sr)

        drums = drum_synth.synthesize_drum_track(accompaniment['drums'], total_duration=len(vocals)/sr)
        bass = bass_synth.synthesize_bass_track(accompaniment['bass'], total_duration=len(vocals)/sr)

        # Mix with character effects
        mixer = AccompanimentMixer(sr=sr)
        mix_dry = mixer.mix_accompaniment(vocals, bass, drums, levels={'vocals': 1.0, 'bass': 0.7, 'drums': 0.8})

        # Apply character effects if provided
        if character_config.get('bass'):
            bass = mixer.process_stem(bass, character_config['bass'])
        if character_config.get('drums'):
            drums = mixer.process_stem(drums, character_config['drums'])

        mix_final = mixer.mix_accompaniment(vocals, bass, drums, levels={'vocals': 1.0, 'bass': 0.7, 'drums': 0.8})

        # Save stems
        output_dir = sess['output_dir'] or os.path.join(app.config['UPLOAD_FOLDER'], f"songshapes_{session_id}")
        os.makedirs(output_dir, exist_ok=True)

        bass_path = os.path.join(output_dir, 'accompaniment_bass.wav')
        drums_path = os.path.join(output_dir, 'accompaniment_drums.wav')
        mix_path = os.path.join(output_dir, 'accompaniment_mix.wav')

        sf.write(bass_path, bass, sr)
        sf.write(drums_path, drums, sr)
        sf.write(mix_path, mix_final, sr)

        sess['accompaniment'] = accompaniment
        sess['accompaniment_stems'] = {
            'bass': bass_path,
            'drums': drums_path,
            'mix': mix_path
        }

        sess['status'] = 'accompaniment_generated'
        sess['message'] = 'Generated bass + drums accompaniment'

        return jsonify({
            'status': 'success',
            'accompaniment_stems': sess['accompaniment_stems'],
            'metadata': {
                'tempo_bpm': tempo_bpm,
                'key': key,
                'num_bass_notes': accompaniment['metadata']['num_bass_notes'],
                'num_drum_events': accompaniment['metadata']['num_drum_events'],
                'articulation': accompaniment['metadata']['articulation']
            },
            'message': sess['message']
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Accompaniment generation failed: {str(e)}'
        }), 500


@app.route('/api/download/accompaniment/<stem_name>/<session_id>', methods=['GET'])
def download_accompaniment(stem_name, session_id):
    """Download accompaniment stem (bass, drums, or mix)"""
    try:
        if session_id not in PROCESSOR_SESSIONS:
            return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

        sess = get_session_processor(session_id)
        accompaniment_stems = sess.get('accompaniment_stems', {})

        if stem_name not in accompaniment_stems:
            return jsonify({'status': 'error', 'message': f'Accompaniment stem not found: {stem_name}'}), 404

        stem_path = accompaniment_stems[stem_name]

        if not os.path.exists(stem_path):
            return jsonify({'status': 'error', 'message': 'Stem file not found'}), 404

        return send_file(
            stem_path,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=f'{session_id}_accompaniment_{stem_name}.wav'
        )

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'SongShapes',
        'version': '0.2.0-alpha',
        'phase1_available': True,
        'phase2_available': PHASE2_AVAILABLE,
        'active_sessions': len(PROCESSOR_SESSIONS)
    })


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(413)
def too_large(e):
    """Handle file too large"""
    return jsonify({
        'status': 'error',
        'message': 'File too large. Maximum 100MB.'
    }), 413


@app.errorhandler(404)
def not_found(e):
    """Handle 404"""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500"""
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500


# ============================================================================
# Phase 3A: Async Task Processing Endpoints
# ============================================================================

if PHASE3A_AVAILABLE:
    # WebSocket event handlers
    @socketio.on('connect')
    def handle_connect():
        """Client WebSocket connected"""
        print(f"[WebSocket] Client connected: {request.sid}")
        emit('connection_response', {
            'data': 'Connected to SongShapes async server',
            'sid': request.sid
        })

    @socketio.on('subscribe_task')
    def handle_subscribe(data):
        """Subscribe to task progress updates"""
        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'message': 'No task_id provided'})
            return

        # Send current task status
        result = AsyncResult(task_id, app=celery)

        if result.state == 'PENDING':
            state_data = {
                'state': 'PENDING',
                'current': 0,
                'total': 100,
                'percentage': 0,
                'message': 'Task queued...',
                'task_id': task_id
            }
        elif result.state == 'PROGRESS':
            state_data = result.info.copy()
            state_data['state'] = 'PROGRESS'
            state_data['task_id'] = task_id
        elif result.state == 'SUCCESS':
            state_data = {
                'state': 'SUCCESS',
                'current': 100,
                'total': 100,
                'percentage': 100,
                'message': 'Complete!',
                'result': result.result,
                'task_id': task_id
            }
        else:
            state_data = {
                'state': result.state,
                'message': str(result.info),
                'task_id': task_id
            }

        emit('task_status', state_data)

    @socketio.on('get_task_status')
    def handle_get_status(data):
        """Poll task status"""
        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'message': 'No task_id provided'})
            return

        result = AsyncResult(task_id, app=celery)

        if result.state == 'PENDING':
            state_data = {'state': 'PENDING', 'current': 0, 'total': 100, 'percentage': 0, 'message': 'Queued...', 'task_id': task_id}
        elif result.state == 'PROGRESS':
            state_data = result.info.copy()
            state_data['state'] = 'PROGRESS'
            state_data['task_id'] = task_id
        elif result.state == 'SUCCESS':
            state_data = {'state': 'SUCCESS', 'current': 100, 'total': 100, 'percentage': 100, 'result': result.result, 'task_id': task_id}
        else:
            state_data = {'state': result.state, 'message': str(result.info), 'task_id': task_id}

        emit('task_status', state_data)

    # Async API Endpoints
    @app.route('/api/extract-melody-async', methods=['POST'])
    def extract_melody_async():
        """
        Async version: Extract melody from vocals

        Returns task_id for polling/WebSocket subscription
        """
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            use_vocals_stem = data.get('use_vocals_stem', True)

            if not session_id or session_id not in PROCESSOR_SESSIONS:
                return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

            # Queue task
            task = celery_tasks.extract_melody_task.delay(session_id, use_vocals_stem)

            return jsonify({
                'status': 'queued',
                'task_id': task.id,
                'status_url': f'/api/task-status/{task.id}',
                'message': 'Melody extraction queued'
            })

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to queue task: {str(e)}'
            }), 500

    @app.route('/api/detect-chords-async', methods=['POST'])
    def detect_chords_async():
        """
        Async version: Detect chord progression

        Returns task_id for polling/WebSocket subscription
        """
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            use_vocals_stem = data.get('use_vocals_stem', True)

            if not session_id or session_id not in PROCESSOR_SESSIONS:
                return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

            # Queue task
            task = celery_tasks.detect_chords_task.delay(session_id, use_vocals_stem)

            return jsonify({
                'status': 'queued',
                'task_id': task.id,
                'status_url': f'/api/task-status/{task.id}',
                'message': 'Chord detection queued'
            })

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to queue task: {str(e)}'
            }), 500

    @app.route('/api/generate-accompaniment-async', methods=['POST'])
    def generate_accompaniment_async():
        """
        Async version: Generate accompaniment

        Returns task_id for polling/WebSocket subscription
        """
        try:
            data = request.get_json()
            session_id = data.get('session_id')
            tempo_bpm = data.get('tempo_bpm', 120)
            key = data.get('key', 'C')
            character_config = data.get('character_config')

            if not session_id or session_id not in PROCESSOR_SESSIONS:
                return jsonify({'status': 'error', 'message': 'Invalid session'}), 400

            # Queue task
            task = celery_tasks.generate_accompaniment_task.delay(
                session_id, tempo_bpm, key, character_config
            )

            return jsonify({
                'status': 'queued',
                'task_id': task.id,
                'status_url': f'/api/task-status/{task.id}',
                'message': 'Accompaniment generation queued'
            })

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to queue task: {str(e)}'
            }), 500

    @app.route('/api/task-status/<task_id>', methods=['GET'])
    def get_task_status(task_id):
        """Get current task status"""
        try:
            result = AsyncResult(task_id, app=celery)

            if result.state == 'PENDING':
                return jsonify({'state': 'PENDING', 'current': 0, 'total': 100, 'percentage': 0, 'message': 'Queued...'})
            elif result.state == 'PROGRESS':
                return jsonify(result.info)
            elif result.state == 'SUCCESS':
                return jsonify({'state': 'SUCCESS', 'current': 100, 'total': 100, 'percentage': 100, 'result': result.result})
            elif result.state == 'FAILURE':
                return jsonify({'state': 'FAILURE', 'message': str(result.info), 'error': True}), 500
            else:
                return jsonify({'state': result.state, 'message': str(result.info)})

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @app.route('/api/task-result/<task_id>', methods=['GET'])
    def get_task_result(task_id):
        """Get task result (blocks until complete)"""
        try:
            result = AsyncResult(task_id, app=celery)

            if result.state == 'SUCCESS':
                return jsonify({'status': 'success', 'result': result.result})
            elif result.state == 'FAILURE':
                return jsonify({'status': 'error', 'message': str(result.info)}), 500
            else:
                return jsonify({'status': result.state, 'message': 'Task not yet complete'}), 202

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    phase2_status = "✓ Phase 2 (Accompaniment Generation) ENABLED" if PHASE2_AVAILABLE else "✗ Phase 2 disabled"
    phase3a_status = "✓ Phase 3A (Async Processing) ENABLED" if PHASE3A_AVAILABLE else "⚠️  Phase 3A disabled (Celery/Redis not available)"

    print(f"""
╭─────────────────────────────────────────────────────╮
│  SongShapes Audio Regeneration System               │
│  Phase 1: Stem separation + character effects      │
│  Phase 2: Accompaniment generation (bass + drums)  │
│  Phase 3A: Async task processing (WebSocket)       │
╭─────────────────────────────────────────────────────╯
│
│  🎵 Running on: http://localhost:{port}
│  📁 Temp folder: {app.config['UPLOAD_FOLDER']}
│  ⚙️  Max upload: 100MB
│  📊 {phase2_status}
│  ⚡ {phase3a_status}
│
│  Usage:
│    Phase 1 (Stem Separation):
│      1. Upload audio file
│      2. Separate into stems (Vocal, Drums, Bass/Pads)
│      3. Regenerate with character effects
│      4. Download stems + master mix
│
│    Phase 2 (Accompaniment Generation):
│      1. Extract melody from vocals
│      2. Detect chord progression
│      3. Generate bass + drums accompaniment
│      4. Apply character effects
│      5. Download mixed track
│
│    Phase 3A (Async Processing):
│      - Use -async endpoints for non-blocking operations
│      - Subscribe to WebSocket for real-time progress updates
│      - Poll /api/task-status/<task_id> for progress
│
│  Celery Worker (if Phase 3A enabled):
│      celery -A celery_tasks worker --loglevel=info
│
│  Press Ctrl+C to stop
│
╭─────────────────────────────────────────────────────╮
    """)

    # Use SocketIO runner if Phase 3A available, else regular Flask
    if PHASE3A_AVAILABLE:
        socketio.run(
            app,
            debug=True,
            host='localhost',
            port=port,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    else:
        app.run(
            debug=True,
            host='localhost',
            port=port,
            use_reloader=True
        )
