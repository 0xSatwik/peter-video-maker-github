import json
import subprocess
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
FFPROBE = FF.replace("ffmpeg", "ffprobe")
if FFPROBE == FF:  # imageio only ships ffmpeg; probe via ffmpeg itself
    for f in [
        "assets/perter10seonds.wav",
        "assets/peter-voice.mp3",
        "assets/Stewies-voice.mp3",
    ]:
        r = subprocess.run(
            [FF, "-hide_banner", "-i", f],
            capture_output=True, text=True, errors="replace",
        )
        info = r.stderr
        for line in info.splitlines():
            if "Duration" in line or "Audio:" in line:
                print(line.strip()[:160])
        print("---", f)
else:
    for f in [
        "assets/perter10seonds.wav",
        "assets/peter-voice.mp3",
        "assets/Stewies-voice.mp3",
    ]:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration,size",
             "-show_entries", "stream=sample_rate,channels,codec_name",
             "-of", "json", f],
            capture_output=True, text=True,
        )
        d = json.loads(r.stdout)
        fmt = d.get("format", {})
        st = (d.get("streams") or [{}])[0]
        print(f, "dur:", fmt.get("duration"), "s | sr:", st.get("sample_rate"),
              "ch:", st.get("channels"), "|", st.get("codec_name"))
