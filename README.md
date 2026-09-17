# 🎬 Peter & Stewie Video Maker

Generate **Family Guy short videos** (Instagram Reels) with AI-cloned voices of Peter and Stewie Griffin.

Uses **MOSS-TTS 1.7B** for zero-shot voice cloning, and **GitHub Actions** for automated video assembly.

Two voice pipelines (pick one per run):
- **A. Kaggle Auto (recommended)** — `Generate Short (Kaggle Auto TTS)`: starts a Kaggle GPU kernel, batch-generates all clips, auto-stops. No manual step, no idle credit burn.
- **B. Colab Manual (fallback)** — `Generate Family Guy Short`: you start the Colab notebook, paste the Gradio URL. Use if Kaggle quota is exhausted.

---

## 🚀 Quick Start

### Step 1 (Option B): Launch the Voice AI on Google Colab (manual fallback)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/0xSatwik/peter-video-maker-github/blob/main/learnwithperandstewie.ipynb)

1. Click the badge above to open the notebook
2. Go to **Runtime → Change runtime type → T4 GPU**
3. Click **Runtime → Run all**
4. Wait ~5-8 minutes for the model to load
5. Copy the **public Gradio URL** (e.g., `https://xxxxxxxx.gradio.live`)

### Step 2: Generate the Video

1. Go to **[Actions](../../actions)** → **"Generate Family Guy Short"**
2. Click **"Run workflow"**
3. Paste your **Colab Gradio URL** in the first field
4. (Optional) Change the script file path
5. Click **"Run workflow"** and wait for completion
6. Download the video from the **Artifacts** section

---

## 📁 Project Structure

```
├── assets/                     # Character images + background video + voice samples
│   ├── peter.png               # Peter Griffin character image
│   ├── stewie.png              # Stewie Griffin character image
│   ├── minecraft_bg.mp4        # Background video
│   ├── peter-voice.mp3         # Peter voice reference for cloning
│   └── Stewies-voice.mp3       # Stewie voice reference for cloning
├── config/scripts/             # Dialogue scripts
│   └── EPISODE_01.txt          # Example episode script
├── scripts/                    # Python pipeline scripts
│   ├── generate_audio.py       # Generates voice via Colab Gradio API
│   ├── assemble_video.py       # Assembles video with characters
│   └── add_captions.py         # Adds animated captions
├── learnwithperandstewie.ipynb  # Colab notebook (MOSS-TTS voice AI)
└── .github/workflows/
    └── generate.yml            # GitHub Actions workflow
```

## ✍️ Writing Scripts

Script format (`config/scripts/EPISODE_01.txt`):
```
SPEAKER|TAGS|DIALOGUE TEXT
```

Example:
```
peter|male, deep, speech|Hey Stewie, what are you doing?
stewie|male, high, speech|I'm plotting world domination, obviously.
```

## ⚙️ How It Works

1. **Colab** runs MOSS-TTS 1.7B (zero-shot voice cloning) and exposes a Gradio API
2. **GitHub Actions** sends each dialogue line to the Colab API with the matching voice reference
3. Generated audio clips are assembled into a 1080×1920 video with character images and captions
4. Final video is uploaded as a GitHub Actions artifact

---

*Made with ❤️*
