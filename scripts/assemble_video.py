from PIL import Image
import numpy as np
import subprocess
import os
import json
import time
import shutil

# === CONSTANTS ===
CANVAS_W, CANVAS_H = 1080, 1920
CHAR_HEIGHT = 400
GAP_SECONDS = 0.3
FPS = 24


def log(msg):
    print(msg, flush=True)


def load_character(name):
    """Load character image with smart background handling."""
    for ext in ['png', 'jpg', 'jpeg']:
        path = f'assets/{name}.{ext}'
        if os.path.exists(path):
            log(f"   Loading {path}...")
            img = Image.open(path).convert("RGBA")
            data = np.array(img)
            
            # Smart background removal for solid black
            alpha = data[:, :, 3]
            fully_transparent = np.sum(alpha == 0) / alpha.size * 100
            if fully_transparent < 5:
                r, g, b = data[:, :, 0], data[:, :, 1], data[:, :, 2]
                black_mask = (r < 30) & (g < 30) & (b < 30)
                data[black_mask, 3] = 0

            # Scale
            scale = CHAR_HEIGHT / img.height
            new_w = int(img.width * scale)
            img_resized = Image.fromarray(data).resize((new_w, CHAR_HEIGHT), Image.LANCZOS)
            return img_resized
            
    return None


def assemble():
    log("=" * 60)
    log("🎬 VIDEO ASSEMBLY — FRAME-BY-FRAME ENGINE")
    log("=" * 60)

    # --- Load metadata ---
    if not os.path.exists('audio/metadata.json'):
        raise Exception("❌ audio/metadata.json not found")

    with open('audio/metadata.json', 'r') as f:
        metadata = json.load(f)

    # --- Determine Timing ---
    log("\n⏱️ CALCULATING TIMING...")
    clip_timing = []
    current_time = 0.0
    
    # We need to compute durations of audio files. Let's use ffprobe.
    audio_files_to_concat = []
    
    for entry in metadata:
        audio_path = entry['audio_file']
        if not entry.get('exists', False) or not os.path.exists(audio_path):
            continue
            
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', audio_path],
            capture_output=True, text=True
        )
        duration = float(json.loads(probe.stdout)['format']['duration'])
        
        clip_timing.append({
            'start': current_time,
            'end': current_time + duration,
            'speaker': entry['speaker'],
            'text': entry['text'],
            'index': entry['index']
        })
        audio_files_to_concat.append(audio_path)
        
        current_time += duration + GAP_SECONDS
        
    total_duration = current_time
    total_frames = int(total_duration * FPS) + 1
    log(f"   Total duration: {total_duration:.2f}s ({total_frames} frames)")

    # Save timing (needed for captions later)
    os.makedirs('output', exist_ok=True)
    with open('output/timing.json', 'w') as f:
        json.dump(clip_timing, f, indent=2)

    # --- Load Characters ---
    log("\n🎭 LOADING CHARACTERS...")
    characters = {}
    for name in ['peter', 'stewie']:
        img = load_character(name)
        if img:
            characters[name] = img
            log(f"   ✅ {name}: {img.width}x{img.height}")
    
    char_y = CANVAS_H - CHAR_HEIGHT - 80

    # --- Frame-by-Frame Generation ---
    log("\n🖼️ PREPARING BACKGROUND FRAMES...")
    frames_dir = 'output/frames_temp'
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)
    
    # Export background video to frames directly (looping and scaling)
    # Added -qscale:v 2 for highest quality JPEG extraction
    subprocess.run([
        'ffmpeg', '-y', 
        '-stream_loop', '-1', 
        '-i', 'assets/minecraft_bg.mp4',
        '-t', str(total_duration),
        '-vf', f'scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,crop={CANVAS_W}:{CANVAS_H},fps={FPS}',
        '-qscale:v', '2',
        f'{frames_dir}/bg_%05d.jpg'
    ], check=True, capture_output=True)
    
    log("\n🖌️ COMPOSITING CHARACTERS ONTO FRAMES...")
    
    # Prepare a list of which character is speaking at which frame
    frame_speakers = [None] * total_frames
    for timing in clip_timing:
        start_f = int(timing['start'] * FPS)
        end_f = int(timing['end'] * FPS)
        speaker = timing['speaker']
        for f_idx in range(start_f, min(end_f, total_frames)):
            frame_speakers[f_idx] = speaker

    start_time = time.time()
    for f_idx in range(total_frames):
        bg_path = f"{frames_dir}/bg_{f_idx+1:05d}.jpg"
        if not os.path.exists(bg_path):
            break
            
        speaker = frame_speakers[f_idx]
        if speaker and speaker in characters:
            # We have someone speaking, load background and composite!
            bg_img = Image.open(bg_path).convert("RGBA")
            char_img = characters[speaker]
            
            if speaker == 'peter':
                cx = 30
            else:
                cx = CANVAS_W - char_img.width - 30
                
            # Paste with alpha
            bg_img.paste(char_img, (cx, char_y), char_img)
            
            # Save at high quality
            bg_img.convert("RGB").save(bg_path, quality=95)
            
        if f_idx % 200 == 0 and f_idx > 0:
            log(f"   Processed {f_idx}/{total_frames} frames...")

    comp_time = time.time() - start_time
    log(f"   ✅ Compositing done in {comp_time:.1f}s")
    
    # --- Assemble Audio ---
    log("\n🎵 ASSEMBLING AUDIO (EXACT SYNC)...")
    
    # Instead of concat (which drifts), build a precise ffmpeg filter to place each audio exactly 
    # where timing.json says it should be.
    
    filter_complex = []
    ffmpeg_inputs = []
    
    for i, _ in enumerate(audio_files_to_concat):
        audio_path = audio_files_to_concat[i]
        timing = clip_timing[i]
        
        ffmpeg_inputs.extend(['-i', audio_path])
        
        delay_ms = int(timing['start'] * 1000)
        # adelay takes delay times for each channel, we provide both L and R
        filter_complex.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

    # Mix them all together
    mix_inputs = "".join([f"[a{i}]" for i in range(len(audio_files_to_concat))])
    # Use amix with duration=longest to ensure it doesn't cut off early
    filter_complex.append(f"{mix_inputs}amix=inputs={len(audio_files_to_concat)}:duration=longest:dropout_transition=0,volume={len(audio_files_to_concat)}[outa]")
    
    filter_str = ";".join(filter_complex)
    
    cmd = ['ffmpeg', '-y'] + ffmpeg_inputs + [
        '-filter_complex', filter_str,
        '-map', '[outa]',
        '-c:a', 'pcm_s16le',
        '-t', str(total_duration),
        'output/combined_audio.wav'
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    
    # --- Final Video Encoding ---
    log("\n🎞️ ENCODING FINAL VIDEO...")
    output_path = 'output/final_reel.mp4'
    
    encode_cmd = [
        'ffmpeg', '-y',
        '-framerate', str(FPS),
        '-i', f'{frames_dir}/bg_%05d.jpg',
        '-i', 'output/combined_audio.wav',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_path
    ]
    
    subprocess.run(encode_cmd, check=True, capture_output=True)
    
    log(f"✅ DONE: {output_path}")

    # Cleanup temp
    shutil.rmtree(frames_dir, ignore_errors=True)
    for f in ['output/audio_concat.txt', 'output/combined_audio.wav', 'output/silence.wav']:
        if os.path.exists(f):
            os.remove(f)

if __name__ == '__main__':
    assemble()