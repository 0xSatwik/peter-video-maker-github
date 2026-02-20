# Implementation Plan: Fix Video Generation Issues (UPDATED)

## Problem Summary

Based on the debug log analysis, the code logic is **correct** but the output video still shows:
1. **Only Peter character** throughout the video (even during Stewie's lines)
2. **Static background** instead of animated video

---

## Debug Log Analysis

### What the Log Shows (ALL CORRECT):
```
Characters available: ['peter', 'stewie']  ✅
[2] stewie   at x= 733 y=1440 t=10.1-13.4  ✅ (Stewie on RIGHT)
[3] stewie   at x= 733 y=1440 t=13.7-14.8  ✅
[7] stewie   at x= 733 y=1440 t=32.5-35.2  ✅
[12] stewie  at x= 733 y=1440 t=49.6-54.2  ✅
Output probe: nb_frames=1636, duration=68.2s  ✅ (Background has frames)
```

### What the Video Shows (INCORRECT):
- Peter character visible during Stewie's lines
- Background appears static (not animating)

---

## Root Cause Analysis (UPDATED)

### Issue 1: Stewie Character Not Visible

**The REAL Problem**: Looking at the debug data:

```
--- STEWIE ---
Raw size: 200x252, channels=4
Alpha: 54.3% opaque, 44.2% transparent
✅ Final: 317x400, shape=(400, 317, 4)
```

Stewie's image is **44.2% transparent** already, meaning it has transparency. But the issue is:

1. **Stewie image is TOO SMALL** (200x252 original vs Peter's 848x1232)
2. **When scaled up 1.58x to 400px height**, the image may become pixelated or have rendering issues
3. **The transparency data may not be rendering correctly** in MoviePy's CompositeVideoClip

**Hypothesis**: The Stewie PNG might have:
- Premultiplied alpha that's not being handled correctly
- Very light/semi-transparent pixels that blend into the background
- Color data that's similar to the background color

### Issue 2: Background Video Static

**The REAL Problem**: The ffmpeg output shows:
```
Output probe: nb_frames=1636, duration=68.2s
```

This is correct - 1636 frames at 24fps = ~68 seconds. BUT:

1. **The background video might have very subtle motion** that looks static
2. **MoviePy might be caching the first frame** due to how CompositeVideoClip works
3. **The video encoding might have issues** with the preset='medium' setting

---

## Implementation Plan (UPDATED)

### Phase 1: Fix Stewie Character Visibility

#### 1.1 Debug Stewie Image Content
Add code to verify Stewie's image actually has visible content:

```python
# After loading Stewie
if name == 'stewie':
    # Check if image has actual color content
    rgb = char_data[:, :, :3]
    alpha = char_data[:, :, 3]
    
    # Count non-transparent pixels with color
    visible_mask = alpha > 128
    visible_rgb = rgb[visible_mask]
    
    print(f"  📊 Stewie visible pixels: {np.sum(visible_mask)}")
    print(f"  📊 Stewie RGB range: R={visible_rgb[:,0].min()}-{visible_rgb[:,0].max()}, "
          f"G={visible_rgb[:,1].min()}-{visible_rgb[:,1].max()}, "
          f"B={visible_rgb[:,2].min()}-{visible_rgb[:,2].max()}")
    
    # Save debug image
    from PIL import Image
    debug_img = Image.fromarray(char_data)
    debug_img.save('output/debug_stewie.png')
    print(f"  📊 Saved debug image: output/debug_stewie.png")
```

#### 1.2 Fix Potential Alpha Compositing Issue
The issue might be with how MoviePy handles RGBA arrays. Try converting to explicit RGB with mask:

```python
def make_char_clip(char_data, start, end, position):
    """Create a character clip with proper alpha handling."""
    
    # Ensure the image is in RGBA format
    if char_data.shape[2] == 4:
        # Create clip from RGBA
        clip = ImageClip(char_data, transparent=True)
    else:
        clip = ImageClip(char_data)
    
    return clip.set_start(start).set_end(end).set_position(position)
```

#### 1.3 Alternative: Pre-render Characters on Solid Background
If alpha compositing is the issue, pre-render characters:

```python
def load_character(name):
    """Load character and pre-render on transparent background."""
    # ... existing loading code ...
    
    # Ensure alpha channel is proper
    if char_data.shape[2] == 4:
        # Make sure alpha is binary (0 or 255) for cleaner compositing
        alpha = char_data[:, :, 3]
        alpha[alpha > 128] = 255
        alpha[alpha <= 128] = 0
        char_data[:, :, 3] = alpha
    
    return char_data
```

### Phase 2: Fix Background Video Animation

#### 2.1 Verify Background is Actually Playing
Add frame extraction to verify:

```python
# After preparing background
print("📊 Extracting first and last frames for verification...")
import subprocess

# Extract first frame
subprocess.run([
    'ffmpeg', '-y', '-i', output_path,
    '-vf', 'select=eq(n\\,0)',
    '-frames:v', '1',
    'output/bg_frame_first.png'
], capture_output=True)

# Extract frame at 50%
subprocess.run([
    'ffmpeg', '-y', '-i', output_path,
    '-vf', f'select=eq(n\\,{1636//2})',
    '-frames:v', '1',
    'output/bg_frame_middle.png'
], capture_output=True)

# Extract last frame
subprocess.run([
    'ffmpeg', '-y', '-i', output_path,
    '-vf', 'select=eq(n\\,1635)',
    '-frames:v', '1',
    'output/bg_frame_last.png'
], capture_output=True)

print("📊 Saved bg_frame_first.png, bg_frame_middle.png, bg_frame_last.png")
```

#### 2.2 Alternative: Use Different Background Loading Method
The issue might be with how MoviePy loads the prepared video:

```python
# Instead of:
bg_video = VideoFileClip(bg_temp)

# Try:
from moviepy.editor import VideoFileClip
bg_video = VideoFileClip(bg_temp, audio=False)
bg_video = bg_video.set_duration(total_duration)

# Verify it's actually a video
print(f"📊 Background: duration={bg_video.duration}, fps={bg_video.fps}, size={bg_video.size}")
print(f"📊 Background has {int(bg_video.duration * bg_video.fps)} frames")
```

### Phase 3: Fix CompositeVideoClip Rendering

#### 3.1 The Real Issue: Layer Order and Timing
Looking at the code more carefully, I see a potential issue:

```python
layers = [bg_video]  # Background first

for timing in clip_timing:
    # ... create character clip ...
    layers.append(char_clip)

final_video = CompositeVideoClip(layers, size=(CANVAS_W, CANVAS_H))
```

**The Problem**: Each character clip is only visible during its specific time range. When Stewie's clip ends, there's NO character visible until Peter's next clip starts.

**But wait** - the debug shows consecutive clips with gaps:
```
[1] peter    at x=  30 y=1440 t=6.1-9.8
[2] stewie   at x= 733 y=1440 t=10.1-13.4  # Gap from 9.8 to 10.1
```

The gaps are only 0.3s (GAP_SECONDS), which is correct.

#### 3.2 Potential MoviePy Bug with ImageClip
MoviePy's ImageClip might have issues with the `set_start()` and `set_end()` methods when used in CompositeVideoClip.

**Solution**: Use `set_duration()` and `set_start()` instead:

```python
char_clip = (
    ImageClip(char_data)
    .set_duration(timing['end'] - timing['start'])
    .set_start(timing['start'])
    .set_position((cx, char_y))
)
```

#### 3.3 Alternative: Pre-compose Character Clips Differently
Try a different approach - create separate videos for each character and overlay:

```python
# Create a single clip for each character that spans the entire video
# with visibility only during their lines

def create_character_track(char_name, char_data, clip_timing, total_duration, position_x, char_y):
    """Create a single clip for a character with visibility changes."""
    
    # Create a base transparent frame
    from moviepy.editor import ImageClip, CompositeVideoClip
    
    # Build segments for this character
    segments = []
    for timing in clip_timing:
        if timing['speaker'] == char_name:
            clip = (
                ImageClip(char_data)
                .set_start(timing['start'])
                .set_duration(timing['end'] - timing['start'])
                .set_position((position_x, char_y))
            )
            segments.append(clip)
    
    return segments
```

### Phase 4: Nuclear Option - Complete Rewrite of Assembly Logic

If the above doesn't work, the issue might be fundamental to how MoviePy handles the composition. Here's a completely different approach:

```python
def assemble_v2():
    """Alternative assembly using frame-by-frame approach."""
    import subprocess
    import os
    from PIL import Image
    import numpy as np
    
    # ... load all data ...
    
    # Create frame directory
    os.makedirs('output/frames', exist_ok=True)
    
    # Extract background frames
    subprocess.run([
        'ffmpeg', '-y', '-i', 'output/bg_prepared.mp4',
        '-vf', f'fps={FPS}',
        'output/frames/bg_%04d.png'
    ])
    
    # For each frame, composite the characters
    for frame_num in range(int(total_duration * FPS)):
        time = frame_num / FPS
        
        # Load background frame
        bg = Image.open(f'output/frames/bg_{frame_num+1:04d}.png').convert('RGBA')
        
        # Find which character should be visible
        for timing in clip_timing:
            if timing['start'] <= time < timing['end']:
                speaker = timing['speaker']
                char_data = characters[speaker]
                char_img = Image.fromarray(char_data)
                
                # Calculate position
                if speaker == 'peter':
                    x = 30
                else:
                    x = CANVAS_W - char_data.shape[1] - 30
                y = char_y
                
                # Paste character
                bg.paste(char_img, (x, y), char_img)
        
        # Save composited frame
        bg.save(f'output/frames/frame_{frame_num:04d}.png')
    
    # Encode final video
    subprocess.run([
        'ffmpeg', '-y',
        '-framerate', str(FPS),
        '-i', 'output/frames/frame_%04d.png',
        '-i', 'audio_combined.wav',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        'output/final_reel.mp4'
    ])
```

---

## Recommended Fix Order

1. **First**: Add debug output for Stewie's image RGB content to verify it has visible pixels
2. **Second**: Try the `set_duration()` instead of `set_end()` fix
3. **Third**: Verify background frames are actually different
4. **Fourth**: If all else fails, use the frame-by-frame approach

---

## Updated Debug Steps for GitHub Workflow

```yaml
- name: Debug - Verify Stewie image content
  run: |
    python -c "
    from PIL import Image
    import numpy as np
    
    img = Image.open('assets/stewie.png').convert('RGBA')
    data = np.array(img)
    
    print(f'Stewie size: {img.size}')
    print(f'Mode: {img.mode}')
    
    rgb = data[:,:,:3]
    alpha = data[:,:,3]
    
    visible = alpha > 128
    print(f'Visible pixels: {np.sum(visible)} / {alpha.size}')
    
    if np.sum(visible) > 0:
        visible_rgb = rgb[visible]
        print(f'RGB range in visible area:')
        print(f'  R: {visible_rgb[:,0].min()}-{visible_rgb[:,0].max()}')
        print(f'  G: {visible_rgb[:,1].min()}-{visible_rgb[:,1].max()}')
        print(f'  B: {visible_rgb[:,2].min()}-{visible_rgb[:,2].max()}')
    "

- name: Debug - Extract background frames
  run: |
    mkdir -p output/bg_debug
    ffmpeg -y -i output/bg_prepared.mp4 -vf "select=eq(n\,0)" -frames:v 1 output/bg_debug/frame_0001.png
    ffmpeg -y -i output/bg_prepared.mp4 -vf "select=eq(n\,500)" -frames:v 1 output/bg_debug/frame_0500.png
    ffmpeg -y -i output/bg_prepared.mp4 -vf "select=eq(n\,1000)" -frames:v 1 output/bg_debug/frame_1000.png
    echo "Background frames extracted to output/bg_debug/"

- name: Debug - Create Stewie debug image
  run: |
    python -c "
    from PIL import Image
    import numpy as np
    
    # Load Stewie
    img = Image.open('assets/stewie.png').convert('RGBA')
    
    # Scale to 400px height
    scale = 400 / img.height
    new_w = int(img.width * scale)
    img = img.resize((new_w, 400), Image.LANCZOS)
    
    # Save for inspection
    img.save('output/debug_stewie_scaled.png')
    
    # Also create on black background for visibility check
    bg = Image.new('RGBA', (new_w + 20, 420), (0, 0, 0, 255))
    bg.paste(img, (10, 10), img)
    bg.save('output/debug_stewie_on_black.png')
    
    print('Saved debug images: debug_stewie_scaled.png, debug_stewie_on_black.png')
    "
```

---

## Summary

The debug log shows the code logic is correct, so the issue must be in:
1. **How MoviePy renders the Stewie image** (possibly alpha/transparency issue)
2. **How MoviePy composites the background video** (possibly caching issue)

The fix requires:
1. Verifying Stewie's image has actual visible RGB content
2. Trying alternative clip creation methods
3. Potentially switching to a frame-by-frame rendering approach if MoviePy's CompositeVideoClip has bugs
