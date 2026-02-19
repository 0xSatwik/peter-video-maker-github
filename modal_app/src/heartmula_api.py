import modal
import os
import subprocess
import shutil
from pathlib import Path

app = modal.App("heartmula-voice-music-api")
volume = modal.Volume.from_name("heartmula-models", create_if_missing=True)

# EXACT dependencies from your Notebook Cell 1
# Using PyTorch CUDA devel image (has nvcc + torch pre-installed)
image = (
    modal.Image.from_registry(
        "pytorch/pytorch:2.1.2-cuda12.1-cudnn8-devel",
        add_python="3.10"
    )
    .env({"DEBIAN_FRONTEND": "noninteractive", "TZ": "Etc/UTC"})
    .apt_install("ffmpeg", "git", "wget")
    .pip_install(
        "numpy<2",
        "packaging",
        "huggingface_hub>=1.3.0,<2.0",
        "accelerate",
        "gradio",
        "fastapi[standard]",
    )
    .pip_install(
        "flash-attn<=2.5.8",
        extra_options="--no-build-isolation"
    )
)

@app.cls(
    gpu="T4",  # Matches your Notebook (T4 GPU 15GB VRAM)
    image=image,
    timeout=3600,
    volumes={"/models": volume},
    scaledown_window=300,
)
class HeartMuLaService:
    @modal.enter()
    def setup(self):
        """Your Notebook Cell 1 + Cell 2"""
        print("🔧 Setting up (Cell 1)...")
        
        # Clone heartlib (Cell 1)
        if not os.path.exists("/tmp/heartlib"):
            subprocess.run(
                ["git", "clone", "https://github.com/HeartMuLa/heartlib.git", "/tmp/heartlib", "-q"],
                check=True
            )
        
        os.chdir("/tmp/heartlib")
        
        # Install packages (Cell 1)
        subprocess.run(["pip", "install", "-q", "-e", "."], check=True)
        
        # Download Models (Cell 2)
        model_dir = Path("/models/heartmula-3b")
        if not model_dir.exists():
            print("📥 Downloading BF16 models (Cell 2 - One Time)...")
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # HeartMuLa-oss-3B (Cell 2)
            subprocess.run([
                "huggingface-cli", "download",
                "--local-dir", str(model_dir / "HeartMuLa-oss-3B"),
                "benjiaiplayground/HeartMuLa-oss-3B-bf16", "--quiet"
            ], check=True)
            
            # HeartCodec-oss (Cell 2)
            subprocess.run([
                "huggingface-cli", "download",
                "--local-dir", str(model_dir / "HeartCodec-oss"),
                "benjiaiplayground/HeartCodec-oss-bf16", "--quiet"
            ], check=True)
            
            # HeartMuLaGen (Cell 2)
            subprocess.run([
                "huggingface-cli", "download",
                "--local-dir", str(model_dir),
                "HeartMuLa/HeartMuLaGen", "--quiet"
            ], check=True)
            
            # Fix HeartCodec naming (Cell 2)
            codec_file = model_dir / "HeartCodec-oss" / "HeartCodec-oss-bf16.safetensors"
            if codec_file.exists():
                shutil.move(codec_file, model_dir / "HeartCodec-oss" / "model.safetensors")
            
            volume.commit()
            print("✅ Models downloaded!")
        
        os.chdir("/tmp/heartlib")
    
    @modal.method()
    def generate(self, lyrics: str, tags: str, duration: int = 30) -> bytes:
        """Your Notebook Cell 3 - Exact generation command"""
        print(f"🎵 Generating {duration}s with tags: {tags}")
        
        timestamp = "modal_run"
        lyrics_file = f"/tmp/lyrics_{timestamp}.txt"
        tags_file = f"/tmp/tags_{timestamp}.txt"
        output_path = f"/tmp/audio_{timestamp}.mp3"
        
        with open(lyrics_file, "w") as f:
            f.write(lyrics)
        with open(tags_file, "w") as f:
            f.write(tags)
        
        # EXACT command from your Notebook Cell 3
        cmd = [
            "python", "./examples/run_music_generation.py",
            f"--model_path=/models/heartmula-3b",
            "--version=3B",
            "--lazy_load=true",
            f"--lyrics={lyrics_file}",
            f"--tags={tags_file}",
            f"--max_audio_length_ms={duration * 1000}",
            "--temperature=1.0",
            "--topk=50",
            "--cfg_scale=1.5",
            f"--save_path={output_path}"
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        if os.path.exists(output_path):
            with open(output_path, "rb") as f:
                return f.read()
        else:
            raise Exception("Generation failed")

# API Endpoint for GitHub Actions
@app.function(image=image, gpu="T4", timeout=3600)
@modal.fastapi_endpoint(method="POST")
def generate_audio(request: dict):
    service = HeartMuLaService()
    audio_bytes = service.generate.remote(
        lyrics=request.get("lyrics", ""),
        tags=request.get("tags", "speech, clear"),
        duration=request.get("duration", 30)
    )
    import base64
    return {"audio_base64": base64.b64encode(audio_bytes).decode()}
