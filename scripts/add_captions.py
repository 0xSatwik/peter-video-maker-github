"""
Caption step — captions are now baked directly into video frames
by assemble_video.py (word-by-word green highlighting via PIL).

This script is kept as a passthrough for workflow compatibility.
"""
import os


def add_captions():
    video_path = 'output/final_reel.mp4'
    if os.path.exists(video_path):
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"✅ Captions already baked into frames by assemble_video.py")
        print(f"   Video: {video_path} ({size_mb:.1f} MB)")
    else:
        print("❌ No video found at output/final_reel.mp4")


if __name__ == '__main__':
    add_captions()