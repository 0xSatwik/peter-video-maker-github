# Implementation Plan: Fix Audio/Video Sync & Quality Issues

## Problem Summary

Based on user feedback, the following issues remain:

1. **Extra sounds in audio** - TTS adding laughing/useless sounds not in script
2. **Old background sound bleeding through** - Background video audio mixing with speech
3. **Background video sizing** - Should loop if shorter, stop if longer (no forced resize)
4. **Inconsistent speaking speed** - Speed varies between clips
5. **Pronunciation issues** - "Which is it" spoken as "w hich is it" (broken up)

---

## Root Cause Analysis

### Issue 1: Extra Sounds (Laughing, etc.) in TTS Audio

**Location**: [`scripts/generate_audio.py`](scripts/generate_audio.py:17-28)

```python
HIGH_QUALITY = {
    "max_new_tokens": 2500,
    "speed": 1.0,
    "text_temp": 1.5,        # TOO HIGH - causes random outputs
    "audio_temp": 0.95,      # High - adds variation
    "audio_repetition_penalty": 1.1,
    "n_vq": 24,
}
```

**Root Cause**: 
- `text_temp: 1.5` is too high, causing the model to generate random tokens (laughing, extra sounds)
- High temperature values introduce randomness in generation
- MOSS-TTS may interpret silence or punctuation as opportunities to add sounds

**Solution**: Lower the temperature values and add text preprocessing

### Issue 2: Background Video Audio Bleeding

**Location**: [`scripts/assemble_video.py`](scripts/assemble_video.py:117-125)

```python
subprocess.run([
    'ffmpeg', '-y', 
    '-stream_loop', '-1', 
    '-i', 'assets/minecraft_bg.mp4',  # Has audio!
    '-t', str(total_duration),
    '-vf', f'scale=...',  # Only video filter
    f'{frames_dir}/bg_%05d.jpg'  # Extracts frames only
], check=True, capture_output=True)
```

**Root Cause**: 
- The background video `minecraft_bg.mp4` has its own audio track
- While we extract only frames, the audio might be bleeding through somewhere
- Need to explicitly disable audio from background

**Solution**: Add `-an` flag to disable audio from background video

### Issue 3: Background Video Sizing

**Location**: [`scripts/assemble_video.py`](scripts/assemble_video.py:121-122)

```python
'-vf', f'scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,crop={CANVAS_W}:{CANVAS_H},fps={FPS}'
```

**Root Cause**: 
- Forces background to exact canvas size with crop
- User wants: keep original aspect, just scale to fit height

**Solution**: Change to fit within canvas without cropping

### Issue 4: Inconsistent Speaking Speed

**Location**: [`scripts/generate_audio.py`](scripts/generate_audio.py:19)

```python
"speed": 1.0,  # Same for all, but TTS model varies
```

**Root Cause**: 
- MOSS-TTS generates different speeds based on text content
- Short phrases like "Genius." generate faster than long sentences
- The model doesn't maintain consistent speaking rate

**Solution**: 
- Post-process audio to normalize speed/duration
- OR use speed parameter more aggressively
- OR use audio stretching to match expected duration

### Issue 5: Pronunciation Issues ("w hich is it")

**Root Cause**: 
- MOSS-TTS tokenization issue with short phrases
- The comma before "Which" might cause weird break
- Model is breaking up the word

**Solution**: 
- Preprocess text to remove problematic patterns
- Add explicit pronunciation hints
- Merge short phrases with previous/next to give more context

---

## Implementation Plan

### Phase 1: Fix TTS Generation Parameters

#### 1.1 Lower Temperature Values
**File**: [`scripts/generate_audio.py`](scripts/generate_audio.py:17-28)

```python
# Change from:
HIGH_QUALITY = {
    "max_new_tokens": 2500,
    "speed": 1.0,
    "text_temp": 1.5,      # Too high
    "text_top_p": 1.0,
    "text_top_k": 50,
    "audio_temp": 0.95,    # Too high
    "audio_top_p": 0.95,
    "audio_top_k": 50,
    "audio_repetition_penalty": 1.1,
    "n_vq": 24,
}

# To:
CONSISTENT_QUALITY = {
    "max_new_tokens": 2500,
    "speed": 1.0,
    "text_temp": 0.8,      # Lower = more deterministic
    "text_top_p": 0.95,    # Lower = less random
    "text_top_k": 40,      # Lower = less random
    "audio_temp": 0.8,     # Lower = more consistent
    "audio_top_p": 0.9,    # Lower = less random
    "audio_top_k": 40,     # Lower = less random
    "audio_repetition_penalty": 1.2,  # Higher = prevent repetition
    "n_vq": 24,
}
```

#### 1.2 Add Text Preprocessing
**File**: [`scripts/generate_audio.py`](scripts/generate_audio.py:98-113)

```python
def preprocess_text(text):
    """Clean text for TTS to prevent pronunciation issues."""
    import re
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Add space after punctuation if missing
    text = re.sub(r'([.,!?])([A-Za-z])', r'\1 \2', text)
    
    # For very short phrases, add context
    # (MOSS-TTS works better with more context)
    if len(text.split()) <= 3:
        text = f"... {text} ..."  # Add ellipsis for context
    
    return text.strip()

def parse_script(script_path):
    """Parse script file: SPEAKER|TAGS|LYRICS"""
    lines = []
    with open(script_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('|')
            if len(parts) == 3:
                speaker, tags, lyrics = parts
                # Preprocess text for better TTS
                lyrics = preprocess_text(lyrics)
                lines.append({
                    'speaker': speaker.strip().lower(),
                    'text': lyrics
                })
    return lines
```

### Phase 2: Fix Background Video Handling

#### 2.1 Disable Audio from Background Video
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:117-125)

```python
# Change from:
subprocess.run([
    'ffmpeg', '-y', 
    '-stream_loop', '-1', 
    '-i', 'assets/minecraft_bg.mp4',
    '-t', str(total_duration),
    '-vf', f'scale=...',
    f'{frames_dir}/bg_%05d.jpg'
], check=True, capture_output=True)

# To:
subprocess.run([
    'ffmpeg', '-y', 
    '-stream_loop', '-1', 
    '-i', 'assets/minecraft_bg.mp4',
    '-t', str(total_duration),
    '-an',  # EXPLICITLY DISABLE AUDIO from background
    '-vf', f'scale=...',
    f'{frames_dir}/bg_%05d.jpg'
], check=True, capture_output=True)
```

#### 2.2 Fix Background Sizing (No Crop, Just Fit)
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:121-122)

```python
# Change from:
'-vf', f'scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,crop={CANVAS_W}:{CANVAS_H},fps={FPS}'

# To (fit height, center horizontally):
'-vf', f'scale=-1:{CANVAS_H},pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:0:black,fps={FPS}'

# This will:
# 1. Scale to height 1920, keeping aspect ratio
# 2. Pad with black bars if needed to reach 1080 width
# 3. No cropping - entire background video is visible
```

### Phase 3: Fix Audio Timing & Sync

#### 3.1 Remove GAP_SECONDS from Timing Calculation
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:86)

The current code adds `GAP_SECONDS` between clips, but the audio filter approach doesn't need this:

```python
# Change from:
current_time += duration + GAP_SECONDS

# To:
current_time += duration  # No artificial gap - let audio flow naturally
```

#### 3.2 Use Simpler Audio Concatenation
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:167-201)

The current `adelay` + `amix` approach is complex and can cause issues. Use simple concat:

```python
# --- Assemble Audio ---
log("\n🎵 ASSEMBLING AUDIO...")

# Create concat list (no gaps needed)
with open('output/audio_concat.txt', 'w') as f:
    for audio_path in audio_files_to_concat:
        f.write(f"file '../{audio_path}'\n")

# Simple concat - no gaps, no complex filters
subprocess.run([
    'ffmpeg', '-y',
    '-f', 'concat', '-safe', '0',
    '-i', 'output/audio_concat.txt',
    '-c:a', 'pcm_s16le',
    'output/combined_audio.wav'
], check=True, capture_output=True)

# Get actual audio duration
probe = subprocess.run(
    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', 'output/combined_audio.wav'],
    capture_output=True, text=True
)
actual_audio_duration = float(json.loads(probe.stdout)['format']['duration'])

# Use audio duration for video
total_duration = actual_audio_duration
total_frames = int(total_duration * FPS) + 1
```

### Phase 4: Normalize Audio Speed/Duration

#### 4.1 Add Audio Normalization Step
**File**: [`scripts/generate_audio.py`](scripts/generate_audio.py) - Add after generation

```python
def normalize_audio_speed(input_path, target_duration=None):
    """
    Normalize audio to consistent speed.
    If target_duration is provided, stretch/shrink to match.
    """
    import subprocess
    import json
    
    # Get current duration
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', input_path],
        capture_output=True, text=True
    )
    current_duration = float(json.loads(probe.stdout)['format']['duration'])
    
    if target_duration is None:
        # Just normalize volume and remove silence
        output_path = input_path.replace('.wav', '_normalized.wav')
        subprocess.run([
            'ffmpeg', '-y', '-i', input_path,
            '-af', 'silenceremove=stop_periods=1:stop_duration=0.3:stop_threshold=-40dB,loudnorm=I=-14:TP=-1.5:LRA=11',
            output_path
        ], check=True, capture_output=True)
        return output_path
    
    # Stretch/shrink to target duration
    tempo = current_duration / target_duration
    output_path = input_path.replace('.wav', '_normalized.wav')
    
    # atempo filter limits: 0.5 to 2.0, chain if needed
    if tempo > 2.0:
        tempo = 2.0
    elif tempo < 0.5:
        tempo = 0.5
    
    subprocess.run([
        'ffmpeg', '-y', '-i', input_path,
        '-af', f'atempo={tempo},loudnorm=I=-14:TP=-1.5:LRA=11',
        output_path
    ], check=True, capture_output=True)
    
    return output_path
```

### Phase 5: Fix Caption Timing

#### 5.1 Render Captions on Frames (Eliminate MoviePy Timing Drift)
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:138-163)

Add caption rendering to the frame compositing loop:

```python
from PIL import Image, ImageDraw, ImageFont

# Load font for captions
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
except:
    font = ImageFont.load_default()

# In the frame loop:
for f_idx in range(total_frames):
    bg_path = f"{frames_dir}/bg_{f_idx+1:05d}.jpg"
    if not os.path.exists(bg_path):
        break
    
    current_time = f_idx / FPS
    speaker = frame_speakers[f_idx]
    
    # Load frame
    bg_img = Image.open(bg_path).convert("RGBA")
    
    # Composite character
    if speaker and speaker in characters:
        char_img = characters[speaker]
        if speaker == 'peter':
            cx = 30
        else:
            cx = CANVAS_W - char_img.width - 30
        bg_img.paste(char_img, (cx, char_y), char_img)
    
    # Render caption
    for timing in clip_timing:
        if timing['start'] <= current_time < timing['end']:
            text = timing['text']
            words = text.split()
            chunk_size = 7
            chunks = [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
            
            if chunks:
                duration = timing['end'] - timing['start']
                chunk_duration = duration / len(chunks)
                time_in_clip = current_time - timing['start']
                chunk_idx = min(int(time_in_clip / chunk_duration), len(chunks) - 1)
                chunk = chunks[chunk_idx]
                
                # Draw caption
                draw = ImageDraw.Draw(bg_img)
                bbox = draw.textbbox((0, 0), chunk, font=font)
                text_width = bbox[2] - bbox[0]
                text_x = (CANVAS_W - text_width) // 2
                text_y = 1050
                
                # Draw stroke
                for ox in range(-3, 4):
                    for oy in range(-3, 4):
                        if ox != 0 or oy != 0:
                            draw.text((text_x + ox, text_y + oy), chunk, font=font, fill='black')
                # Draw text
                draw.text((text_x, text_y), chunk, font=font, fill='yellow')
            break
    
    # Save frame
    bg_img.convert("RGB").save(bg_path, quality=95)
```

---

## Summary of Changes

| File | Change | Priority |
|------|--------|----------|
| `generate_audio.py` | Lower temperature values (text_temp: 1.5→0.8, audio_temp: 0.95→0.8) | Critical |
| `generate_audio.py` | Add text preprocessing function | High |
| `assemble_video.py` | Add `-an` flag to disable background audio | Critical |
| `assemble_video.py` | Change background scaling to fit without crop | Medium |
| `assemble_video.py` | Remove GAP_SECONDS from timing | High |
| `assemble_video.py` | Simplify audio concatenation | High |
| `assemble_video.py` | Add caption rendering to frame loop | High |
| `add_captions.py` | Can be removed (captions now in assemble) | Optional |

---

## Testing Checklist

After implementing fixes, verify:

- [ ] No extra sounds (laughing, etc.) in generated audio
- [ ] No background audio bleeding through
- [ ] Background video loops properly if shorter than speech
- [ ] Background video stops when speech ends
- [ ] Speaking speed is consistent across all clips
- [ ] No pronunciation issues (words not broken up)
- [ ] Captions sync perfectly with audio
- [ ] Character appears at correct times
