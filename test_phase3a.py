#!/usr/bin/env python3
"""
Test Phase 3A Core Audio Processing Logic
Tests melody extraction, chord detection, and accompaniment generation
WITHOUT async infrastructure (no Celery/Redis needed)
"""

import requests
import json
import sys
import time
from pathlib import Path

# Test audio files (synthetic, properly generated for Phase 3A testing)
TEST_AUDIO_VOCAL = "/home/claude/test_audio_vocal.wav"      # 30s: melody extraction test
TEST_AUDIO_CHORDS = "/home/claude/test_audio_chords.wav"    # 20s: chord detection test

# Flask API base URL
API_URL = "http://localhost:5000"

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def print_step(msg):
    print(f"{BLUE}→ {msg}{RESET}")

def print_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")

def print_data(label, data):
    print(f"{YELLOW}{label}:{RESET}")
    print(json.dumps(data, indent=2))

def test_phase3a():
    """Run Phase 3A core tests"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Phase 3A Core Audio Logic Tests{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    # Check if Flask is running
    print_step("Checking Flask server connectivity...")
    try:
        resp = requests.get(f"{API_URL}/api/health", timeout=5)
        if resp.status_code == 200:
            print_success("Flask server is running")
        else:
            print_error(f"Flask returned unexpected status: {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to Flask server on localhost:5000")
        print("Please run: python3 app.py")
        return False
    except Exception as e:
        print_error(f"Connection error: {e}")
        return False

    # Check test audio files exist
    print_step(f"Checking test audio files...")
    if not Path(TEST_AUDIO_VOCAL).exists():
        print_error(f"Test audio not found: {TEST_AUDIO_VOCAL}")
        return False
    print_success(f"Test audio found: {TEST_AUDIO_VOCAL}")

    # ========================================================================
    # Step 1: Upload audio to initialize session
    # ========================================================================
    print_step("Uploading test audio to initialize session...")
    try:
        with open(TEST_AUDIO_VOCAL, 'rb') as f:
            files = {'file': (Path(TEST_AUDIO_VOCAL).name, f)}
            resp = requests.post(f"{API_URL}/api/upload", files=files, timeout=30)

        if resp.status_code != 200:
            print_error(f"Upload failed with status {resp.status_code}")
            print_data("Response", resp.json())
            return False

        result = resp.json()
        if result.get('status') != 'success':
            print_error(f"Upload failed: {result.get('message')}")
            return False

        session_id = result['session_id']
        sr = result['sample_rate']
        duration = result['duration']

        print_success(f"Audio uploaded")
        print_data("Session Details", {
            'session_id': session_id,
            'sample_rate': sr,
            'duration': f"{duration:.2f}s",
        })
    except Exception as e:
        print_error(f"Upload error: {e}")
        return False

    # ========================================================================
    # Step 2: Extract Melody (F0 contour)
    # ========================================================================
    print_step("Extracting melody (F0 contour) from audio...")
    try:
        start_time = time.time()
        resp = requests.post(
            f"{API_URL}/api/extract-melody",
            json={
                'session_id': session_id,
                'use_vocals_stem': False  # Use original audio (no stem separation yet)
            },
            timeout=60
        )
        elapsed = time.time() - start_time

        if resp.status_code != 200:
            print_error(f"Melody extraction failed with status {resp.status_code}")
            print_data("Response", resp.json())
            return False

        result = resp.json()
        if result.get('status') != 'success':
            print_error(f"Melody extraction failed: {result.get('message')}")
            return False

        f0_mean = result['f0_mean']
        voicing_ratio = result['voicing_ratio']
        num_frames = result['num_frames']

        print_success(f"Melody extracted in {elapsed:.2f}s")
        print_data("Extraction Results", {
            'f0_mean': f"{f0_mean:.1f} Hz",
            'voicing_ratio': f"{voicing_ratio*100:.1f}%",
            'num_frames': num_frames,
            'message': result.get('message')
        })
    except Exception as e:
        print_error(f"Melody extraction error: {e}")
        return False

    # ========================================================================
    # Step 3: Detect Chords
    # ========================================================================
    print_step("Detecting chord progression...")
    try:
        start_time = time.time()
        resp = requests.post(
            f"{API_URL}/api/detect-chords",
            json={
                'session_id': session_id,
                'use_vocals_stem': False
            },
            timeout=60
        )
        elapsed = time.time() - start_time

        if resp.status_code != 200:
            print_error(f"Chord detection failed with status {resp.status_code}")
            print_data("Response", resp.json())
            return False

        result = resp.json()
        if result.get('status') != 'success':
            print_error(f"Chord detection failed: {result.get('message')}")
            return False

        chords = result['chords']

        print_success(f"Chords detected in {elapsed:.2f}s")
        print_data("Chord Progression", {
            'num_changes': len(chords),
            'first_5_chords': chords[:5] if chords else "None detected",
            'message': result.get('message')
        })
    except Exception as e:
        print_error(f"Chord detection error: {e}")
        return False

    # ========================================================================
    # Step 4: Generate Accompaniment (Bass + Drums)
    # ========================================================================
    print_step("Generating accompaniment (bass + drums)...")
    try:
        start_time = time.time()
        resp = requests.post(
            f"{API_URL}/api/generate-accompaniment",
            json={
                'session_id': session_id,
                'tempo_bpm': 120,
                'key': 'C',
                'character_config': {
                    'bass': {
                        'eq_low': 1.2,
                        'eq_mid': 1.0,
                        'eq_high': 0.8,
                        'compression': 2.0,
                        'saturation': 0.3,
                        'reverb': 0.15
                    },
                    'drums': {
                        'eq_low': 0.9,
                        'eq_mid': 1.1,
                        'eq_high': 1.2,
                        'compression': 3.0,
                        'saturation': 0.2,
                        'reverb': 0.1
                    }
                }
            },
            timeout=120
        )
        elapsed = time.time() - start_time

        if resp.status_code != 200:
            print_error(f"Accompaniment generation failed with status {resp.status_code}")
            print_data("Response", resp.json())
            return False

        result = resp.json()
        if result.get('status') != 'success':
            print_error(f"Accompaniment generation failed: {result.get('message')}")
            return False

        stems = result['accompaniment_stems']
        metadata = result['metadata']

        print_success(f"Accompaniment generated in {elapsed:.2f}s")
        print_data("Generated Stems", {
            'bass': Path(stems['bass']).name if stems.get('bass') else 'N/A',
            'drums': Path(stems['drums']).name if stems.get('drums') else 'N/A',
            'mix': Path(stems['mix']).name if stems.get('mix') else 'N/A',
        })
        print_data("Accompaniment Metadata", metadata)

        # Verify stem files exist
        print_step("Verifying generated audio files...")
        for stem_type, stem_path in stems.items():
            if Path(stem_path).exists():
                size_mb = Path(stem_path).stat().st_size / (1024*1024)
                print_success(f"{stem_type.capitalize()}: {size_mb:.2f} MB")
            else:
                print_error(f"{stem_type.capitalize()}: File not found at {stem_path}")
                return False

    except Exception as e:
        print_error(f"Accompaniment generation error: {e}")
        return False

    # ========================================================================
    # Summary
    # ========================================================================
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}Phase 3A Core Logic Test PASSED{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"\nAll three core operations executed successfully:")
    print(f"  1. {GREEN}✓{RESET} Melody extraction (F0 contour)")
    print(f"  2. {GREEN}✓{RESET} Chord detection")
    print(f"  3. {GREEN}✓{RESET} Accompaniment generation (bass + drums)")
    print(f"\nSession ID: {YELLOW}{session_id}{RESET}")
    print(f"Generated files location: {YELLOW}{Path(stems['bass']).parent}{RESET}\n")

    return True

if __name__ == '__main__':
    success = test_phase3a()
    sys.exit(0 if success else 1)
