"""FAST video assembly — same output as assemble_video.py, one ffmpeg pass.

Why this exists
---------------
assemble_video.py writes ~1,570 full-HD PNG frames, re-opens each one in PIL to
paste a character + draw caption text, saves it again, then has ffmpeg read all
of them back (~6 GB of I/O, single-threaded) => 25-28 minutes per video.

This engine renders only the UNIQUE images (2 characters + one PNG per caption
state), builds the caption layer as a small image sequence, and lets a single
ffmpeg filtergraph do every composite + the encode in one pass.

Visual output is identical: same constants, same font, same word-level green
highlight, same character positions, same caption y, same 24fps / 1080x1920.

Safety: the workflow runs this first and falls back to assemble_video.py if this
exits non-zero, and ASSEMBLE_ENGINE=python forces the old engine.
"""
import json
import os
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont

# === CONSTANTS (kept identical to assemble_video.py) ===
CANVAS_W, CANVAS_H = 1080, 1920
CHAR_HEIGHT_BASE = 750
CHAR_SCALES = {'peter': 1.10, 'stewie': 0.95}
GAP_SECONDS = 0.3
FPS = 24
CAPTION_Y = 930
CAPTION_FONT_SIZE = 68
CAPTION_PADDING = 50
CHUNK_SIZE = 4
LINE_SPACING = 12
STROKE_WIDTH = 4

FFMPEG = os.environ.get("FFMPEG_BIN", "ffmpeg")


def log(msg):
    print(msg, flush=True)


def find_font():
    candidates = [
        '/usr/share/fonts/truetype/montserrat/Montserrat-Black.ttf',
        '/usr/share/fonts/truetype/montserrat/Montserrat-ExtraBold.ttf',
        '/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf',
        '/usr/share/fonts/truetype/roboto/hinted/Roboto-Black.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            log(f"   Using font: {path}")
            return ImageFont.truetype(path, CAPTION_FONT_SIZE)
    log("   no custom font found, using default")
    return ImageFont.load_default()


def load_character(name):
    """Cut-out + border + shadow art (see scripts/char_art.py), saved as RGBA PNG.

    Replaces the old near-black-only keying which left a blue anti-aliased halo
    (the "background showing through" you saw around Peter/Stewie).
    """
    import char_art
    got = char_art.load_character(name)
    if not got:
        return None
    img, w, h = got
    path = f'output/char_{name}.png'
    img.save(path)
    return {"path": path, "w": w, "h": h}


def caption_block(text, active_word_idx, font):
    """Render one caption state at FULL canvas size, overlaying exactly where
    the old engine drew it (draw.text at y=CAPTION_Y), so the caption position
    is pixel-identical to the old engine. Returns (image, top_y=0).
    """
    probe = ImageDraw.Draw(Image.new("RGBA", (CANVAS_W, CANVAS_H)))
    words = text.upper().split()
    if not words:
        return None

    max_width = CANVAS_W - (CAPTION_PADDING * 2)
    space_width = probe.textlength(" ", font=font)
    bbox = font.getbbox("A")
    line_height = bbox[3] - bbox[1] + LINE_SPACING

    lines = []
    current_line = []
    current_width = 0
    for i, word in enumerate(words):
        word_w = probe.textlength(word, font=font)
        needed = word_w + (space_width if current_line else 0)
        if current_line and current_width + needed > max_width:
            lines.append(current_line)
            current_line = [(word, i)]
            current_width = word_w
        else:
            current_line.append((word, i))
            current_width += needed
    if current_line:
        lines.append(current_line)

    # Old engine drew: draw.text((x, CAPTION_Y + line_idx*line_height), ...).
    # Render into a SMALL strip covering exactly that area (fast PNG decode),
    # and report the y where the strip must be overlaid so the text lands on
    # the exact same pixels as before.
    margin = STROKE_WIDTH + 8
    top = int(max(0, CAPTION_Y - margin))
    block_h = int(len(lines) * line_height + margin * 2)
    block = Image.new("RGBA", (CANVAS_W, max(1, block_h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(block)

    for line_idx, line_words in enumerate(lines):
        word_widths = [draw.textlength(w, font=font) for w, _ in line_words]
        line_width = sum(word_widths) + space_width * (len(line_words) - 1)
        x = (CANVAS_W - line_width) / 2
        line_y = CAPTION_Y + line_idx * line_height - top
        for j, (word, orig_idx) in enumerate(line_words):
            fill = '#00FF00' if orig_idx == active_word_idx else '#FFFFFF'
            draw.text((x, line_y), word, font=font, fill=fill,
                      stroke_fill='#000000', stroke_width=STROKE_WIDTH)
            x += word_widths[j] + space_width

    return block, top


def probe_duration(path, ffprobe):
    """Duration via ffprobe JSON; falls back to `ffmpeg -i` (or ffmpeg.exe renamed)."""
    import re
    if os.path.basename(ffprobe).lower() == "ffprobe.exe":
        out = subprocess.run([ffprobe, '-hide_banner', '-i', path],
                             capture_output=True, text=True, errors='replace').stderr
    else:
        try:
            probe = subprocess.run(
                [ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', path],
                capture_output=True, text=True,
            )
            return float(json.loads(probe.stdout)['format']['duration'])
        except Exception:
            out = subprocess.run([FFMPEG, '-hide_banner', '-i', path],
                                 capture_output=True, text=True, errors='replace').stderr
    for line in out.splitlines():
        m = re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', line)
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    raise RuntimeError(f"could not determine duration of {path}")


def build_timing():
    """Same timing math as the old engine (duration per clip + GAP_SECONDS)."""
    ffprobe = os.environ.get("FFPROBE_BIN", "ffprobe")
    with open('audio/metadata.json', 'r') as f:
        metadata = json.load(f)

    clip_timing = []
    audio_files = []
    current_time = 0.0
    for entry in metadata:
        path = entry['audio_file']
        if not entry.get('exists', False) or not os.path.exists(path):
            continue
        try:
            duration = probe_duration(path, ffprobe)
        except Exception:
            log(f"   skipping unreadable audio: {path}")
            continue
        clip_timing.append({
            'start': current_time,
            'end': current_time + duration,
            'speaker': entry['speaker'],
            'text': entry['text'],
            'index': entry['index'],
        })
        audio_files.append(path)
        current_time += duration + GAP_SECONDS

    return clip_timing, audio_files, current_time


def caption_events(clip_timing):
    """Identical chunking/word-timing to the old engine."""
    events = []
    for timing in clip_timing:
        words = timing['text'].split()
        duration = timing['end'] - timing['start']
        chunks = [words[i:i + CHUNK_SIZE] for i in range(0, len(words), CHUNK_SIZE)]
        if not chunks:
            continue
        chunk_duration = duration / len(chunks)
        for ci, chunk_words in enumerate(chunks):
            chunk_start = timing['start'] + ci * chunk_duration
            chunk_text = ' '.join(chunk_words)
            word_duration = chunk_duration / len(chunk_words)
            for wi in range(len(chunk_words)):
                events.append({
                    'start': chunk_start + wi * word_duration,
                    'end': chunk_start + (wi + 1) * word_duration,
                    'chunk_text': chunk_text,
                    'active_word_idx': wi,
                })
    return events


def speaker_intervals(clip_timing):
    iv = {'peter': [], 'stewie': []}
    for t in clip_timing:
        if t['speaker'] in iv:
            iv[t['speaker']].append((t['start'], t['end']))
    return iv


def enable_expr(intervals):
    if not intervals:
        return "0"
    return "+".join(f"between(t,{a:.4f},{b:.4f})" for a, b in intervals)


def assemble():
    t_start = time.time()
    log("=" * 60)
    log("🎬 VIDEO ASSEMBLY — FAST FFMPEG FILTERGRAPH ENGINE")
    log("=" * 60)

    os.makedirs('output', exist_ok=True)
    frames_dir = 'output/fast_tmp'
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)

    log("\n⏱️ CALCULATING TIMING...")
    clip_timing, audio_files, total_duration = build_timing()
    if not audio_files:
        raise SystemExit("no usable audio clips")
    total_frames = int(total_duration * FPS) + 1
    log(f"   Total duration: {total_duration:.2f}s ({total_frames} frames)")
    with open('output/timing.json', 'w') as f:
        json.dump(clip_timing, f, indent=2)

    log("\n🎭 LOADING CHARACTERS...")
    chars = {}
    for name in ['peter', 'stewie']:
        c = load_character(name)
        if c:
            chars[name] = c
            log(f"   ✅ {name}: {c['w']}x{c['h']}")

    log("\n🔤 LOADING CAPTION FONT...")
    font = find_font()

    log("\n📝 COMPUTING WORD-LEVEL TIMING...")
    events = caption_events(clip_timing)
    log(f"   {len(events)} word-highlight events")

    frame_state = [None] * total_frames
    for ev in events:
        sf = max(0, int(ev['start'] * FPS))
        ef = min(total_frames, int(ev['end'] * FPS) + 1)
        for f_idx in range(sf, ef):
            if ev['start'] <= f_idx / FPS < ev['end']:
                frame_state[f_idx] = (ev['chunk_text'], ev['active_word_idx'])

    state_cache = {}
    sequence = []          # [png_path, top_y, frame_count]
    for f_idx in range(total_frames):
        st = frame_state[f_idx]
        if st is None:
            if sequence and sequence[-1][0] is None:
                sequence[-1][2] += 1
            else:
                sequence.append([None, 0, 1])
            continue
        if st not in state_cache:
            rendered = caption_block(st[0], st[1], font)
            if rendered is None:
                state_cache[st] = (None, 0)
            else:
                block, top = rendered
                path = f"{frames_dir}/cap_{len(state_cache):04d}.png"
                block.save(path)
                state_cache[st] = (path, top)
        path, top = state_cache[st]
        if sequence and sequence[-1][0] == path and sequence[-1][1] == top:
            sequence[-1][2] += 1
        else:
            sequence.append([path, top, 1])

    log(f"   {len(state_cache)} unique caption images, {len(sequence)} timeline runs")

    # caption layer: sequence runs reference (path, top_y) pairs — rebuild the
    # concat list so the overlay places each strip at its own y offset.
    blank = f"{frames_dir}/blank.png"
    Image.new("RGBA", (CANVAS_W, 8), (0, 0, 0, 0)).save(blank)

    # 1) one caption video per distinct y offset is overkill; instead place all
    #    strips on a full-canvas transparent sheet per run (same visual result,
    #    one video input, exact y placement per strip).
    strip_frames = []
    for path, top, frames in sequence:
        strip_frames.append((path, top, frames))

    # 2) build the caption layer as a full-canvas RGBA video: for every run,
    #    paste the strip at (0, top) onto a transparent canvas and emit
    #    `frames` copies via the concat demuxer.
    canvas_frames_dir = f"{frames_dir}/caps_canvas"
    shutil.rmtree(canvas_frames_dir, ignore_errors=True)
    os.makedirs(canvas_frames_dir, exist_ok=True)

    frame_idx = 0
    list_path = f"{frames_dir}/caps_canvas.txt"
    with open(list_path, "w") as f:
        for path, top, frames in strip_frames:
            if path:
                strip = Image.open(path)
                canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
                canvas.paste(strip, (0, top), strip)
            else:
                canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
            cf = f"{canvas_frames_dir}/c_{frame_idx:05d}.png"
            canvas.save(cf)
            for _ in range(frames):
                f.write(f"file '{cf}'\n")
                f.write(f"duration {1.0 / FPS:.6f}\n")
                frame_idx += 1
            if frame_idx >= total_frames:
                break
        # concat demuxer needs the last file repeated once
        f.write(f"file '{cf}'\n")

    log("\n🧩 BUILDING CAPTION LAYER...")
    caps_video = f"{frames_dir}/captions.mov"
    subprocess.run([
        FFMPEG, '-y', '-f', 'concat', '-safe', '0', '-i', list_path,
        '-fps_mode', 'cfr', '-r', str(FPS),
        '-c:v', 'png', '-pix_fmt', 'rgba', caps_video,
    ], check=True, capture_output=True)
    shutil.rmtree(canvas_frames_dir, ignore_errors=True)
    log(f"   ✅ caption layer ready ({time.time() - t_start:.1f}s elapsed)")

    log("\n🎞️ SINGLE-PASS RENDER (background + characters + captions + audio)...")
    iv = speaker_intervals(clip_timing)
    cmd = [FFMPEG, '-y', '-stream_loop', '-1', '-i', 'assets/minecraft_bg.mp4']
    order = [n for n in ['peter', 'stewie'] if n in chars]
    for name in order:
        cmd += ['-loop', '1', '-i', chars[name]['path']]
    cmd += ['-i', caps_video]
    for a in audio_files:
        cmd += ['-i', a]

    filters = [
        f"[0:v]hqdn3d=1.5:1.5:6:6,scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase:"
        f"flags=lanczos,crop={CANVAS_W}:{CANVAS_H},unsharp=5:5:1.0:5:5:0.0,"
        f"eq=saturation=1.2:contrast=1.05,fps={FPS}[bg]",
    ]
    idx = 1
    last = "bg"
    for name in order:
        c = chars[name]
        y = CANVAS_H - c['h'] + 40
        x = 30 if name == 'peter' else CANVAS_W - c['w'] - 30
        out = f"v{idx}"
        expr = "+".join(f"gte(t,{a:.4f})*lt(t,{b:.4f})" for a, b in iv[name])
        filters.append(f"[{last}][{idx}:v]overlay={x}:{y}:format=auto:enable='{expr}'[{out}]")
        last = out
        idx += 1

    caps_idx = idx
    filters.append(f"[{last}][{caps_idx}:v]overlay=0:0[vout]")

    first_audio = caps_idx + 1

    # --- AUDIO: SUM WITH normalize=0 (NOT amix+volume) ---------------------
    # The old chain was `adelay ... amix, volume=N`. That is wrong: amix
    # re-normalises by the number of *active* inputs, so as each clip finished
    # the residual gain grew from 1x to Nx -> the tail of the video clipped
    # (measured peak ramp 0.48 -> 1.00, 1347 clipped samples) which is exactly
    # the harsh "coughing" voice at the end. Our clips are strictly sequential
    # (separated by GAP_SECONDS, never overlapping), so a plain SUM with
    # normalize=0 reproduces the original levels with zero clipping.
    mix = []
    for i, path in enumerate(audio_files):
        delay = int(clip_timing[i]['start'] * 1000)
        filters.append(f"[{first_audio + i}:a]adelay={delay}|{delay}[d{i}]")
        mix.append(f"[d{i}]")
    filters.append(
        f"{''.join(mix)}amix=inputs={len(audio_files)}:duration=longest:"
        f"dropout_transition=0:normalize=0[cat]"
    )
    # safety limiter: nothing can ever reach full scale
    filters.append("[cat]alimiter=limit=0.95:level=disabled[outa]")

    cmd += [
        '-filter_complex', ";".join(filters),
        '-map', '[vout]', '-map', '[outa]',
        '-t', f"{total_duration:.3f}",
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        '-shortest', 'output/final_reel.mp4',
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        log(proc.stderr[-3000:])
        raise SystemExit(f"ffmpeg render failed ({proc.returncode})")
    log(f"✅ DONE: output/final_reel.mp4 in {time.time() - t_start:.1f}s")

    shutil.rmtree(frames_dir, ignore_errors=True)


if __name__ == '__main__':
    assemble()