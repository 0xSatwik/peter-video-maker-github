import os
import requests
import base64
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

MODAL_ENDPOINT = os.environ.get('MODAL_ENDPOINT')
MAX_RETRIES = 3
RETRY_DELAY = 5
PARALLEL_WORKERS = 3


def generate_audio(text, speaker, output_path):
    """Generate speech via MOSS-TTS API with retry logic"""

    if not MODAL_ENDPOINT:
        print(f"⚠️ Skipping {output_path} - No Modal endpoint")
        return False

    # Skip if already generated (resume support)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        print(f"⏭️ Skipping {output_path} - Already exists")
        return True

    print(f"🎤 [{speaker.upper()}]: {text[:60]}...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                MODAL_ENDPOINT,
                json={
                    "text": text,
                    "speaker": speaker,
                },
                timeout=600
            )

            if response.status_code == 200:
                data = response.json()
                audio_bytes = base64.b64decode(data['audio_base64'])

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)

                print(f"✅ Saved: {output_path}")
                return True
            else:
                print(f"❌ Attempt {attempt}/{MAX_RETRIES} failed: HTTP {response.status_code}")

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ReadTimeout) as e:
            print(f"⚠️ Attempt {attempt}/{MAX_RETRIES} error: {type(e).__name__}")

        except Exception as e:
            print(f"❌ Attempt {attempt}/{MAX_RETRIES} error: {e}")

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            print(f"⏳ Retrying in {wait}s...")
            time.sleep(wait)

    print(f"💀 Failed after {MAX_RETRIES} attempts: {output_path}")
    return False


def parse_script(script_path):
    """Parse script file: SPEAKER|TAGS|LYRICS"""
    lines = []
    with open(script_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|')
            if len(parts) == 3:
                speaker, tags, lyrics = parts
                lines.append({
                    'speaker': speaker.strip().lower(),
                    'text': lyrics.strip()
                })
    return lines


def generate_one(task):
    """Worker function for parallel generation."""
    return generate_audio(
        text=task['text'],
        speaker=task['speaker'],
        output_path=task['output_path']
    )


def main():
    script_path = os.environ.get('SCRIPT_PATH', 'config/scripts/EPISODE_01.txt')
    lines = parse_script(script_path)

    print(f"📄 Loaded {len(lines)} dialogue lines from {script_path}")
    os.makedirs('audio', exist_ok=True)

    # Build task list
    tasks = []
    for i, line in enumerate(lines):
        output_path = f"audio/{line['speaker']}_{i:03d}.wav"
        tasks.append({
            'text': line['text'],
            'speaker': line['speaker'],
            'output_path': output_path
        })

    print(f"🚀 Generating {len(tasks)} audio files with {PARALLEL_WORKERS} parallel workers...")
    start_time = time.time()

    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        future_to_task = {executor.submit(generate_one, task): task for task in tasks}

        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                ok = future.result()
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"❌ Exception for {task['output_path']}: {e}")
                fail_count += 1

    elapsed = time.time() - start_time
    print(f"\n📊 Results: {success_count} succeeded, {fail_count} failed")
    print(f"⏱️ Total time: {elapsed/60:.1f} minutes")

    if fail_count > 0:
        print("⚠️ Some audio files failed. Pipeline will continue with available files.")

    # Save metadata for video assembly
    timing = []
    for i, line in enumerate(lines):
        audio_path = f"audio/{line['speaker']}_{i:03d}.wav"
        timing.append({
            'index': i,
            'speaker': line['speaker'],
            'text': line['text'],
            'audio_file': audio_path,
            'exists': os.path.exists(audio_path)
        })

    with open('audio/metadata.json', 'w', encoding='utf-8') as f:
        json.dump(timing, f, indent=2)

    print(f"💾 Saved audio/metadata.json with {len(timing)} entries")


if __name__ == '__main__':
    main()