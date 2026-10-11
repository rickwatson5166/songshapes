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

app = Flask(__name__, template_folder='templates')
app.secret_key = 'songshapes_secret_key_2026'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Allowed file types
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'ogg', 'm4a'}

# Global processor sessions
PROCESSOR_SESSIONS = {}


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
            'message': ''
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


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'SongShapes',
        'version': '0.1.0-alpha',
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
# CLI Entry Point
# ============================================================================

if __name__ == '__main__':
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    print(f"""
╭─────────────────────────────────────────────────────╮
│  SongShapes Audio Regeneration System               │
│  Theory-trained stem separation + character effects │
╭─────────────────────────────────────────────────────╯
│
│  🎵 Running on: http://localhost:{port}
│  📁 Temp folder: {app.config['UPLOAD_FOLDER']}
│  ⚙️  Max upload: 100MB
│
│  Usage:
│    1. Upload audio file
│    2. Separate into stems (Vocal, Drums, Bass/Pads)
│    3. Regenerate with character effects
│    4. Download stems + master mix
│
│  Press Ctrl+C to stop
│
╭─────────────────────────────────────────────────────╮
    """)

    app.run(
        debug=True,
        host='localhost',
        port=port,
        use_reloader=True
    )
