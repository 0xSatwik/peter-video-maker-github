"""
Add captions to the assembled video.
Uses the script file + audio timing instead of Whisper transcription.
This is faster, more accurate, and removes the openai-whisper dependency.
"""
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import json
import os


# Fonts to try in order (same list as assemble_video.py)
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
            return font
        except Exception:
            continue
    return None


def add_captions():
    print("📝 Adding auto-captions...")

    # Load the assembled video
    video = VideoFileClip('output/final_reel.mp4')

    # Load timing data from assembly step
    timing_path = 'output/timing.json'
    if not os.path.exists(timing_path):
        print("❌ timing.json not found. Run assemble_video.py first.")
        return

    with open(timing_path, 'r', encoding='utf-8') as f:
        timing = json.load(f)

    print(f"📄 Loaded {len(timing)} caption entries")

    # Find working font
    font = find_working_font()
    if font:
        print(f"🔤 Using font: {font}")

    caption_clips = []

    for entry in timing:
        text = entry['text']
        start = entry['start']
        end = entry['end']
        duration = end - start

        # Split long text into chunks of ~7 words for readability
        words = text.split()
        chunks = []
        chunk_size = 7
        for i in range(0, len(words), chunk_size):
            chunks.append(' '.join(words[i:i + chunk_size]))

        if not chunks:
            continue

        chunk_duration = duration / len(chunks)

        for ci, chunk in enumerate(chunks):
            chunk_start = start + (ci * chunk_duration)
            chunk_end = chunk_start + chunk_duration

            try:
                kwargs = {
                    'fontsize': 44,
                    'color': 'white',
                    'stroke_color': 'black',
                    'stroke_width': 2,
                    'method': 'caption',
                    'size': (900, None),
                    'align': 'center',
                }
                if font:
                    kwargs['font'] = font

                txt = TextClip(chunk, **kwargs)
                txt = txt.set_position(('center', 880))
                txt = txt.set_start(chunk_start).set_end(chunk_end)
                txt = txt.fadein(0.15).fadeout(0.15)

                caption_clips.append(txt)

            except Exception as e:
                print(f"⚠️ Failed to create caption for '{chunk}': {e}")

    if not caption_clips:
        print("⚠️ No captions created, keeping video as-is.")
        return

    print(f"✨ Created {len(caption_clips)} caption segments")

    # Composite captions on top of the video
    final = CompositeVideoClip([video] + caption_clips)
    final.write_videofile(
        'output/final_reel.mp4',
        fps=24,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=2
    )
    print("✅ Final video with captions: output/final_reel.mp4")


if __name__ == '__main__':
    add_captions()