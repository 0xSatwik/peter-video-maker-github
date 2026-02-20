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
import sys

# === CONSTANTS ===
CANVAS_W, CANVAS_H = 1080, 1920
CHAR_HEIGHT = 400
GAP_SECONDS = 0.3
FPS = 24

FONT_CANDIDATES = [
    'DejaVu-Sans-Bold', 'DejaVu-Sans',
    'Liberation-Sans-Bold', 'Liberation-Sans',
    'Ubuntu-Bold', 'Arial-Bold', 'Arial',
]


def log(msg):
    """Print with flush for GitHub Actions live logging."""
    print(msg, flush=True)


def find_working_font():
    for font in FONT_CANDIDATES:
        try:
            TextClip("test", fontsize=20, color='white', font=font, method='label')
            log(f"🔤 Using font: {font}")
            return font
        except Exception:
            continue
    log("⚠️ No preferred font, using default")
    return None


def prepare_background(input_path, output_path, duration):
    """Use ffmpeg to create a looping, scaled, cropped background video."""

    log(f"🎬 Preparing background video...")
    log(f"   Input: {input_path} (exists={os.path.exists(input_path)})")
    log(f"   Target: {CANVAS_W}x{CANVAS_H}, {duration:.1f}s, {FPS}fps")

    # First check the source video
    probe_cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration:stream=width,height,nb_frames,r_frame_rate',
        '-of', 'json', input_path
    ]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    log(f"   Source probe: {probe_result.stdout.strip()}")

    cmd = [
        'ffmpeg', '-y',
        '-stream_loop', '-1',
        '-i', input_path,
        '-t', str(duration),
        '-vf', (
            f'scale={CANVAS_W}:{CANVAS_H}:'
            f'force_original_aspect_ratio=increase,'
            f'crop={CANVAS_W}:{CANVAS_H}'
        ),
        '-an',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-r', str(FPS),
        output_path
    ]

    log(f"   CMD: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log(f"   ❌ ffmpeg FAILED (exit={result.returncode})")
        log(f"   STDERR: {result.stderr[-1000:]}")
        raise Exception("ffmpeg background prep failed")

    # Verify output
    probe2 = subprocess.run(
        ['ffprobe', '-v', 'error',
         '-show_entries', 'format=duration:stream=width,height,nb_frames',
         '-of', 'json', output_path],
        capture_output=True, text=True
    )
    log(f"   Output probe: {probe2.stdout.strip()}")
    log(f"   Output size: {os.path.getsize(output_path) / 1024:.0f}KB")
    log(f"✅ Background ready")


def load_character(name):
    """Load character image with smart background handling."""
    for ext in ['png', 'jpg', 'jpeg']:
        path = f'assets/{name}.{ext}'
        if os.path.exists(path):
            log(f"   Loading {path} ({os.path.getsize(path)/1024:.0f}KB)...")

            try:
                img = Image.open(path).convert("RGBA")
                data = np.array(img)
                log(f"   Raw size: {img.width}x{img.height}, channels={data.shape[2]}")

                # Check transparency
                alpha = data[:, :, 3]
                fully_opaque = np.sum(alpha == 255) / alpha.size * 100
                fully_transparent = np.sum(alpha == 0) / alpha.size * 100
                log(f"   Alpha: {fully_opaque:.1f}% opaque, {fully_transparent:.1f}% transparent")

                if fully_transparent < 5:
                    # Almost no transparency → remove black background
                    log(f"   🔧 Removing black background...")
                    r, g, b = data[:, :, 0], data[:, :, 1], data[:, :, 2]
                    black_mask = (r < 30) & (g < 30) & (b < 30)
                    pixels_removed = np.sum(black_mask)
                    data[black_mask, 3] = 0
                    log(f"   Removed {pixels_removed} black pixels ({pixels_removed/alpha.size*100:.1f}%)")

                # Scale
                scale = CHAR_HEIGHT / img.height
                new_w = int(img.width * scale)
                img_resized = Image.fromarray(data).resize((new_w, CHAR_HEIGHT), Image.LANCZOS)
                result = np.array(img_resized)
                log(f"   ✅ Final: {new_w}x{CHAR_HEIGHT}, shape={result.shape}")
                return result

            except Exception as e:
                log(f"   ❌ FAILED to load {name}: {e}")
                import traceback
                traceback.print_exc()
                return None

    log(f"   ❌ No image found for '{name}' in assets/")
    return None


def make_silence(duration, fps=44100):
    return AudioClip(lambda t: [0, 0], duration=duration, fps=fps)


def assemble():
    log("=" * 60)
    log("🎬 VIDEO ASSEMBLY — DEBUG MODE")
    log("=" * 60)

    font = find_working_font()

    # --- Load metadata ---
    log("\n📄 LOADING METADATA...")
    if not os.path.exists('audio/metadata.json'):
        raise Exception("❌ audio/metadata.json not found")

    with open('audio/metadata.json', 'r') as f:
        metadata = json.load(f)

    log(f"   Entries in metadata: {len(metadata)}")
    for i, entry in enumerate(metadata):
        log(f"   [{i:2d}] speaker={entry['speaker']:8s} exists={entry.get('exists',False)} "
            f"file={entry['audio_file']} text=\"{entry['text'][:40]}...\"")

    # --- List audio files actually on disk ---
    log("\n📁 AUDIO FILES ON DISK:")
    for f in sorted(os.listdir('audio')):
        fpath = os.path.join('audio', f)
        log(f"   {f} ({os.path.getsize(fpath)/1024:.0f}KB)")

    # --- Load character images ---
    log("\n🎭 LOADING CHARACTERS...")
    characters = {}
    for name in ['peter', 'stewie']:
        log(f"\n   --- {name.upper()} ---")
        char_img = load_character(name)
        if char_img is not None:
            characters[name] = char_img
        else:
            log(f"   ⚠️ {name} NOT loaded!")

    log(f"\n   Characters available: {list(characters.keys())}")

    # --- Load audio clips ---
    log("\n🎵 LOADING AUDIO CLIPS...")
    audio_segments = []
    clip_timing = []
    current_time = 0.0

    for entry in metadata:
        audio_path = entry['audio_file']
        speaker = entry['speaker']

        if not entry.get('exists', False) or not os.path.exists(audio_path):
            log(f"   ⚠️ SKIP (missing): {audio_path}")
            continue

        clip = AudioFileClip(audio_path)
        audio_segments.append(clip)

        timing_entry = {
            'start': current_time,
            'end': current_time + clip.duration,
            'speaker': speaker,
            'text': entry['text'],
            'index': entry['index']
        }
        clip_timing.append(timing_entry)

        # Check if this speaker has a character loaded
        has_char = speaker in characters
        log(f"   [{entry['index']:2d}] {speaker:8s} | {clip.duration:5.1f}s | "
            f"t={current_time:.1f}-{current_time+clip.duration:.1f} | "
            f"char={'✅' if has_char else '❌'} | \"{entry['text'][:35]}...\"")

        current_time += clip.duration

        # Gap
        gap = make_silence(GAP_SECONDS, fps=clip.fps)
        audio_segments.append(gap)
        current_time += GAP_SECONDS

    if not audio_segments:
        raise Exception("❌ No audio clips found!")

    voice_audio = concatenate_audioclips(audio_segments)
    total_duration = voice_audio.duration
    log(f"\n   Total clips: {len(clip_timing)}")
    log(f"   Total duration: {total_duration:.1f}s")

    peter_count = sum(1 for t in clip_timing if t['speaker'] == 'peter')
    stewie_count = sum(1 for t in clip_timing if t['speaker'] == 'stewie')
    other_count = sum(1 for t in clip_timing if t['speaker'] not in ('peter', 'stewie'))
    log(f"   Peter lines: {peter_count}, Stewie lines: {stewie_count}, Other: {other_count}")

    # --- Prepare background ---
    log("\n🎬 PREPARING BACKGROUND VIDEO...")
    os.makedirs('output', exist_ok=True)
    bg_temp = 'output/bg_prepared.mp4'
    prepare_background('assets/minecraft_bg.mp4', bg_temp, total_duration)

    bg_video = VideoFileClip(bg_temp)
    log(f"   Loaded bg_video: {bg_video.w}x{bg_video.h}, "
        f"duration={bg_video.duration:.1f}s, fps={bg_video.fps}")

    # --- Build layers ---
    log("\n🎞️ BUILDING LAYERS...")
    layers = [bg_video]

    char_y = CANVAS_H - CHAR_HEIGHT - 80
    log(f"   Character Y position: {char_y}")

    for i, timing in enumerate(clip_timing):
        speaker = timing['speaker']

        if speaker not in characters:
            log(f"   [{i}] ❌ SKIP — no character for speaker '{speaker}'")
            continue

        char_data = characters[speaker]
        char_w = char_data.shape[1]

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

        log(f"   [{i}] {speaker:8s} at x={cx:4d} y={char_y} "
            f"t={timing['start']:.1f}-{timing['end']:.1f}")

    log(f"\n   Total layers: {len(layers)} (1 bg + {len(layers)-1} characters)")

    # --- Compose ---
    log("\n🎞️ COMPOSITING FINAL VIDEO...")
    final_video = CompositeVideoClip(layers, size=(CANVAS_W, CANVAS_H))
    final_video = final_video.set_audio(voice_audio)
    final_video = final_video.set_duration(total_duration)

    output_path = 'output/final_reel.mp4'
    log(f"💾 Writing {output_path}...")
    final_video.write_videofile(
        output_path,
        fps=FPS,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=2
    )

    log(f"\n✅ DONE: {output_path} ({total_duration:.1f}s)")

    with open('output/timing.json', 'w') as f:
        json.dump(clip_timing, f, indent=2)

    if os.path.exists(bg_temp):
        os.remove(bg_temp)


if __name__ == '__main__':
    assemble()