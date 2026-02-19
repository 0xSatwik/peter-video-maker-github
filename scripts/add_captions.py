"""
Add captions to the assembled video.
Uses the script file + audio timing instead of Whisper transcription.
This is faster, more accurate, and removes the openai-whisper dependency.
"""
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
import json
import os


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

    # The assemble_video.py already adds dialogue text in the bottom panel.
    # This script adds word-by-word highlight captions for extra polish
    # in the MIDDLE area (between top video and bottom characters).

    caption_clips = []

    for entry in timing:
        text = entry['text']
        start = entry['start']
        end = entry['end']
        speaker = entry.get('speaker', 'unknown')
        duration = end - start

        # Split long text into chunks of ~6-8 words for readability
        words = text.split()
        chunks = []
        chunk_size = 7
        for i in range(0, len(words), chunk_size):
            chunks.append(' '.join(words[i:i + chunk_size]))

        # Distribute chunks evenly across the clip duration
        if not chunks:
            continue

        chunk_duration = duration / len(chunks)

        for ci, chunk in enumerate(chunks):
            chunk_start = start + (ci * chunk_duration)
            chunk_end = chunk_start + chunk_duration

            try:
                # Caption background pill
                txt = TextClip(
                    chunk,
                    fontsize=44,
                    color='white',
                    font='DejaVu-Sans-Bold',
                    stroke_color='black',
                    stroke_width=2,
                    method='caption',
                    size=(900, None),
                    align='center'
                )

                # Position in the transition zone between top and bottom
                # (around y=900, just above the bottom panel)
                txt = txt.set_position(('center', 880))
                txt = txt.set_start(chunk_start).set_end(chunk_end)
                txt = txt.crossfadein(0.15).crossfadeout(0.15)

                caption_clips.append(txt)

            except Exception as e:
                print(f"⚠️ Failed to create caption for chunk '{chunk}': {e}")

    if not caption_clips:
        print("⚠️ No caption clips created. Saving video without captions.")
        # Just copy the video
        video.write_videofile('output/final_reel.mp4', fps=24, codec='libx264', audio_codec='aac')
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