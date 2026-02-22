from PIL import Image, ImageDraw, ImageFont
import numpy as np
import subprocess
import os
import json
import time
import shutil

# === CONSTANTS ===
CANVAS_W, CANVAS_H = 1080, 1920
CHAR_HEIGHT_BASE = 750  # Base character height
CHAR_SCALES = {
    'peter': 1.10,      # Peter size +10%
    'stewie': 0.95,     # Stewie size -5%
}
GAP_SECONDS = 0.3
FPS = 24
CAPTION_Y = 834         # Moved down ~7% (from 700 to 834)
CAPTION_FONT_SIZE = 68  # Bold, large, readable on mobile
CAPTION_PADDING = 50    # Horizontal padding on each side to prevent text going off-screen
CHUNK_SIZE = 4          # ~4 words per caption line (short punchy chunks)
LINE_SPACING = 12       # Extra pixels between wrapped caption lines


def log(msg):
    print(msg, flush=True)


def find_font():
    """Find the best thick/geometric font available on the system."""
    # Frick/Komika/TheBoldFont style geometric thick fonts
    candidates = [
        '/usr/share/fonts/truetype/montserrat/Montserrat-Black.ttf',      # Best match for Frick-style reel fonts
        '/usr/share/fonts/truetype/montserrat/Montserrat-ExtraBold.ttf',
        '/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf',
        '/usr/share/fonts/truetype/roboto/hinted/Roboto-Black.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            log(f"   🔤 Using font: {path}")
            return ImageFont.truetype(path, CAPTION_FONT_SIZE)
    log("   ⚠️ No custom font found, using default")
    return ImageFont.load_default()


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

            # Scale to specific character height
            target_h = int(CHAR_HEIGHT_BASE * CHAR_SCALES.get(name, 1.0))
            scale = target_h / img.height
            new_w = int(img.width * scale)
            img_resized = Image.fromarray(data).resize((new_w, target_h), Image.LANCZOS)
            return img_resized
            
    return None


def draw_caption_with_highlight(draw, text, active_word_idx, font, canvas_w, y_pos):
    """
    Draw ALL-CAPS caption text with word-by-word green highlighting.
    All words are white, the active word is bright green.
    Heavy black stroke on all text for readability.
    Auto-wraps to multiple lines if text is too wide for the canvas.
    """
    words = text.upper().split()
    if not words:
        return
    
    max_width = canvas_w - (CAPTION_PADDING * 2)  # Available width with padding
    space_width = draw.textlength(" ", font=font)
    stroke_width = 4  # Heavy black stroke
    
    # Get font height for line spacing
    bbox = font.getbbox("A")
    line_height = bbox[3] - bbox[1] + LINE_SPACING
    
    # --- Word-wrap: split words into lines that fit within max_width ---
    lines = []          # Each line is a list of (word, original_index) tuples
    current_line = []
    current_width = 0
    
    for i, word in enumerate(words):
        word_w = draw.textlength(word, font=font)
        needed = word_w + (space_width if current_line else 0)
        
        if current_line and current_width + needed > max_width:
            # Start a new line
            lines.append(current_line)
            current_line = [(word, i)]
            current_width = word_w
        else:
            current_line.append((word, i))
            current_width += needed
    
    if current_line:
        lines.append(current_line)
    
    # --- Draw each line centered ---
    total_text_height = len(lines) * line_height
    start_y = y_pos - total_text_height / 2  # Center vertically around y_pos
    
    for line_idx, line_words in enumerate(lines):
        # Calculate line width
        word_widths = [draw.textlength(w, font=font) for w, _ in line_words]
        line_width = sum(word_widths) + space_width * (len(line_words) - 1)
        
        # Center this line horizontally
        x = (canvas_w - line_width) / 2
        line_y = start_y + line_idx * line_height
        
        for j, (word, orig_idx) in enumerate(line_words):
            # Active word = bright green, others = white
            if orig_idx == active_word_idx:
                fill_color = '#00FF00'  # Bright green
            else:
                fill_color = '#FFFFFF'  # White
            
            # Draw the word with black stroke
            draw.text(
                (x, line_y), word, font=font,
                fill=fill_color,
                stroke_fill='#000000',
                stroke_width=stroke_width
            )
            
            x += word_widths[j] + space_width


def assemble():
    log("=" * 60)
    log("🎬 VIDEO ASSEMBLY — PREMIUM FRAME-BY-FRAME ENGINE")
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

    # Save timing
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
    

    # --- Load Font for Captions ---
    log("\n🔤 LOADING CAPTION FONT...")
    font = find_font()

    # --- Prepare word-level timing ---
    # For each clip, split text into chunks of ~CHUNK_SIZE words.
    # Within each chunk, assign each word an equal timeslice.
    log("\n📝 COMPUTING WORD-LEVEL TIMING...")
    
    # Build a list of (start, end, chunk_text, active_word_idx) for every sub-frame
    caption_events = []  # list of {start, end, chunk_text, active_word_idx}
    
    for timing in clip_timing:
        text = timing['text']
        words = text.split()
        duration = timing['end'] - timing['start']
        
        # Split into small chunks
        chunks = []
        for i in range(0, len(words), CHUNK_SIZE):
            chunks.append(words[i:i + CHUNK_SIZE])
        
        if not chunks:
            continue
        
        chunk_duration = duration / len(chunks)
        
        for ci, chunk_words in enumerate(chunks):
            chunk_start = timing['start'] + ci * chunk_duration
            chunk_text = ' '.join(chunk_words)
            word_duration = chunk_duration / len(chunk_words)
            
            for wi in range(len(chunk_words)):
                word_start = chunk_start + wi * word_duration
                word_end = word_start + word_duration
                caption_events.append({
                    'start': word_start,
                    'end': word_end,
                    'chunk_text': chunk_text,
                    'active_word_idx': wi,
                })
    
    log(f"   Created {len(caption_events)} word-highlight events")

    # --- Frame-by-Frame Generation ---
    log("\n🖼️ PREPARING BACKGROUND FRAMES...")
    frames_dir = 'output/frames_temp'
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)
    
    # Full-screen background (crop to fill, no black bars)
    # Enhanced with denoise → lanczos scale → sharpen → color boost
    subprocess.run([
        'ffmpeg', '-y',
        '-stream_loop', '-1', 
        '-i', 'assets/minecraft_bg.mp4',
        '-t', str(total_duration),
        '-vf', f'hqdn3d=1.5:1.5:6:6,scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase:flags=lanczos,crop={CANVAS_W}:{CANVAS_H},unsharp=5:5:1.0:5:5:0.0,eq=saturation=1.2:contrast=1.05,fps={FPS}',
        '-an',
        '-vsync', '0',
        f'{frames_dir}/bg_%05d.png'
    ], check=True, capture_output=True)
    
    log("\n🖌️ COMPOSITING CHARACTERS + CAPTIONS ONTO FRAMES...")
    
    # Pre-compute speaker per frame
    frame_speakers = [None] * total_frames
    for timing in clip_timing:
        start_f = int(timing['start'] * FPS)
        end_f = int(timing['end'] * FPS)
        speaker = timing['speaker']
        for f_idx in range(start_f, min(end_f, total_frames)):
            frame_speakers[f_idx] = speaker

    start_time = time.time()
    for f_idx in range(total_frames):
        bg_path = f"{frames_dir}/bg_{f_idx+1:05d}.png"
        if not os.path.exists(bg_path):
            break
        
        current_time_sec = f_idx / FPS
        speaker = frame_speakers[f_idx]
        
        # Load the background frame
        bg_img = Image.open(bg_path).convert("RGBA")
        
        # --- Composite character ---
        if speaker and speaker in characters:
            char_img = characters[speaker]
            
            # Recalculate dynamic Y position based on this specific character's height
            char_y = CANVAS_H - char_img.height + 40  # Anchor bottom +40px cutoff
            
            if speaker == 'peter':
                cx = 30  # Left side
            else:
                cx = CANVAS_W - char_img.width - 30  # Right side
            bg_img.paste(char_img, (cx, char_y), char_img)
        
        # --- Render word-by-word caption with green highlight ---
        draw = ImageDraw.Draw(bg_img)
        for event in caption_events:
            if event['start'] <= current_time_sec < event['end']:
                draw_caption_with_highlight(
                    draw,
                    event['chunk_text'],
                    event['active_word_idx'],
                    font,
                    CANVAS_W,
                    CAPTION_Y
                )
                break  # Only one caption at a time
        
        # Save as PNG (lossless)
        bg_img.convert("RGB").save(bg_path)
            
        if f_idx % 200 == 0 and f_idx > 0:
            log(f"   Processed {f_idx}/{total_frames} frames...")

    comp_time = time.time() - start_time
    log(f"   ✅ Compositing done in {comp_time:.1f}s")
    
    # --- Assemble Audio ---
    log("\n🎵 ASSEMBLING AUDIO (EXACT SYNC)...")
    
    filter_complex = []
    ffmpeg_inputs = []
    
    for i, _ in enumerate(audio_files_to_concat):
        audio_path = audio_files_to_concat[i]
        timing = clip_timing[i]
        
        ffmpeg_inputs.extend(['-i', audio_path])
        
        delay_ms = int(timing['start'] * 1000)
        filter_complex.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

    mix_inputs = "".join([f"[a{i}]" for i in range(len(audio_files_to_concat))])
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
        '-i', f'{frames_dir}/bg_%05d.png',
        '-i', 'output/combined_audio.wav',
        '-c:v', 'libx264', 
        '-preset', 'slow',
        '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
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