#!/usr/bin/env python3
"""
Mastercrafter Web UI - Flask Backend
Handles file uploads, audio processing, and track management
"""

import os
import json
import tempfile
import numpy as np
import soundfile as sf
from flask import Flask, render_template, request, send_file, jsonify, session
from werkzeug.utils import secure_filename
from mastercrafter_performance_extractor import PerformanceExtractor
from mastercrafter_stage1_orchestrator import Stage1PerformanceUnderstanding
from mastercrafter_stage2_orchestrator import Stage2AccompanimentGeneration
from mastercrafter_stage3_orchestrator import Stage3AudioSynthesis

app = Flask(__name__)
app.secret_key = 'mastercrafter_secret'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Global state (in production, use database)
PROCESSING_STATE = {}


class AudioProcessor:
    """Handles the complete audio processing pipeline"""

    def __init__(self, session_id):
        self.session_id = session_id
        self.state = {
            'original_audio': None,
            'sr': None,
            'performance': None,
            'understanding': None,
            'accompaniment': None,
            'synthesis_result': None,
            'locked_tracks': [],  # Which tracks are locked
            'current_stage': 'upload'  # upload, analysis, drums, bass, pads, export
        }

    def process_upload(self, audio_path):
        """Process uploaded audio file"""

        # Load audio
        audio, sr = sf.read(audio_path)

        # Handle stereo → mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        self.state['original_audio'] = audio
        self.state['sr'] = sr
        self.state['current_stage'] = 'analysis'

        return {
            'status': 'success',
            'duration': len(audio) / sr,
            'sample_rate': sr
        }

    def analyze_performance(self):
        """Run Week 1 + Stage 1 analysis"""

        if self.state['original_audio'] is None:
            return {'status': 'error', 'message': 'No audio loaded'}

        # Week 1: Extract performance
        extractor = PerformanceExtractor(sr=self.state['sr'])
        performance = extractor.extract_full_performance(
            self.state['original_audio'],
            fmin=100,
            fmax=600
        )

        self.state['performance'] = performance

        # Stage 1: Understand performance
        orchestrator_s1 = Stage1PerformanceUnderstanding(
            sr=self.state['sr'],
            hop_length=512
        )
        understanding = orchestrator_s1.understand_performance(performance, verbosity=0)

        self.state['understanding'] = understanding

        return {
            'status': 'success',
            'analysis': {
                'key': understanding['key']['key'],
                'tempo': understanding['tempo']['tempo_bpm'],
                'time_signature': understanding['tempo']['time_signature'],
                'chords': understanding['chords']['chord_progression'][:8],  # First 8
                'articulation': understanding['style']['articulation'],
                'timing': understanding['style']['timing'],
                'expression': f"{understanding['style']['expression']:.0%}"
            }
        }

    def generate_accompaniment(self):
        """Generate Stage 2 accompaniment"""

        if self.state['understanding'] is None:
            return {'status': 'error', 'message': 'Analysis not complete'}

        orchestrator_s2 = Stage2AccompanimentGeneration()
        accompaniment = orchestrator_s2.generate_accompaniment(
            self.state['understanding'],
            verbosity=0
        )

        self.state['accompaniment'] = accompaniment

        return {
            'status': 'success',
            'accompaniment': {
                'bass_notes': len(accompaniment['bass']['notes']),
                'drum_events': len(accompaniment['drums']['combined']['notes']),
                'pad_voices': len(accompaniment['pads']['combined']['notes'])
            }
        }

    def synthesize_audio(self, regenerate_tracks=None):
        """
        Synthesize audio from accompaniment.

        Args:
            regenerate_tracks: list of track types to regenerate
                ['drums', 'bass', 'pads'] or None for all
        """

        if self.state['accompaniment'] is None:
            return {'status': 'error', 'message': 'Accompaniment not generated'}

        # Generate new accompaniment for specified tracks
        if regenerate_tracks:
            # For now, regenerate all (in production, would only regenerate specific tracks)
            pass

        # Stage 3: Synthesize to audio
        synthesizer = Stage3AudioSynthesis(sr=self.state['sr'])
        synthesis_result = synthesizer.synthesize_accompaniment(
            self.state['accompaniment'],
            verbosity=0
        )

        self.state['synthesis_result'] = synthesis_result
        self.state['current_stage'] = 'audition'

        return {
            'status': 'success',
            'synthesis': {
                'duration': synthesis_result['duration_seconds'],
                'key': synthesis_result['key']
            }
        }

    def get_audio_for_playback(self, track='mixed'):
        """Get audio bytes for web player"""

        if self.state['synthesis_result'] is None:
            return None

        audio = self.state['synthesis_result'].get(track, {}).get('audio')
        if audio is None:
            return None

        # Create WAV in memory
        import io
        buffer = io.BytesIO()
        sf.write(buffer, audio, self.state['sr'], format='WAV')
        buffer.seek(0)
        return buffer

    def lock_track(self, track):
        """Lock a track so it won't be regenerated"""

        if track not in self.state['locked_tracks']:
            self.state['locked_tracks'].append(track)

        return {
            'status': 'success',
            'locked_tracks': self.state['locked_tracks']
        }

    def unlock_track(self, track):
        """Unlock a track for regeneration"""

        if track in self.state['locked_tracks']:
            self.state['locked_tracks'].remove(track)

        return {
            'status': 'success',
            'locked_tracks': self.state['locked_tracks']
        }

    def export_stems(self):
        """Export individual stems"""

        if self.state['synthesis_result'] is None:
            return {'status': 'error', 'message': 'No synthesis result'}

        synthesizer = Stage3AudioSynthesis(sr=self.state['sr'])
        export_dir = os.path.join(tempfile.gettempdir(), f'mastercrafter_{self.session_id}')
        os.makedirs(export_dir, exist_ok=True)

        stems = synthesizer.export_stems(self.state['synthesis_result'], export_dir)

        return {
            'status': 'success',
            'stems': stems
        }


# ─────────────────────────────────────────────────
# Flask Routes
# ─────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve main UI"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload"""

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    if not file.filename.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
        return jsonify({'status': 'error', 'message': 'Unsupported file format'}), 400

    # Generate session ID
    session_id = os.urandom(16).hex()
    session['session_id'] = session_id

    # Save uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'{session_id}_{filename}')
    file.save(filepath)

    # Process upload
    processor = AudioProcessor(session_id)
    PROCESSING_STATE[session_id] = processor

    result = processor.process_upload(filepath)

    return jsonify(result)


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Analyze uploaded audio"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]

    result = processor.analyze_performance()

    if result['status'] == 'success':
        result['stage'] = 'analysis_complete'

    return jsonify(result)


@app.route('/api/generate', methods=['POST'])
def generate():
    """Generate accompaniment"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]

    result = processor.generate_accompaniment()

    if result['status'] == 'success':
        result['stage'] = 'accompaniment_ready'

    return jsonify(result)


@app.route('/api/synthesize', methods=['POST'])
def synthesize():
    """Synthesize accompaniment to audio"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]

    # Check which tracks to regenerate
    data = request.get_json() or {}
    regenerate_tracks = data.get('regenerate_tracks', None)

    result = processor.synthesize_audio(regenerate_tracks)

    if result['status'] == 'success':
        result['stage'] = 'ready_to_audition'

    return jsonify(result)


@app.route('/api/audio/<track>')
def get_audio(track):
    """Stream audio for playback"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]
    audio_buffer = processor.get_audio_for_playback(track)

    if audio_buffer is None:
        return jsonify({'status': 'error', 'message': 'Audio not available'}), 400

    return send_file(audio_buffer, mimetype='audio/wav')


@app.route('/api/lock/<track>', methods=['POST'])
def lock_track(track):
    """Lock a track"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]
    result = processor.lock_track(track)

    return jsonify(result)


@app.route('/api/unlock/<track>', methods=['POST'])
def unlock_track(track):
    """Unlock a track"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]
    result = processor.unlock_track(track)

    return jsonify(result)


@app.route('/api/export', methods=['POST'])
def export_stems():
    """Export accompaniment stems"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]
    result = processor.export_stems()

    return jsonify(result)


@app.route('/api/status')
def get_status():
    """Get current processing status"""

    session_id = session.get('session_id')
    if session_id not in PROCESSING_STATE:
        return jsonify({'status': 'error', 'message': 'No session'}), 400

    processor = PROCESSING_STATE[session_id]

    return jsonify({
        'current_stage': processor.state['current_stage'],
        'locked_tracks': processor.state['locked_tracks'],
        'has_analysis': processor.state['understanding'] is not None,
        'has_accompaniment': processor.state['accompaniment'] is not None,
        'has_synthesis': processor.state['synthesis_result'] is not None
    })


if __name__ == '__main__':
    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER WEB UI SERVER                 ║")
    print("╚════════════════════════════════════════════════╝\n")
    print("Starting server on http://localhost:5000")
    print("Upload audio and follow the track-by-track workflow\n")

    app.run(debug=True, port=5000)
