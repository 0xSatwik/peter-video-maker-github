from moviepy.editor import *
import whisper, os

def add_captions():
    video = VideoFileClip('output/final.mp4')
    model = whisper.load_model("tiny")
    result = model.transcribe('output/final.mp4')
    
    caption_clips = []
    for seg in result['segments']:
        txt = TextClip(
            seg['text'].strip(),
            fontsize=52, color='white', stroke_color='black',
            stroke_width=3, font='Arial-Bold', method='caption',
            size=(900, None)
        )
        txt = txt.set_position(('center', 1450))
        txt = txt.set_start(seg['start']).set_end(seg['end'])
        txt = txt.fadein(0.3).fadeout(0.3)
        caption_clips.append(txt)
    
    final = CompositeVideoClip([video] + caption_clips)
    final.write_videofile('output/final_reel.mp4', fps=24, codec='libx264')
    print("✅ Final video: output/final_reel.mp4")

if __name__ == '__main__':
    add_captions()