import os
import requests
import base64

MODAL_ENDPOINT = os.environ.get('MODAL_ENDPOINT')

def generate_audio(lyrics, tags, duration, output_path):
    """Generate audio via HeartMuLa API"""
    
    if not MODAL_ENDPOINT:
        print(f"⚠️ Skipping {output_path} - No Modal endpoint")
        return False
    
    print(f"🎵 Generating: {tags}")
    
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
        print(f"❌ Failed: {response.status_code}")
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
    script_path = os.environ.get('SCRIPT_PATH', 'config/scripts/episode_01.txt')
    lines = parse_script(script_path)
    
    print(f"📄 Loaded {len(lines)} dialogue lines from {script_path}")
    
    os.makedirs('audio', exist_ok=True)
    
    # Generate each line
    for i, line in enumerate(lines):
        output_path = f"audio/{line['speaker']}_{i:03d}.mp3"
        
        # Estimate duration based on text length (~15 chars per second)
        duration = max(5, len(line['lyrics']) // 15)
        
        generate_audio(
            lyrics=line['lyrics'],
            tags=line['tags'],
            duration=duration,
            output_path=output_path
        )
    
    # Generate background music (instrumental)
    generate_audio(
        lyrics="Instrumental",
        tags="upbeat, tech, background, calm, lofi",
        duration=60,
        output_path='assets/background_music.mp3'
    )
    
    print(f"\n✅ Generated {len(lines) + 1} audio files!")

if __name__ == '__main__':
    main()