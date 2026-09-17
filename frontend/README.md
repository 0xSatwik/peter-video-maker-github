# Frontend — Cloudflare Pages + Functions + D1

Topic in → Gemini writes `SPEAKER|TAGS|DIALOGUE` script → committed to repo →
Kaggle TTS workflow dispatched → video assembled → temp link back. Key-gated,
progress + elapsed time survive refresh (job id in localStorage, state in D1).

## One-time setup (Cloudflare dashboard)

1. **Pages project**: Workers & Pages → Create → Pages → Upload assets (or connect
   this repo, build output = `frontend/`). Framework: None, output dir: repo root
   of `frontend/` (set **Root directory** to `frontend` if connecting git).
2. **D1**: Storage → D1 → Create `peter-jobs` → Console → paste `schema.sql` → Execute.
3. **Bind D1**: Pages project → Settings → Functions → D1 bindings → add `DB` → `peter-jobs`.
4. **Env vars** (Settings → Environment variables, Production):
   - `ACCESS_KEY` — the frontend gate key (never commit it)
   - `GITHUB_PAT` — repo-scoped token (`contents:write`, `actions:write`)
   - `GITHUB_REPO` — `0xSatwik/peter-video-maker-github`
   - `GEMINI_PROXY` — `https://gemini-web-proxy.dipteshray7.workers.dev/v1/chat/completions`
   - `GEMINI_MODEL` — `gemini-3.7-flash`
   - `CALLBACK_SECRET` — random string, also added as GitHub repo secret
5. **GitHub repo secrets** (repo Settings → Secrets → Actions):
   - `KAGGLE_USERNAME`, `KAGGLE_KEY` (Kaggle auto TTS)
   - `CALLBACK_URL` — `https://<your-pages-domain>/api/complete`
   - `CALLBACK_SECRET` — same value as above

## Flow

- `POST /api/generate {topic, max_tokens}` → Gemini script → commit
  `config/scripts/AUTO_<ts>.txt` (first line `# JOB:<uuid>`) → dispatch
  `generate-kaggle.yml` → D1 row `gh_queued`.
- `GET /api/status?id=` → D1 row + live GitHub run state + elapsed ms.
  Frontend polls every 10s; timer ticks every 1s.
- Workflow end step: uploads `final_reel.mp4` to tmpfiles.org
  (`expire=86400`, files must be <100MB) → `POST /api/complete`
  → D1 `done` + `temp_url`. Manual Colab runs have no `# JOB:` line,
  so the callback step skips itself.
