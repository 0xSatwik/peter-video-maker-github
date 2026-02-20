import modal
import os
import base64
import gc
import time
import warnings

app = modal.App("moss-tts-voice-api")
volume = modal.Volume.from_name("moss-tts-models", create_if_missing=True)

# Dependencies matching the notebook (Step 2)
# Voice samples are baked into the image via add_local_file
image = (
    modal.Image.from_registry(
        "pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel",
        add_python="3.10"
    )
    .env({"DEBIAN_FRONTEND": "noninteractive", "TZ": "Etc/UTC"})
    .apt_install("ffmpeg", "git")
    .pip_install(
        "transformers>=4.40.0",
        "accelerate",
        "torchaudio",
        "librosa",
        "soundfile",
        "einops",
        "omegaconf",
        "pyyaml",
        "scipy",
        "datasets",
        "sentencepiece",
        "protobuf",
        "fastapi[standard]",
    )
    .add_local_file("assets/peter-vocie.mp3", "/voice_samples/peter-vocie.mp3")
    .add_local_file("assets/Stewies-voice.mp3", "/voice_samples/Stewies-voice.mp3")
)

# Voice sample paths (inside the mounted volume)
VOICE_SAMPLES = {
    "peter": "/voice_samples/peter-vocie.mp3",
    "stewie": "/voice_samples/Stewies-voice.mp3",
}

# "High Quality (24 RVQ)" preset from the notebook
HIGH_QUALITY = {
    "n_vq": 24,
    "text_temp": 1.5,
    "audio_temp": 0.95,
    "text_top_p": 1.0,
    "audio_top_p": 0.95,
    "text_top_k": 50,
    "audio_top_k": 50,
    "audio_rep_pen": 1.1,
}


@app.cls(
    gpu="T4",
    image=image,
    timeout=3600,
    volumes={"/models": volume},
    scaledown_window=300,
)
class MossTTSService:

    @modal.enter()
    def setup(self):
        """Load MOSS-TTS 1.7B model (matches notebook Step 4)"""
        import torch
        from transformers import AutoModel, AutoProcessor

        warnings.filterwarnings('ignore', category=FutureWarning)
        warnings.filterwarnings('ignore', category=UserWarning)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        # Memory optimizations (best-effort, not all available in every PyTorch version)
        if self.device == "cuda":
            try:
                torch.backends.cuda.enable_flash_sdp(True)
                torch.backends.cuda.enable_mem_efficient_sdp(True)
                torch.backends.cuda.enable_math_sdp(True)
            except AttributeError:
                print("⚠️ Some SDP optimizations not available, skipping")

        print("🔄 Loading MOSS-TTS 1.7B...")
        model_cache = "/models/moss-tts-cache"

        self.processor = AutoProcessor.from_pretrained(
            "OpenMOSS-Team/MOSS-TTS-Local-Transformer",
            trust_remote_code=True,
            cache_dir=model_cache,
        )
        self.processor.audio_tokenizer = self.processor.audio_tokenizer.to(self.device)

        if self.device == "cuda":
            torch.cuda.empty_cache()
            gc.collect()

        attn = "sdpa" if self.device == "cuda" else "eager"
        self.model = AutoModel.from_pretrained(
            "OpenMOSS-Team/MOSS-TTS-Local-Transformer",
            trust_remote_code=True,
            attn_implementation=attn,
            torch_dtype=self.dtype,
            low_cpu_mem_usage=True,
            cache_dir=model_cache,
        ).to(self.device)

        self.model.eval()

        # Cache model weights in volume
        volume.commit()

        if self.device == "cuda":
            torch.cuda.empty_cache()
            gc.collect()
            vram = torch.cuda.memory_allocated() / 1024**3
            print(f"✅ MOSS-TTS loaded! VRAM: {vram:.2f}GB")

        # Log available voice samples
        for name, path in VOICE_SAMPLES.items():
            exists = os.path.exists(path)
            print(f"🎙️ Voice sample '{name}': {'✅ found' if exists else '❌ missing'} at {path}")

    @modal.method()
    def generate(self, text: str, speaker: str = "peter") -> bytes:
        """Generate speech with voice cloning (matches notebook generate_speech)"""
        import torch
        import torchaudio
        from transformers import GenerationConfig

        print(f"🎤 [{speaker.upper()}]: {text[:80]}...")

        # Build conversation with voice reference
        voice_path = VOICE_SAMPLES.get(speaker.lower())
        if voice_path and os.path.exists(voice_path):
            print(f"🎙️ Voice cloning: {os.path.basename(voice_path)}")
            conversations = [[
                self.processor.build_user_message(text=text, reference=[voice_path])
            ]]
        else:
            print(f"🎙️ Default voice (no reference for '{speaker}')")
            conversations = [[
                self.processor.build_user_message(text=text)
            ]]

        # Process input
        batch = self.processor(conversations, mode="generation")
        input_ids = batch["input_ids"].to(self.device)
        attention_mask = batch["attention_mask"].to(self.device)

        # Fix temperature bug (from notebook)
        text_temp = HIGH_QUALITY["text_temp"]
        audio_temp = HIGH_QUALITY["audio_temp"]
        if text_temp == 1.0:
            text_temp = 1.001
        if audio_temp == 1.0:
            audio_temp = 1.001

        n_vq = HIGH_QUALITY["n_vq"]

        # Estimate max_new_tokens based on text length
        # ~150 words/min = ~2.5 words/sec, 12.5 tokens/sec audio
        words = len(text.split())
        est_duration = words / 2.5
        max_new_tokens = int(est_duration * 12.5 * 1.5)  # 50% buffer
        max_new_tokens = max(200, min(max_new_tokens, 2500))

        # DelayGenerationConfig (from notebook's custom class)
        generation_config = GenerationConfig()
        generation_config.pad_token_id = self.processor.tokenizer.pad_token_id
        generation_config.eos_token_id = 151653
        generation_config.max_new_tokens = max_new_tokens
        generation_config.use_cache = True
        generation_config.do_sample = True
        generation_config.num_beams = 1

        # MOSS-TTS specific attributes
        generation_config.n_vq_for_inference = n_vq
        generation_config.do_samples = [True] * (n_vq + 1)
        generation_config.layers = [
            {
                "repetition_penalty": 1.0,
                "temperature": text_temp,
                "top_p": HIGH_QUALITY["text_top_p"],
                "top_k": HIGH_QUALITY["text_top_k"],
            }
        ] + [
            {
                "repetition_penalty": HIGH_QUALITY["audio_rep_pen"],
                "temperature": audio_temp,
                "top_p": HIGH_QUALITY["audio_top_p"],
                "top_k": HIGH_QUALITY["audio_top_k"],
            }
        ] * n_vq

        # Clear cache before generation
        if self.device == "cuda":
            torch.cuda.empty_cache()
            gc.collect()

        # Generate
        start_time = time.time()

        with torch.no_grad():
            outputs = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                generation_config=generation_config,
            )

        gen_time = time.time() - start_time

        # Decode audio
        decoded_messages = self.processor.decode(outputs)
        audio = decoded_messages[0].audio_codes_list[0]

        # Clean up GPU memory
        if self.device == "cuda":
            del outputs, input_ids, attention_mask, batch, decoded_messages
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            gc.collect()

        # Save to WAV
        output_path = f"/tmp/tts_{speaker}_{int(time.time())}.wav"
        torchaudio.save(
            output_path,
            audio.unsqueeze(0),
            self.processor.model_config.sampling_rate,
        )

        duration = len(audio) / self.processor.model_config.sampling_rate
        print(f"✅ Generated {duration:.1f}s speech in {gen_time:.1f}s (RTF: {gen_time/duration:.2f}x)")

        with open(output_path, "rb") as f:
            return f.read()


# === API Endpoint for GitHub Actions ===
@app.function(
    image=image,
    gpu="T4",
    timeout=3600,
    volumes={"/models": volume},
)
@modal.fastapi_endpoint(method="POST")
def generate_audio(request: dict):
    service = MossTTSService()
    audio_bytes = service.generate.remote(
        text=request.get("text", ""),
        speaker=request.get("speaker", "peter"),
    )
    return {"audio_base64": base64.b64encode(audio_bytes).decode()}
