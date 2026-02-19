from moviepy.editor import *
import glob, os

def assemble():
    # Load background
    bg = VideoFileClip('assets/minecraft_bg.mp4').resize(height=1920)
    w, h = bg.size
    bg = bg.crop(x1=w//2 - 540, width=1080, height=1920)
    
    # Load ALL audio files IN ORDER
    audio_files = sorted(glob.glob('audio/*.mp3'))
    
    if not audio_files:
        raise Exception("No audio clips found in audio/")
    
    print(f"🎵 Found {len(audio_files)} audio clips")
    
    # Separate voice clips from background music
    voice_clips = [f for f in audio_files if 'background_music' not in f]
    music_clip = [f for f in audio_files if 'background_music' in f]
    
    # Combine voice clips in order
    audio = concatenate_audioclips([AudioFileClip(f) for f in voice_clips])
    
    # Add background music (lower volume)
    if music_clip:
        music = AudioFileClip(music_clip[0]).volumex(0.2)
        if music.duration < audio.duration:
            music = music.loop(duration=audio.duration)
        audio = CompositeAudioClip([audio, music])
    
    final = bg.set_audio(audio)
    
    os.makedirs('output', exist_ok=True)
    final.write_videofile('output/final.mp4', fps=24, codec='libx264')
    print(f"✅ Video assembled: output/final.mp4 ({audio.duration:.1f}s)")

if __name__ == '__main__':
    assemble()