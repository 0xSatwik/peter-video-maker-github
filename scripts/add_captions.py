"""
Add highlight captions to the assembled video.
Uses timing.json from the assembly step (no Whisper needed).
"""
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import json
import os

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

    video = VideoFileClip('output/final_reel.mp4')

    timing_path = 'output/timing.json'
    if not os.path.exists(timing_path):
        print("❌ timing.json not found. Run assemble_video.py first.")
        return

    with open(timing_path, 'r', encoding='utf-8') as f:
        timing = json.load(f)

    print(f"📄 Loaded {len(timing)} caption entries")

    font = find_working_font()
    if font:
        print(f"🔤 Using font: {font}")

    caption_clips = []

    # Place highlight captions in the middle of the screen
    # (above the character area, below the clean top area)
    caption_y = 1050  # Middle area of the 1920px height

    for entry in timing:
        text = entry['text']
        start = entry['start']
        end = entry['end']
        duration = end - start

        # Split into readable chunks (~7 words)
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
                    'fontsize': 46,
                    'color': 'yellow',
                    'stroke_color': 'black',
                    'stroke_width': 2.5,
                    'method': 'caption',
                    'size': (900, None),
                    'align': 'center',
                }
                if font:
                    kwargs['font'] = font

                txt = TextClip(chunk, **kwargs)
                txt = txt.set_position(('center', caption_y))
                txt = txt.set_start(chunk_start).set_end(chunk_end)
                txt = txt.fadein(0.1).fadeout(0.1)

                caption_clips.append(txt)

            except Exception as e:
                print(f"⚠️ Failed caption for '{chunk}': {e}")

    if not caption_clips:
        print("⚠️ No captions created, keeping video as-is.")
        return

    print(f"✨ Created {len(caption_clips)} caption segments")

    temp_output = 'output/final_reel_captioned.mp4'
    final = CompositeVideoClip([video] + caption_clips)
    final.write_videofile(
        temp_output,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        preset='medium',
        threads=2
    )
    
    # Close clips to release file handles
    video.close()
    final.close()
    
    # Replace original with captioned version
    import shutil
    shutil.move(temp_output, 'output/final_reel.mp4')
    
    print("✅ Final video with captions: output/final_reel.mp4")

if __name__ == '__main__':
    add_captions()