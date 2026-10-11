import os
import tempfile
import json
from flask import Flask, render_template, request, send_file, session
from werkzeug.utils import secure_filename
import soundfile as sf

app = Flask(__name__, template_folder='templates')
app.secret_key = 'mastercrafter_secret'
app.config['MAX_CONTENT_LENGTH'] = 60 * 1024 * 1024  # 60MB max
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Global state (in production, use database)
PROCESSING_STATE = {}

class AudioProcessor:
    """Handles the audio processing pipeline (simplified for testing)"""

    def __init__(self, session_id):
        self.session_id = session_id
        self.state = {
            'original_audio': None,
            'art': None,
            'performance': None,
            'understanding': None,
            'accompaniment': None,
            'synthesis_result': None,
            'locked_tracks': [],
            'current_stage': 'upload'
        }

    def process_upload(self, audio_path):
        """Process uploaded audio file"""
        try:
            audio, sr = sf.read(audio_path)
            self.state['original_audio'] = {'path': audio_path, 'sr': sr, 'length': len(audio)}
            self.state['current_stage'] = 'analysis'
            return {'status': 'success', 'message': 'Audio loaded successfully'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_state(self):
        return self.state


@app.route('/')
def index():
    """Serve main UI"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    """Handle audio upload"""
    if 'audio' not in request.files:
        return {'error': 'No audio file provided'}, 400

    file = request.files['audio']
    if file.filename == '':
        return {'error': 'No file selected'}, 400

    session_id = request.form.get('session_id', 'default')
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    if session_id not in PROCESSING_STATE:
        PROCESSING_STATE[session_id] = AudioProcessor(session_id)

    result = PROCESSING_STATE[session_id].process_upload(filepath)
    return result


@app.route('/api/state', methods=['GET'])
def get_state():
    """Get current processing state"""
    session_id = request.args.get('session_id', 'default')
    if session_id not in PROCESSING_STATE:
        PROCESSING_STATE[session_id] = AudioProcessor(session_id)
    return PROCESSING_STATE[session_id].get_state()


if __name__ == '__main__':
    app.run(debug=True, port=5000, host='localhost')
