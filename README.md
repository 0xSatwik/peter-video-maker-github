# Peter Video Maker

This project generates videos using Peter Griffin and Stewie Griffin assets.

## Structure (New)

- `.github/workflows`: GitHub Actions workflows
- `assets`: Binary assets (video, images, music)
- `assets/peter.jpg`: Peter Griffin image
- `assets/stewie.png`: Stewie Griffin image
- `modal_app`: Modal application logic (HeartMuLa)
- `scripts`: Python scripts for generation and assembly
- `config`: Configuration files (scripts)

## Scripts
- `scripts/generate_audio.py`: Generates voices using Edge TTS and background music using Modal.
- `scripts/assemble_video.py`: Assembles the final video using MoviePy.
- `modal_app/src/heartmula_api.py`: Modal app for music generation.
