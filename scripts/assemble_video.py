from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip, TextClip,
    CompositeVideoClip, ColorClip,
    concatenate_audioclips, concatenate_videoclips
)
from PIL import Image
import numpy as np
import os
import json
import glob

# === CONSTANTS ===
CANVAS_W, CANVAS_H = 1080, 1920  # Instagram Reel (9:16)
CHAR_HEIGHT = 500
FPS = 24

# Fonts to try
FONT_CANDIDATES = [
    'DejaVu-Sans-Bold',
    'DejaVu-Sans',
    'Liberation-Sans-Bold',
    'Liberation-Sans',
    'Ubuntu-Bold',
    'Arial-Bold',
    'Arial',
]


def find_working_font():
    """Find a font that works with ImageMagick."""
    for font in FONT_CANDIDATES:
        try:
            TextClip("test", fontsize=20, color='white', font=font, method='label')
            print(f"🔤 Using font: {font}")
            return font
        except Exception:
            continue
    print("⚠️ No preferred font found, using ImageMagick default")
    return None


def load_character(name):
    """Load character image with background removal."""
    for ext in ['png', 'jpg', 'jpeg']:
        path = f'assets/{name}.{ext}'
        if os.path.exists(path):
            img = Image.open(path).convert("RGBA")
            data = np.array(img)

            # Remove near-black bg (peter.png)
            black_mask = (data[:, :, 0] < 40) & \
                         (data[:, :, 1] < 40) & \
                         (data[:, :, 2] < 40)
            # Remove near-white bg (stewie.png)
            white_mask = (data[:, :, 0] > 215) & \
                         (data[:, :, 1] > 215) & \
                         (data[:, :, 2] > 215)
            data[black_mask | white_mask, 3] = 0

            scale = CHAR_HEIGHT / img.height
            new_w = int(img.width * scale)
            img_resized = Image.fromarray(data).resize(
                (new_w, CHAR_HEIGHT), Image.LANCZOS
            )
            return np.array(img_resized)

    print(f"⚠️ Character image not found for '{name}'")
    return None


def assemble():
    print("🎬 Starting professional video assembly...")

    font = find_working_font()

    # --- Load metadata ---
    if not os.path.exists('audio/metadata.json'):
        raise Exception("❌ audio/metadata.json not found. Run generate_audio.py first.")

    with open('audio/metadata.json', 'r') as f:
        metadata = json.load(f)

    # --- Load background video ---
    if not os.path.exists('assets/minecraft_bg.mp4'):
        raise Exception("❌ Background video not found at assets/minecraft_bg.mp4")

    bg_raw = VideoFileClip('assets/minecraft_bg.mp4')

    # Resize to cover full screen (1080x1920)
    bg_scale = max(CANVAS_W / bg_raw.w, CANVAS_H / bg_raw.h)
    bg = bg_raw.resize(bg_scale)

    # Center crop to 1080x1920
    bw, bh = bg.size
    x1 = max(0, int((bw - CANVAS_W) / 2))
    y1 = max(0, int((bh - CANVAS_H) / 2))
    bg = bg.crop(x1=x1, y1=y1, x2=x1 + CANVAS_W, y2=y1 + CANVAS_H)

    # --- Load character images ---
    characters = {}
    for name in ['peter', 'stewie']:
        char_img = load_character(name)
        if char_img is not None:
            characters[name] = char_img
            print(f"✅ Loaded character: {name} ({char_img.shape[1]}x{char_img.shape[0]})")

    # --- Load voice audio clips (supports both .wav and .mp3) ---
    voice_clips = []
    clip_timing = []
    current_time = 0.0

    for entry in metadata:
        audio_path = entry['audio_file']
        if not entry.get('exists', False) or not os.path.exists(audio_path):
            print(f"⚠️ Skipping missing audio: {audio_path}")
            continue

        clip = AudioFileClip(audio_path)
        voice_clips.append(clip)
        clip_timing.append({
            'start': current_time,
            'end': current_time + clip.duration,
            'speaker': entry['speaker'],
            'text': entry['text'],
            'index': entry['index']
        })
        current_time += clip.duration

    if not voice_clips:
        raise Exception("❌ No audio clips found!")

    print(f"🎵 Loaded {len(voice_clips)} voice clips, total duration: {current_time:.1f}s")

    voice_audio = concatenate_audioclips(voice_clips)
    total_duration = voice_audio.duration

    # --- Loop background video using fl_time (keeps it animated!) ---
    bg_duration = bg.duration
    bg_looped = bg.fl_time(lambda t: t % bg_duration, apply_to=['mask', 'audio'])
    bg_looped = bg_looped.set_duration(total_duration)

    # --- Build layers ---
    print("🎞️ Building layers...")

    layers = [bg_looped]

    # Character positions: Peter on LEFT, Stewie on RIGHT
    char_y = CANVAS_H - CHAR_HEIGHT - 100  # 100px from bottom

    # Peter LEFT position
    peter_x = 30
    # Stewie RIGHT position
    stewie_x = CANVAS_W - 30  # will subtract width after loading

    # Place characters — show the SPEAKING character
    for timing in clip_timing:
        speaker = timing['speaker']
        if speaker in characters:
            char_data = characters[speaker]
            char_w = char_data.shape[1]

            # Peter on left, Stewie on right
            if speaker == 'peter':
                cx = peter_x
            else:
                cx = CANVAS_W - char_w - 30  # right-aligned

            char_clip = (
                ImageClip(char_data)
                .set_start(timing['start'])
                .set_end(timing['end'])
                .set_position((cx, char_y))
                .fadein(0.15)
                .fadeout(0.15)
            )
            layers.append(char_clip)

    # --- Compose final video ---
    print("🎞️ Compositing all layers...")
    final_video = CompositeVideoClip(layers, size=(CANVAS_W, CANVAS_H))
    final_video = final_video.set_audio(voice_audio)
    final_video = final_video.set_duration(total_duration)

    os.makedirs('output', exist_ok=True)
    output_path = 'output/final_reel.mp4'

    print(f"💾 Writing video to {output_path}...")
    final_video.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=2
    )

    print(f"✅ Video assembled: {output_path} ({total_duration:.1f}s)")

    # Save timing data for caption script
    with open('output/timing.json', 'w') as f:
        json.dump(clip_timing, f, indent=2)


if __name__ == '__main__':
    assemble()