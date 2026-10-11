#!/usr/bin/env python3
"""
Test SongShapes character control workflow end-to-end
1. Create synthetic test audio
2. Upload to Flask server
3. Separate into stems
4. Regenerate with character effects
5. Verify output files exist
"""

import requests
import numpy as np
import soundfile as sf
import os
import tempfile
import json
import time
from pathlib import Path

# Configuration
BASE_URL = 'http://localhost:5000'
TEST_AUDIO_PATH = '/tmp/test_audio.wav'

def create_test_audio(duration=3, sr=44100):
    """Create synthetic test audio with multiple components"""
    t = np.linspace(0, duration, int(sr * duration))

    # Vocals: mid-frequency sine wave
    vocals = 0.3 * np.sin(2 * np.pi * 440 * t)  # A4 note

    # Bass: low-frequency sine wave
    bass = 0.2 * np.sin(2 * np.pi * 55 * t)  # A1 note

    # Percussion: high-frequency bursts
    drums = np.zeros_like(t)
    for i in range(0, len(t), sr // 4):  # Every quarter second
        drums[i:i+sr//20] += 0.4 * np.sin(2 * np.pi * 8000 * t[i:i+sr//20])

    # Mix
    mix = vocals + bass + drums
    mix = np.clip(mix, -1, 1) * 0.9

    # Save
    sf.write(TEST_AUDIO_PATH, mix, sr)
    print(f"✓ Created test audio: {TEST_AUDIO_PATH} ({duration}s)")
    return TEST_AUDIO_PATH

def upload_audio(audio_path):
    """Upload audio file and return session_id"""
    print("\n[1/4] Uploading audio...")
    with open(audio_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f'{BASE_URL}/api/upload', files=files)

    result = response.json()
    if result['status'] == 'success':
        session_id = result['session_id']
        duration = result['duration']
        sr = result['sample_rate']
        print(f"✓ Upload successful")
        print(f"  Session: {session_id}")
        print(f"  Duration: {duration:.2f}s @ {sr}Hz")
        return session_id
    else:
        print(f"✗ Upload failed: {result['message']}")
        return None

def separate_stems(session_id):
    """Separate audio into stems"""
    print("\n[2/4] Separating into stems...")
    payload = {
        'session_id': session_id,
        'character_config': {
            'vocals': {'eq_low': 0, 'eq_mid': 0, 'eq_high': 0, 'compression': 0, 'saturation': 0, 'reverb': 0},
            'percussion': {'eq_low': 0, 'eq_mid': 0, 'eq_high': 0, 'compression': 0, 'saturation': 0, 'reverb': 0},
            'bass_pads': {'eq_low': 0, 'eq_mid': 0, 'eq_high': 0, 'compression': 0, 'saturation': 0, 'reverb': 0}
        }
    }

    response = requests.post(f'{BASE_URL}/api/separate', json=payload)
    result = response.json()

    if result['status'] == 'success':
        print(f"✓ Separation successful")
        print(f"  Message: {result['message']}")
        print(f"  Stems generated: {len(result['stems'])} files")
        for stem_name, path in result['stems'].items():
            size_mb = os.path.getsize(path) / 1024 / 1024
            print(f"    - {stem_name}: {size_mb:.2f}MB")
        return True
    else:
        print(f"✗ Separation failed: {result['message']}")
        return False

def regenerate_with_character(session_id):
    """Regenerate stems with character effects"""
    print("\n[3/4] Regenerating with character effects...")

    # Apply different settings to each stem
    payload = {
        'session_id': session_id,
        'character_config': {
            'vocals': {
                'eq_low': 2,      # +2dB bass boost
                'eq_mid': 1,      # +1dB mid boost
                'eq_high': 3,     # +3dB treble boost
                'compression': 0.5,  # 50% compression
                'saturation': 0.3,   # 30% saturation
                'reverb': 0.2     # 20% reverb
            },
            'percussion': {
                'eq_low': -1,     # -1dB bass reduction
                'eq_mid': 0,      # No mid change
                'eq_high': 2,     # +2dB treble boost
                'compression': 0.7,  # 70% compression
                'saturation': 0.1,   # 10% saturation
                'reverb': 0.1     # 10% reverb
            },
            'bass_pads': {
                'eq_low': 2,      # +2dB bass boost
                'eq_mid': -1,     # -1dB mid reduction
                'eq_high': 0,     # No treble change
                'compression': 0.3,  # 30% compression
                'saturation': 0.2,   # 20% saturation
                'reverb': 0.3     # 30% reverb
            }
        }
    }

    response = requests.post(f'{BASE_URL}/api/regenerate', json=payload)
    result = response.json()

    if result['status'] == 'success':
        print(f"✓ Regeneration successful")
        print(f"  Message: {result['message']}")
        print(f"  Stems regenerated: {len(result['stems'])} files")
        for stem_name, path in result['stems'].items():
            size_mb = os.path.getsize(path) / 1024 / 1024
            print(f"    - {stem_name}: {size_mb:.2f}MB")
        return True
    else:
        print(f"✗ Regeneration failed: {result['message']}")
        return False

def check_state(session_id):
    """Check current processing state"""
    print("\n[4/4] Checking final state...")
    response = requests.get(f'{BASE_URL}/api/state', params={'session_id': session_id})
    result = response.json()

    print(f"✓ State retrieved")
    print(f"  Status: {result['status']}")
    print(f"  Message: {result['message']}")
    print(f"  Audio loaded: {result['audio_loaded']}")
    print(f"  Stems ready: {result['stems_ready']}")

    return True

def main():
    print("=" * 60)
    print("SongShapes Character Control Workflow Test")
    print("=" * 60)

    try:
        # Create test audio
        audio_path = create_test_audio(duration=3)

        # Upload
        session_id = upload_audio(audio_path)
        if not session_id:
            return False

        # Separate
        if not separate_stems(session_id):
            return False

        time.sleep(1)  # Brief pause between operations

        # Regenerate with character effects
        if not regenerate_with_character(session_id):
            return False

        time.sleep(1)  # Brief pause before checking state

        # Check state
        check_state(session_id)

        print("\n" + "=" * 60)
        print("✓ All tests passed! Character control workflow is working.")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
