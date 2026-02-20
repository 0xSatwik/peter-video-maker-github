from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip, TextClip,
    CompositeVideoClip, ColorClip,
    concatenate_audioclips, concatenate_videoclips
)
from moviepy.audio.AudioClip import AudioClip
from PIL import Image
import numpy as np
import subprocess
import os
import json

# === CONSTANTS ===
CANVAS_W, CANVAS_H = 1080, 1920  # Instagram Reel (9:16)
CHAR_HEIGHT = 400
GAP_SECONDS = 0.3  # Small pause between dialogue lines
FPS = 24

FONT_CANDIDATES = [
    'DejaVu-Sans-Bold', 'DejaVu-Sans',
    'Liberation-Sans-Bold', 'Liberation-Sans',
    'Ubuntu-Bold', 'Arial-Bold', 'Arial',
]


def find_working_font():
    for font in FONT_CANDIDATES:
        try:
            TextClip("test", fontsize=20, color='white', font=font, method='label')
            print(f"🔤 Using font: {font}")
            return font
        except Exception:
            continue
    print("⚠️ No preferred font, using default")
    return None


def prepare_background(input_path, output_path, duration):
    """Use ffmpeg to create a looping, scaled, cropped background video.
    This avoids MoviePy's broken resize+crop+loop chain."""

    print(f"🎬 Preparing background video ({duration:.1f}s)...")

    cmd = [
        'ffmpeg', '-y',
        '-stream_loop', '-1',       # loop infinitely
        '-i', input_path,
        '-t', str(duration),         # trim to exact duration
        '-vf', f'scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,'
               f'crop={CANVAS_W}:{CANVAS_H}',
        '-an',                       # no audio from bg
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-r', str(FPS),
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ ffmpeg stderr: {result.stderr[-500:]}")
        raise Exception("ffmpeg background prep failed")

    print(f"✅ Background ready: {output_path}")


def load_character(name):
    """Load character image. Removes black background if image isn't already transparent."""
    for ext in ['png', 'jpg', 'jpeg']:
        path = f'assets/{name}.{ext}'
        if os.path.exists(path):
            img = Image.open(path).convert("RGBA")
            data = np.array(img)

            # Check if image already has meaningful transparency
            alpha = data[:, :, 3]
            transparent_pct = np.sum(alpha < 250) / alpha.size

            if transparent_pct < 0.05:
                # Image has almost no transparency → has a solid background
                # Remove ONLY near-black pixels (bg), preserve everything else
                print(f"  🔧 {name}: removing black background...")
                black_mask = (data[:, :, 0] < 30) & \
                             (data[:, :, 1] < 30) & \
                             (data[:, :, 2] < 30)
                data[black_mask, 3] = 0
            else:
                print(f"  ✅ {name}: already transparent ({transparent_pct*100:.0f}%)")

            # Scale to target height
            scale = CHAR_HEIGHT / img.height
            new_w = int(img.width * scale)
            img_resized = Image.fromarray(data).resize((new_w, CHAR_HEIGHT), Image.LANCZOS)

            return np.array(img_resized)

    print(f"⚠️ Character image not found for '{name}'")
    return None


def make_silence(duration, fps=44100):
    """Create a silent audio clip."""
    return AudioClip(lambda t: [0, 0], duration=duration, fps=fps)


def assemble():
    print("🎬 Starting video assembly...")

    font = find_working_font()

    # --- Load metadata ---
    if not os.path.exists('audio/metadata.json'):
        raise Exception("❌ audio/metadata.json not found")

    with open('audio/metadata.json', 'r') as f:
        metadata = json.load(f)

    # --- Load character images ---
    characters = {}
    for name in ['peter', 'stewie']:
        char_img = load_character(name)
        if char_img is not None:
            characters[name] = char_img
            print(f"✅ Loaded {name}: {char_img.shape[1]}x{char_img.shape[0]}, "
                  f"has_alpha={'yes' if char_img.shape[2] == 4 else 'no'}")

    # --- Load audio clips WITH gaps between them ---
    audio_segments = []
    clip_timing = []
    current_time = 0.0

    for entry in metadata:
        audio_path = entry['audio_file']
        if not entry.get('exists', False) or not os.path.exists(audio_path):
            print(f"⚠️ Skipping missing: {audio_path}")
            continue

        clip = AudioFileClip(audio_path)

        audio_segments.append(clip)
        clip_timing.append({
            'start': current_time,
            'end': current_time + clip.duration,
            'speaker': entry['speaker'],
            'text': entry['text'],
            'index': entry['index']
        })
        current_time += clip.duration

        # Add a small gap between clips
        gap = make_silence(GAP_SECONDS, fps=clip.fps)
        audio_segments.append(gap)
        current_time += GAP_SECONDS

    if not audio_segments:
        raise Exception("❌ No audio clips found!")

    voice_audio = concatenate_audioclips(audio_segments)
    total_duration = voice_audio.duration
    print(f"🎵 {len(clip_timing)} clips, total: {total_duration:.1f}s (with {GAP_SECONDS}s gaps)")

    # --- Prepare background video (ffmpeg: loop + scale + crop) ---
    os.makedirs('output', exist_ok=True)
    bg_temp = 'output/bg_prepared.mp4'
    prepare_background('assets/minecraft_bg.mp4', bg_temp, total_duration)
    bg_video = VideoFileClip(bg_temp)

    # --- Build layers ---
    print("🎞️ Building layers...")
    layers = [bg_video]

    # Character positions
    char_y = CANVAS_H - CHAR_HEIGHT - 80

    for timing in clip_timing:
        speaker = timing['speaker']
        if speaker not in characters:
            continue

        char_data = characters[speaker]
        char_w = char_data.shape[1]

        # Peter on LEFT, Stewie on RIGHT
        if speaker == 'peter':
            cx = 30
        else:
            cx = CANVAS_W - char_w - 30

        char_clip = (
            ImageClip(char_data)
            .set_start(timing['start'])
            .set_end(timing['end'])
            .set_position((cx, char_y))
        )
        layers.append(char_clip)

    # --- Compose ---
    print("🎞️ Compositing...")
    final_video = CompositeVideoClip(layers, size=(CANVAS_W, CANVAS_H))
    final_video = final_video.set_audio(voice_audio)
    final_video = final_video.set_duration(total_duration)

    output_path = 'output/final_reel.mp4'
    print(f"💾 Writing {output_path}...")
    final_video.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=2
    )

    print(f"✅ Done: {output_path} ({total_duration:.1f}s)")

    with open('output/timing.json', 'w') as f:
        json.dump(clip_timing, f, indent=2)

    # Cleanup temp
    if os.path.exists(bg_temp):
        os.remove(bg_temp)


if __name__ == '__main__':
    assemble()