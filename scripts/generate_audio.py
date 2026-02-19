import os
import requests
import base64
import time
import json

MODAL_ENDPOINT = os.environ.get('MODAL_ENDPOINT')
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds (doubles each retry)
REQUEST_GAP = 2  # seconds between requests


def generate_audio(lyrics, tags, duration, output_path):
    """Generate audio via HeartMuLa API with retry logic"""

    if not MODAL_ENDPOINT:
        print(f"⚠️ Skipping {output_path} - No Modal endpoint")
        return False

    # Skip if already generated (resume support)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        print(f"⏭️ Skipping {output_path} - Already exists")
        return True

    print(f"🎵 Generating: {tags}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                MODAL_ENDPOINT,
                json={
                    "lyrics": lyrics,
                    "tags": tags,
                    "duration": duration
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
            print(f"⚠️ Attempt {attempt}/{MAX_RETRIES} connection error: {type(e).__name__}")

        except Exception as e:
            print(f"❌ Attempt {attempt}/{MAX_RETRIES} unexpected error: {e}")

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            print(f"⏳ Retrying in {wait}s...")
            time.sleep(wait)

    print(f"💀 Failed after {MAX_RETRIES} attempts: {output_path}")
    return False


def parse_script(script_path):
    """Parse script file into lines"""
    lines = []
    with open(script_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Format: SPEAKER|TAGS|LYRICS
            parts = line.split('|')
            if len(parts) == 3:
                speaker, tags, lyrics = parts
                lines.append({
                    'speaker': speaker.strip().lower(),
                    'tags': tags.strip(),
                    'lyrics': lyrics.strip()
                })
    return lines


def main():
    # Load script
    script_path = os.environ.get('SCRIPT_PATH', 'config/scripts/EPISODE_01.txt')
    lines = parse_script(script_path)

    print(f"📄 Loaded {len(lines)} dialogue lines from {script_path}")

    os.makedirs('audio', exist_ok=True)

    success_count = 0
    fail_count = 0

    # Generate each line
    for i, line in enumerate(lines):
        output_path = f"audio/{line['speaker']}_{i:03d}.mp3"

        # Estimate duration based on text length (~15 chars per second)
        duration = max(5, len(line['lyrics']) // 15)

        # Small gap between requests to let Modal breathe
        if i > 0:
            time.sleep(REQUEST_GAP)

        ok = generate_audio(
            lyrics=line['lyrics'],
            tags=line['tags'],
            duration=duration,
            output_path=output_path
        )

        if ok:
            success_count += 1
        else:
            fail_count += 1

    # Generate background music (instrumental)
    time.sleep(REQUEST_GAP)
    ok = generate_audio(
        lyrics="Instrumental",
        tags="upbeat, tech, background, calm, lofi",
        duration=60,
        output_path='audio/background_music.mp3'
    )
    if ok:
        success_count += 1
    else:
        fail_count += 1

    print(f"\n📊 Results: {success_count} succeeded, {fail_count} failed")

    if fail_count > 0:
        print("⚠️ Some audio files failed to generate. The pipeline will continue with available files.")

    # Save timing metadata for the video assembly scripts
    timing = []
    for i, line in enumerate(lines):
        audio_path = f"audio/{line['speaker']}_{i:03d}.mp3"
        timing.append({
            'index': i,
            'speaker': line['speaker'],
            'text': line['lyrics'],
            'audio_file': audio_path,
            'exists': os.path.exists(audio_path)
        })

    with open('audio/metadata.json', 'w', encoding='utf-8') as f:
        json.dump(timing, f, indent=2)

    print(f"💾 Saved audio/metadata.json with {len(timing)} entries")


if __name__ == '__main__':
    main()