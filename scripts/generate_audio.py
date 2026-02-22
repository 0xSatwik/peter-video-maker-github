"""
Generate voice audio via Colab Gradio API (MOSS-TTS 1.7B).
Connects to a user-provided Gradio URL from Google Colab.
"""
import os
import json
import time
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from gradio_client import Client, handle_file

COLAB_URL = os.environ.get('COLAB_URL', '')
PARALLEL_WORKERS = 5
MAX_RETRIES = 2

# User-Vetted Perfect Preset (Matches Colab Screenshot)
HIGH_QUALITY = {
    "max_new_tokens": 2850,
    "speed": 1.0,
    "text_temp": 1.5,
    "text_top_p": 1.0,
    "text_top_k": 50,
    "audio_temp": 0.95,
    "audio_top_p": 0.95,
    "audio_top_k": 50,
    "audio_repetition_penalty": 1.1,
    "n_vq": 24,
}

# Voice reference files
VOICE_REFS = {
    "peter": "assets/peter-vocie.mp3",
    "stewie": "assets/Stewies-voice.mp3",
}


def generate_one(client, text, speaker, output_path, index, total):
    """Generate a single voice clip via Gradio API."""

    # Skip if already generated (resume support)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        print(f"  ⏭️  [{index+1}/{total}] SKIP (already exists): {output_path}")
        return True

    voice_ref = VOICE_REFS.get(speaker)
    if not voice_ref or not os.path.exists(voice_ref):
        print(f"  ⚠️  [{index+1}/{total}] No voice ref for '{speaker}', using default voice")
        voice_ref = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            start = time.time()
            print(f"  🎤  [{index+1}/{total}] Generating ({speaker.upper()}): \"{text[:50]}...\"")

            # Call the Gradio generate_speech function
            result = client.predict(
                text,                                           # text input
                handle_file(voice_ref) if voice_ref else None,  # reference audio
                HIGH_QUALITY["max_new_tokens"],
                HIGH_QUALITY["speed"],
                HIGH_QUALITY["text_temp"],
                HIGH_QUALITY["text_top_p"],
                HIGH_QUALITY["text_top_k"],
                HIGH_QUALITY["audio_temp"],
                HIGH_QUALITY["audio_top_p"],
                HIGH_QUALITY["audio_top_k"],
                HIGH_QUALITY["audio_repetition_penalty"],
                HIGH_QUALITY["n_vq"],
                api_name="/generate_speech"
            )

            elapsed = time.time() - start

            # result is (audio_path, status_text)
            audio_path = result[0] if isinstance(result, (list, tuple)) else result

            if audio_path and os.path.exists(audio_path):
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(audio_path, output_path)
                size_kb = os.path.getsize(output_path) / 1024
                print(f"  ✅  [{index+1}/{total}] DONE in {elapsed:.1f}s — {size_kb:.0f}KB — {output_path}")
                return True
            else:
                print(f"  ❌  [{index+1}/{total}] Attempt {attempt}: No audio returned")

        except Exception as e:
            elapsed = time.time() - start
            print(f"  ❌  [{index+1}/{total}] Attempt {attempt} failed after {elapsed:.1f}s: {e}")

        if attempt < MAX_RETRIES:
            print(f"  ⏳  [{index+1}/{total}] Retrying in 3s...")
            time.sleep(3)

    print(f"  💀  [{index+1}/{total}] FAILED after {MAX_RETRIES} attempts: {output_path}")
    return False


def preprocess_text(text):
    """Clean text for TTS to prevent pronunciation issues."""
    import re
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Add space after punctuation if missing
    text = re.sub(r'([.,!?])([A-Za-z])', r'\1 \2', text)
    
    # For very short phrases, add context padding (helps MOSS-TTS enunciate)
    if len(text.split()) <= 3:
        text = f"... {text} ..."
        
    return text.strip()


def parse_script(script_path):
    """Parse script file: SPEAKER|TAGS|LYRICS"""
    lines = []
    with open(script_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines, comments, and common header text
            if not line or line.startswith('#'):
                continue
            if line.lower().startswith('format:') or line.lower().startswith('family guy'):
                continue
                
            parts = line.split('|')
            if len(parts) == 3:
                speaker = parts[0].strip().lower()
                text = preprocess_text(parts[2].strip())
                
                if not text.endswith(('.', '!', '?', '"', "'")):
                    text += '.'
                    
                lines.append({
                    'speaker': speaker,
                    'text': text
                })
    return lines


def main():
    if not COLAB_URL:
        print("❌ ERROR: COLAB_URL environment variable not set!")
        print("   Please provide your Colab Gradio URL when running the workflow.")
        exit(1)

    print("=" * 60)
    print("🎙️  MOSS-TTS Voice Generation via Google Colab")
    print("=" * 60)
    print(f"📡 Colab URL: {COLAB_URL}")
    print(f"👷 Parallel workers: {PARALLEL_WORKERS}")
    print(f"🎛️  Quality: High (24 RVQ)")
    print()

    # Connect to Colab Gradio
    print("🔌 Connecting to Colab Gradio API...")
    try:
        client = Client(COLAB_URL)
        print("✅ Connected!\n")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        print("   Make sure the Colab notebook is running and the Gradio URL is correct.")
        exit(1)

    # Parse script
    script_path = os.environ.get('SCRIPT_PATH', 'config/scripts/EPISODE_01.txt')
    lines = parse_script(script_path)
    print(f"📄 Script: {script_path}")
    print(f"📝 Dialogue lines: {len(lines)}")

    # Check voice references
    for name, path in VOICE_REFS.items():
        exists = "✅" if os.path.exists(path) else "❌"
        print(f"🎙️  {name} voice ref: {exists} {path}")
    print()

    os.makedirs('audio', exist_ok=True)

    # Build tasks
    tasks = []
    for i, line in enumerate(lines):
        output_path = f"audio/{line['speaker']}_{i:03d}.wav"
        tasks.append({
            'text': line['text'],
            'speaker': line['speaker'],
            'output_path': output_path,
            'index': i,
        })

    # Generate with parallel workers
    print(f"🚀 Starting generation of {len(tasks)} clips...\n")
    overall_start = time.time()
    success = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(
                generate_one, client,
                t['text'], t['speaker'], t['output_path'],
                t['index'], len(tasks)
            ): t
            for t in tasks
        }

        for future in as_completed(futures):
            task = futures[future]
            try:
                if future.result():
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  💥 Exception for {task['output_path']}: {e}")
                failed += 1

    total_time = time.time() - overall_start

    print()
    print("=" * 60)
    print(f"📊 RESULTS: {success} succeeded, {failed} failed")
    print(f"⏱️  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    if success > 0:
        print(f"⚡ Average: {total_time/success:.1f}s per clip")
    print("=" * 60)

    if failed > 0:
        print("⚠️  Some clips failed. Pipeline will continue with available audio.")

    # Save metadata for video assembly
    metadata = []
    for i, line in enumerate(lines):
        audio_path = f"audio/{line['speaker']}_{i:03d}.wav"
        metadata.append({
            'index': i,
            'speaker': line['speaker'],
            'text': line['text'],
            'audio_file': audio_path,
            'exists': os.path.exists(audio_path)
        })

    with open('audio/metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n💾 Saved audio/metadata.json ({len(metadata)} entries)")


if __name__ == '__main__':
    main()