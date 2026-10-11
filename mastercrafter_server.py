"""
Mastercrafter Stage 1: Flask Server for Sound Restoration Backend
Handles file upload, processing, and download.
"""

from flask import Flask, request, jsonify, send_file
import numpy as np
import soundfile as sf
import io
from mastercrafter_audio_restoration import SoundRestorationEngine, TapePreset
import logging

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def index():
    """Serve the HTML interface."""
    with open('mastercrafter_restoration_ui.html', 'r') as f:
        return f.read()

@app.route('/api/presets', methods=['GET'])
def get_presets():
    """Return available tape presets."""
    presets = {}
    for name, config in TapePreset.PRESETS.items():
        presets[name] = {
            "description": config.get("description", ""),
            "bias": config.get("bias", 0.5),
            "hf_driver": config.get("hf_driver", 0.5),
            "eq_low_shelf": config.get("eq_low_shelf", 0.0),
            "eq_mid_gain": config.get("eq_mid_gain", 0.0),
            "eq_high_shelf": config.get("eq_high_shelf", 0.0),
        }
    return jsonify(presets)

@app.route('/api/process', methods=['POST'])
def process_audio():
    """
    Process audio file with restoration engine.

    Expected multipart form:
    - audio: AudioFile (WAV, MP3, FLAC, etc.)
    - tape_preset: str (warm_tape, bright_tape, etc.)
    - bias: float (0-1, overrides preset)
    - hf_driver: float (0-1, overrides preset)
    - low_shelf: float (-18 to 18 dB)
    - mid_gain: float (-18 to 18 dB)
    - high_shelf: float (-18 to 18 dB)
    - noise_gate: bool
    """
    try:
        # Get uploaded file
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({"error": "Empty filename"}), 400

        # Read audio data
        audio_data, sr = sf.read(audio_file)

        # Normalize to [-1, 1] if needed
        max_val = np.max(np.abs(audio_data))
        if max_val > 1.0:
            audio_data = audio_data / max_val

        logger.info(f"Loaded audio: {audio_data.shape}, SR: {sr}")

        # Get processing parameters
        tape_preset = request.form.get('tape_preset', 'warm_tape')
        bias = request.form.get('bias', None)
        hf_driver = request.form.get('hf_driver', None)
        low_shelf = request.form.get('low_shelf', None)
        mid_gain = request.form.get('mid_gain', None)
        high_shelf = request.form.get('high_shelf', None)
        noise_gate = request.form.get('noise_gate', 'true').lower() == 'true'

        # Initialize restoration engine
        engine = SoundRestorationEngine(sr=sr, tape_preset=tape_preset)

        # Override parameters if provided
        if bias is not None:
            engine.hysteresis.bias = float(bias)
        if hf_driver is not None:
            engine.hysteresis.hf_driver = float(hf_driver)
        if low_shelf is not None:
            engine.neve_preamp.low_shelf_gain = float(low_shelf)
        if mid_gain is not None:
            engine.neve_preamp.mid_gain = float(mid_gain)
        if high_shelf is not None:
            engine.neve_preamp.high_shelf_gain = float(high_shelf)

        logger.info(f"Processing with preset: {tape_preset}, noise_gate: {noise_gate}")

        # Process audio
        restored = engine.process(audio_data, apply_noise_gate=noise_gate)

        logger.info(f"Processing complete. Output shape: {restored.shape}")

        # Save to BytesIO buffer
        output_buffer = io.BytesIO()
        sf.write(output_buffer, restored, sr, format='WAV')
        output_buffer.seek(0)

        return send_file(
            output_buffer,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='mastercrafter_restored.wav'
        )

    except Exception as e:
        logger.error(f"Processing error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_audio():
    """
    Analyze audio file without processing.
    Returns statistics about the audio.
    """
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files['audio']
        audio_data, sr = sf.read(audio_file)

        # Analyze
        if audio_data.ndim > 1:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data

        rms = np.sqrt(np.mean(audio_mono ** 2))
        peak = np.max(np.abs(audio_mono))
        crest_factor = peak / rms if rms > 0 else 0

        # Simple spectral analysis (frequency distribution)
        fft = np.abs(np.fft.fft(audio_mono[:sr]))  # 1 second
        freqs = np.fft.fftfreq(len(fft), 1/sr)[:len(fft)//2]
        magnitude = fft[:len(fft)//2]

        # Find dominant frequencies
        top_freqs = np.argsort(magnitude)[-5:][::-1]
        dominant = [(freqs[i], magnitude[i]) for i in top_freqs if freqs[i] > 0]

        return jsonify({
            "sample_rate": sr,
            "duration": len(audio_data) / sr,
            "channels": audio_data.ndim,
            "rms": float(rms),
            "peak": float(peak),
            "crest_factor": float(crest_factor),
            "dominant_frequencies": [
                {"freq": float(f), "magnitude": float(m)} for f, m in dominant
            ]
        })

    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Mastercrafter Stage 1: Sound Restoration Engine",
        "version": "1.0.0"
    })

# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "File too large (max 500MB)"}), 413

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# ============================================================================
# Run Server
# ============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("Mastercrafter Stage 1: Sound Restoration Engine")
    print("=" * 70)
    print("\n🎵 Server running at http://localhost:5000")
    print("\nAvailable endpoints:")
    print("  GET  /                 - Web interface")
    print("  GET  /api/presets      - List tape presets")
    print("  POST /api/process      - Process audio file")
    print("  POST /api/analyze      - Analyze audio without processing")
    print("  GET  /health           - Health check")
    print("\n" + "=" * 70)
    print("\nSupported audio formats: WAV, MP3, FLAC, OGG, M4A, etc.")
    print("Max file size: 500MB")
    print("\n" + "=" * 70)

    app.run(debug=True, host='0.0.0.0', port=5000)
