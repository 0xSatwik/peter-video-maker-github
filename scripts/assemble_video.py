from moviepy.editor import (
    VideoFileClip, AudioFileClip, ImageClip, TextClip,
    CompositeVideoClip, CompositeAudioClip, ColorClip,
    concatenate_audioclips, concatenate_videoclips
)
from PIL import Image
import numpy as np
import os
import json

# === CONSTANTS ===
CANVAS_W, CANVAS_H = 1080, 1920
TOP_H = 960       # Top half: background video (clean for overlay editing)
BOTTOM_H = 960    # Bottom half: characters + captions panel
CHAR_HEIGHT = 500  # Character image height
CHAR_MARGIN = 30   # Margin from left edge
FPS = 24

# Character colors for name badges
CHAR_COLORS = {
    'peter': {'badge': '#2E86AB', 'text': 'white'},
    'stewie': {'badge': '#A23B72', 'text': 'white'},
}

# Fonts to try in order of preference (CI may not have all fonts)
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
    """Find a font that actually works with ImageMagick on this system."""
    for font in FONT_CANDIDATES:
        try:
            TextClip("test", fontsize=20, color='white', font=font, method='label')
            print(f"🔤 Using font: {font}")
            return font
        except Exception:
            continue
    print("⚠️ No preferred font found, using ImageMagick default")
    return None


def loop_audio(audio_clip, target_duration):
    """Loop an audio clip to fill target_duration (moviepy 1.0.3 safe)."""
    if audio_clip.duration >= target_duration:
        return audio_clip.subclip(0, target_duration)
    loops_needed = int(target_duration / audio_clip.duration) + 1
    looped = concatenate_audioclips([audio_clip] * loops_needed)
    return looped.subclip(0, target_duration)


def loop_video(video_clip, target_duration):
    """Loop a video clip to fill target_duration (moviepy 1.0.3 safe)."""
    if video_clip.duration >= target_duration:
        return video_clip.subclip(0, target_duration)
    loops_needed = int(target_duration / video_clip.duration) + 1
    looped = concatenate_videoclips([video_clip] * loops_needed)
    return looped.subclip(0, target_duration)


def load_character(name):
    """Load and prepare a character image with background removal."""
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

            # Resize to target height
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

    # --- Find a working font ---
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

    # Resize background to fill top half (1080 x 960)
    bg_scale = max(CANVAS_W / bg_raw.w, TOP_H / bg_raw.h)
    bg = bg_raw.resize(bg_scale)

    # Center crop to exactly 1080x960
    bw, bh = bg.size
    x1 = max(0, int((bw - CANVAS_W) / 2))
    y1 = max(0, int((bh - TOP_H) / 2))
    bg = bg.crop(x1=x1, y1=y1, x2=x1 + CANVAS_W, y2=y1 + TOP_H)

    # --- Load character images ---
    characters = {}
    for name in ['peter', 'stewie']:
        char_img = load_character(name)
        if char_img is not None:
            characters[name] = char_img
            print(f"✅ Loaded character: {name} ({char_img.shape[1]}x{char_img.shape[0]})")

    # --- Load voice audio clips and calculate timing ---
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

    # Concatenate voice audio
    voice_audio = concatenate_audioclips(voice_clips)
    total_duration = voice_audio.duration

    final_audio = voice_audio

    # --- Loop background video to match total duration ---
    bg = loop_video(bg, total_duration)

    # --- Build the video layers ---
    print("🎞️ Building layers...")

    # Layer 1: Full dark canvas
    canvas = ColorClip(
        size=(CANVAS_W, CANVAS_H), color=(10, 10, 18)
    ).set_duration(total_duration)

    # Layer 2: Background video in top half
    bg_top = bg.set_position((0, 0))

    # Layer 3: Dark bottom panel
    bottom_panel = ColorClip(
        size=(CANVAS_W, BOTTOM_H), color=(18, 18, 30)
    ).set_opacity(0.95).set_duration(total_duration).set_position((0, TOP_H))

    # Subtle divider line between top and bottom
    divider = ColorClip(
        size=(CANVAS_W, 3), color=(80, 180, 255)
    ).set_opacity(0.6).set_duration(total_duration).set_position((0, TOP_H))

    layers = [canvas, bg_top, bottom_panel, divider]

    # Layer 4: Character images (timed to their dialogue)
    for timing in clip_timing:
        speaker = timing['speaker']
        if speaker in characters:
            char_data = characters[speaker]
            char_clip = (
                ImageClip(char_data)
                .set_start(timing['start'])
                .set_end(timing['end'])
                .set_position((CHAR_MARGIN, TOP_H + (BOTTOM_H - CHAR_HEIGHT) // 2))
                .fadein(0.2)
                .fadeout(0.2)
            )
            layers.append(char_clip)

    # Layer 5: Speaker name badges
    for timing in clip_timing:
        speaker = timing['speaker']
        colors = CHAR_COLORS.get(speaker, {'badge': '#555555', 'text': 'white'})

        try:
            kwargs = {
                'fontsize': 36,
                'color': colors['text'],
                'bg_color': colors['badge'],
                'method': 'label',
            }
            if font:
                kwargs['font'] = font

            name_clip = (
                TextClip(speaker.upper(), **kwargs)
                .set_start(timing['start'])
                .set_end(timing['end'])
                .set_position((CHAR_MARGIN + 10, TOP_H + 20))
                .fadein(0.2)
                .fadeout(0.2)
            )
            layers.append(name_clip)
        except Exception as e:
            print(f"⚠️ Could not create name badge for {speaker}: {e}")

    # Layer 6: Dialogue text on the right side of bottom panel
    for timing in clip_timing:
        text = timing['text']
        text_x = 400
        text_w = CANVAS_W - text_x - 40

        try:
            kwargs = {
                'fontsize': 40,
                'color': 'white',
                'stroke_color': 'black',
                'stroke_width': 1.5,
                'method': 'caption',
                'size': (text_w, None),
                'align': 'West',
            }
            if font:
                kwargs['font'] = font

            txt_clip = (
                TextClip(text, **kwargs)
                .set_start(timing['start'])
                .set_end(timing['end'])
                .set_position((text_x, TOP_H + BOTTOM_H // 2 - 80))
                .fadein(0.3)
                .fadeout(0.2)
            )
            layers.append(txt_clip)
        except Exception as e:
            print(f"⚠️ Could not create text clip: {e}")

    # --- Compose final video ---
    print("🎞️ Compositing all layers...")
    final_video = CompositeVideoClip(layers, size=(CANVAS_W, CANVAS_H))
    final_video = final_video.set_audio(final_audio)
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