// push workflow + cpu TTS via GitHub REST API (local git push creds broken)
const fs = require("fs");
const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const H = { Authorization: "Bearer " + env.GH_PAT, Accept: "application/vnd.github+json", "User-Agent": "pvm", "Content-Type": "application/json" };
const REPO = "0xSatwik/peter-video-maker-github";
const ROOT = "C:/Users/akasa/Desktop/MYPROJECTS/peter video maker github";

async function put(path, transform, message) {
  const cur = await (await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, { headers: H })).json();
  let content = Buffer.from(cur.content, "base64").toString("utf8");
  content = transform(content);
  const body = { message, content: Buffer.from(content).toString("base64"), sha: cur.sha };
  const r = await (await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, { method: "PUT", headers: H, body: JSON.stringify(body) })).json();
  console.log(path, "->", r.commit ? "OK " + r.commit.sha.slice(0, 7) : "FAIL " + JSON.stringify(r).slice(0, 200));
}

(async () => {
  // 1. new CPU fallback script
  const tts = fs.readFileSync(ROOT + "/scripts/tts_cpu.py", "utf8");
  const ex = await fetch(`https://api.github.com/repos/${REPO}/contents/scripts/tts_cpu.py`, { headers: H });
  const r1 = await (await fetch(`https://api.github.com/repos/${REPO}/contents/scripts/tts_cpu.py`, {
    method: "PUT", headers: H,
    body: JSON.stringify({ message: "CPU TTS fallback (edge-tts) for GH runner", content: Buffer.from(tts).toString("base64"), ...(ex.status === 200 ? { sha: (await ex.json()).sha } : {}) }),
  })).json();
  console.log("tts_cpu.py ->", r1.commit ? "OK" : "FAIL " + JSON.stringify(r1).slice(0, 200));

  // 2. patch the workflow (3 replacements on top of origin version)
  await put(
    ".github/workflows/generate-kaggle.yml",
    (c) => c
      .replace("pip install kaggle\n", "pip install kaggle edge-tts\n")
      .replace("      - name: TTS on Kaggle (auto start/stop, no Colab URL)\n", "      - name: TTS on Kaggle (auto start/stop, CPU fallback on GPU quota)\n")
      .replace("        run: python scripts/kaggle_run.py\n", '        run: |\n          python scripts/kaggle_run.py || { echo "Kaggle GPU unavailable, using CPU fallback"; python scripts/tts_cpu.py "$SCRIPT_FILE"; }\n')
      .replace('          cat audio/metadata.json | python3 -m json.tool || echo "No metadata"\n',
        '          cat audio/metadata.json | python3 -m json.tool || echo "No metadata"\n          echo ""\n          if ! ls audio/*.wav >/dev/null 2>&1; then\n            echo "FATAL: no audio wavs, cannot assemble video"; exit 1\n          fi\n'),
    "Workflow: CPU TTS fallback + audio guard"
  );
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
