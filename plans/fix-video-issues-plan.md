# Implementation Plan: Fix Background Quality & Caption Styling

## Problem Summary

Two remaining issues:
1. **Background video quality is very poor** - Pixelated, blurry
2. **Caption look is very bad** - Basic font, not attractive

---

## Root Cause Analysis

### Issue 1: Poor Background Video Quality

**Location**: [`scripts/assemble_video.py`](scripts/assemble_video.py:115-124)

```python
subprocess.run([
    'ffmpeg', '-y',
    '-stream_loop', '-1', 
    '-i', 'assets/minecraft_bg.mp4',
    '-t', str(total_duration),
    '-vf', f'scale=-1:{CANVAS_H},pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:0:black,fps={FPS}',
    '-an',
    '-qscale:v', '2',
    f'{frames_dir}/bg_%05d.jpg'  # ❌ JPG is lossy!
], check=True, capture_output=True)
```

**Root Causes**:
1. **JPG format is lossy** - Each frame is compressed with lossy JPEG
2. **Double compression** - Frames extracted as JPG, then re-encoded to video
3. **CRF 23 is too high** - Final encoding uses medium quality
4. **Source video upscaling** - Background is 202x360, being scaled to 1080x1920 (5x upscale!)

**Solution**: Use PNG for intermediate frames and improve encoding settings

### Issue 2: Poor Caption Styling

**Location**: [`scripts/add_captions.py`](scripts/add_captions.py:79-91)

```python
kwargs = {
    'fontsize': 46,
    'color': 'yellow',           # ❌ Basic yellow
    'stroke_color': 'black',     # ❌ Basic black stroke
    'stroke_width': 2.5,
    'method': 'caption',
    'size': (900, None),
    'align': 'center',
}
```

**Root Causes**:
1. **Basic font** - DejaVu-Sans-Bold is not attractive for social media
2. **Basic colors** - Plain yellow with black stroke
3. **No effects** - No glow, shadow, or gradient effects
4. **Small font size** - 46px is too small for mobile viewing

**Solution**: Use attractive fonts with better styling (glow, shadows, gradients)

---

## Implementation Plan

### Phase 1: Fix Background Video Quality

#### 1.1 Use PNG Instead of JPG for Intermediate Frames
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:115-124)

```python
# Change from:
subprocess.run([
    'ffmpeg', '-y',
    '-stream_loop', '-1', 
    '-i', 'assets/minecraft_bg.mp4',
    '-t', str(total_duration),
    '-vf', f'scale=-1:{CANVAS_H},pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:0:black,fps={FPS}',
    '-an',
    '-qscale:v', '2',
    f'{frames_dir}/bg_%05d.jpg'  # JPG = lossy
], check=True, capture_output=True)

# To:
subprocess.run([
    'ffmpeg', '-y',
    '-stream_loop', '-1', 
    '-i', 'assets/minecraft_bg.mp4',
    '-t', str(total_duration),
    '-vf', f'scale=-1:{CANVAS_H}:flags=lanczos,pad={CANVAS_W}:{CANVAS_H}:(ow-iw)/2:0:black,fps={FPS}',
    '-an',
    '-vsync', '0',
    f'{frames_dir}/bg_%05d.png'  # PNG = lossless
], check=True, capture_output=True)
```

**Key Changes**:
- Use `.png` instead of `.jpg` for lossless intermediate frames
- Add `:flags=lanczos` for high-quality scaling
- Remove `-qscale:v` (not needed for PNG)
- Add `-vsync 0` to prevent frame dropping

#### 1.2 Update Frame Loading to Use PNG
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:139, 146, 158)

```python
# Change all references from .jpg to .png
bg_path = f"{frames_dir}/bg_{f_idx+1:05d}.png"  # Line 139

# When saving, still save as PNG
bg_img.convert("RGB").save(bg_path, quality=95)  # Keep high quality
```

#### 1.3 Improve Final Video Encoding Quality
**File**: [`scripts/assemble_video.py`](scripts/assemble_video.py:206-216)

```python
# Change from:
encode_cmd = [
    'ffmpeg', '-y',
    '-framerate', str(FPS),
    '-i', f'{frames_dir}/bg_%05d.jpg',
    '-i', 'output/combined_audio.wav',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',  # ❌ CRF 23
    '-c:a', 'aac', '-b:a', '192k',
    '-pix_fmt', 'yuv420p',
    '-shortest',
    output_path
]

# To:
encode_cmd = [
    'ffmpeg', '-y',
    '-framerate', str(FPS),
    '-i', f'{frames_dir}/bg_%05d.png',  # PNG input
    '-i', 'output/combined_audio.wav',
    '-c:v', 'libx264', 
    '-preset', 'slow',      # Better compression
    '-crf', '18',           # Lower = higher quality (18 is visually lossless)
    '-c:a', 'aac', '-b:a', '192k',
    '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',  # Better streaming
    '-shortest',
    output_path
]
```

**Key Changes**:
- CRF 18 instead of 23 (visually lossless quality)
- Preset `slow` for better compression efficiency
- Add `-movflags +faststart` for better streaming

### Phase 2: Improve Caption Styling

#### 2.1 Install Better Fonts in GitHub Workflow
**File**: [`.github/workflows/generate.yml`](.github/workflows/generate.yml:29-35)

```yaml
- name: Install system dependencies
  env:
    DEBIAN_FRONTEND: noninteractive
    TZ: UTC
  run: |
    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
      ffmpeg \
      imagemagick \
      fonts-dejavu-core \
      fonts-noto \
      fonts-noto-cjk \
      fonts-roboto \
      fonts-open-sans \
      fonts-montserrat
```

#### 2.2 Update Caption Styling
**File**: [`scripts/add_captions.py`](scripts/add_captions.py:9-17)

```python
# Better font candidates for social media
FONT_CANDIDATES = [
    'Montserrat-ExtraBold',     # Modern, bold, attractive
    'Montserrat-Bold',
    'Roboto-Bold',              # Clean, modern
    'OpenSans-Bold',            # Friendly, readable
    'NotoSans-Bold',            # Universal, clean
    'DejaVu-Sans-Bold',         # Fallback
    'Arial-Bold',               # Fallback
]
```

#### 2.3 Improve Caption Appearance
**File**: [`scripts/add_captions.py`](scripts/add_captions.py:79-91)

```python
# Change from:
kwargs = {
    'fontsize': 46,
    'color': 'yellow',
    'stroke_color': 'black',
    'stroke_width': 2.5,
    'method': 'caption',
    'size': (900, None),
    'align': 'center',
}

# To:
kwargs = {
    'fontsize': 58,                    # Larger for mobile
    'color': '#FFD700',                # Gold yellow (more vibrant)
    'stroke_color': '#000000',         # Black stroke
    'stroke_width': 3,                 # Thicker stroke
    'method': 'caption',
    'size': (950, None),               # Slightly wider
    'align': 'center',
    'bg_color': 'transparent',
}
```

#### 2.4 Add Glow Effect (Alternative Approach)
Since MoviePy doesn't support glow directly, we can simulate it with multiple text layers:

```python
def create_glowing_caption(text, font, fontsize=58):
    """Create a caption with glow effect using multiple layers."""
    
    # Glow layer (larger, semi-transparent)
    glow_kwargs = {
        'fontsize': fontsize + 4,
        'color': '#FFD700',           # Gold
        'stroke_color': '#FFD700',    # Same color for glow
        'stroke_width': 8,            # Wide stroke for glow
        'method': 'caption',
        'size': (950, None),
        'align': 'center',
        'font': font,
    }
    
    # Main text layer
    main_kwargs = {
        'fontsize': fontsize,
        'color': '#FFFFFF',           # White text
        'stroke_color': '#000000',    # Black outline
        'stroke_width': 3,
        'method': 'caption',
        'size': (950, None),
        'align': 'center',
        'font': font,
    }
    
    glow_clip = TextClip(text, **glow_kwargs).set_opacity(0.3)
    main_clip = TextClip(text, **main_kwargs)
    
    return glow_clip, main_clip
```

#### 2.5 Alternative: Render Captions with PIL (Better Control)
**File**: [`scripts/add_captions.py`](scripts/add_captions.py) - Complete rewrite

```python
"""
Add attractive captions using PIL for better styling.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import json
import os
import subprocess
from moviepy.editor import VideoFileClip

def create_caption_image(text, font_path, width=950, font_size=58):
    """Create a caption image with glow effect."""
    
    # Load font
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
    
    # Create temporary image to measure text
    temp = Image.new('RGBA', (width, 200), (0, 0, 0, 0))
    draw = ImageDraw.Draw(temp)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Create final image with padding
    padding = 20
    img = Image.new('RGBA', (width, text_height + padding * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Position text centered
    x = (width - text_width) // 2
    y = padding
    
    # Draw glow (multiple passes with blur)
    for offset in range(3, 0, -1):
        glow_color = (255, 215, 0, 50)  # Gold, semi-transparent
        for ox in range(-offset, offset + 1):
            for oy in range(-offset, offset + 1):
                draw.text((x + ox, y + oy), text, font=font, fill=glow_color)
    
    # Draw stroke (outline)
    stroke_color = (0, 0, 0, 255)  # Black
    for ox in range(-3, 4):
        for oy in range(-3, 4):
            if ox != 0 or oy != 0:
                draw.text((x + ox, y + oy), text, font=font, fill=stroke_color)
    
    # Draw main text
    text_color = (255, 255, 255, 255)  # White
    draw.text((x, y), text, font=font, fill=text_color)
    
    return img

def find_font():
    """Find the best available font."""
    font_paths = [
        '/usr/share/fonts/truetype/montserrat/Montserrat-ExtraBold.ttf',
        '/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf',
        '/usr/share/fonts/truetype/open-sans/OpenSans-Bold.ttf',
        '/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]
    for path in font_paths:
        if os.path.exists(path):
            return path
    return None

def add_captions():
    print("📝 Adding attractive captions...")
    
    # Find font
    font_path = find_font()
    if font_path:
        print(f"🔤 Using font: {font_path}")
    else:
        print("⚠️ No custom font found, using default")
    
    # Load timing
    with open('output/timing.json', 'r') as f:
        timing = json.load(f)
    
    print(f"📄 Loaded {len(timing)} caption entries")
    
    # Create caption images directory
    os.makedirs('output/captions', exist_ok=True)
    
    # Generate caption clips
    from moviepy.editor import ImageClip, CompositeVideoClip
    
    video = VideoFileClip('output/final_reel.mp4')
    caption_clips = []
    caption_y = 1050
    
    for entry in timing:
        text = entry['text']
        start = entry['start']
        end = entry['end']
        duration = end - start
        
        # Split into chunks
        words = text.split()
        chunk_size = 7
        chunks = [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        
        if not chunks:
            continue
        
        chunk_duration = duration / len(chunks)
        
        for ci, chunk in enumerate(chunks):
            chunk_start = start + (ci * chunk_duration)
            chunk_end = chunk_start + chunk_duration
            
            # Create caption image
            caption_img = create_caption_image(chunk, font_path)
            caption_path = f'output/captions/caption_{entry["index"]}_{ci}.png'
            caption_img.save(caption_path)
            
            # Create clip
            clip = (ImageClip(str(caption_img))
                   .set_start(chunk_start)
                   .set_end(chunk_end)
                   .set_position(('center', caption_y)))
            
            caption_clips.append(clip)
    
    print(f"✨ Created {len(caption_clips)} caption segments")
    
    # Composite
    temp_output = 'output/final_reel_captioned.mp4'
    final = CompositeVideoClip([video] + caption_clips)
    final.write_videofile(
        temp_output,
        fps=24,
        codec='libx264',
        audio_codec='copy',  # Copy audio without re-encoding
        preset='slow',
        crf=18
    )
    
    video.close()
    final.close()
    
    # Replace
    import shutil
    shutil.move(temp_output, 'output/final_reel.mp4')
    
    print("✅ Final video with captions: output/final_reel.mp4")

if __name__ == '__main__':
    add_captions()
```

---

## Summary of Changes

| File | Change | Priority |
|------|--------|----------|
| `assemble_video.py` | Use PNG instead of JPG for frames | Critical |
| `assemble_video.py` | Add `:flags=lanczos` for quality scaling | High |
| `assemble_video.py` | Change CRF from 23 to 18 | High |
| `assemble_video.py` | Change preset from medium to slow | Medium |
| `.github/workflows/generate.yml` | Install better fonts (Montserrat, Roboto) | High |
| `add_captions.py` | Use better fonts | High |
| `add_captions.py` | Increase font size to 58 | Medium |
| `add_captions.py` | Add glow effect | Medium |
| `add_captions.py` | Use PIL for better caption rendering | Optional |

---

## Quality Comparison

| Setting | Before | After |
|---------|--------|-------|
| Frame format | JPG (lossy) | PNG (lossless) |
| Scaling filter | default | lanczos |
| CRF | 23 | 18 |
| Preset | medium | slow |
| Font | DejaVu-Sans-Bold | Montserrat-ExtraBold |
| Font size | 46px | 58px |
| Caption color | yellow | gold with glow |
