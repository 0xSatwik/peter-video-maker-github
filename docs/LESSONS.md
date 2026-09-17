# Lessons (append-only, newest last)

Format: `TRIGGER -> RULE`

- Workflow YAML step name contained ": " (`Verify audio files (guard: need WAVs + metadata)`) -> Never put an unquoted `: ` inside a YAML scalar; GitHub run failed with `mapping values are not allowed here`.
- Cloudflare Worker calling GitHub API got 403 while the same PAT worked from PowerShell -> Cloudflare Workers send no User-Agent; GitHub rejects such requests. Add `"User-Agent": "..."` to every GitHub API call in Functions/Workers.
- Render agent returned `no research available` with 0 urls -> Monid calls need the `/run` suffix (`https://api.monid.ai/v1/run`) and results live at `j.output.results`; also `r.json()` must be parsed once (double parse threw and was silently swallowed).
- Render deploys hung / failed while "build successful" -> the deploy ran node and crashed (`SyntaxError: Unexpected end of input`, a missing `}`); `git push` alone is not enough when using the Render API deploy. Always `node --check` before pushing and read `/v1/logs?resource=<service>` for the runtime error.
- Render wants a GitHub App connection -> not needed for public repos: create/deploy via REST (`POST /v1/services/{id}/deploys` with the API key) and it clones fine.
- Kaggle TTS fails with `Maximum batch GPU session count of 2 reached` -> free-tier GPU quota; workflow now falls back to CPU `edge-tts` (`scripts/tts_cpu.py`) so a run still produces a video.
- actions/upload-artifact failed on `audio/*.wav` -> a stray file named `audio/format: speaker_000.wav` broke the glob (colon in path). Glob explicit `audio/peter_*.wav` + `audio/stewie_*.wav`.
- tmpfiles.org accepted the 79 MB upload but its link returns an HTML page (no direct file, `Content-Type: text/html`) -> use sto.care (`PUT https://ul.sto.care/<name>`, verified: real bytes back, `video/mp4`, correct filename, 100 MB, 72 h) with gofile as the >100 MB fallback. Zipping an MP4 saves nothing, so a bigger-limit host is the only real fix.
- storage.to works but multipart assemble payload is undocumented -> `/upload/complete-multipart` returned `MalformedXML`/`Upload is no longer active` for every guess, and a failed assemble invalidates the upload. Skip hosts that require chunked/multipart flows for CI uploads.
- Windows PowerShell here-docs and multi-line `python -c` fail -> write a small `.py`/`.js` file and run it.
- Local `git push` had stale credential-manager creds (`remote: invalid credentials`) -> push via `agent/ghpush.js` (contents API) or set the remote URL with the PAT; also every `git pull --rebase` conflict must be resolved before the next pull ("Pulling is not possible because you have unmerged files").