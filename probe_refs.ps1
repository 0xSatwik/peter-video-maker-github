$ErrorActionPreference = "Continue"
$ff = python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
$ff = $ff.Trim()
$out = @()
foreach ($f in @('assets/perter10seonds.wav','assets/peter-voice.mp3','assets/Stewies-voice.mp3')) {
  $o = cmd /c "`"$ff`" -hide_banner -i `"$f`" 2>&1" | Out-String
  $out += "=== $f"
  $out += ($o -split "`n" | Select-String 'Duration|Stream.*Audio' | ForEach-Object { $_.Line.Trim() })
}
$out | Out-File output\refs.txt -Encoding utf8
Get-Content output\refs.txt