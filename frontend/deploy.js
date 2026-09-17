// Deploy frontend/dist to Cloudflare Pages via REST API only (no CLI).
// Token/account come from ~/.peter-deploy/deploy.env
// Flow (mirrors wrangler): upload-token -> check-missing -> assets/upload -> upsert-hashes
//                          -> POST deployments (manifest + _worker.bundle)
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const env = Object.fromEntries(
  fs.readFileSync(process.env.USERPROFILE + "/.peter-deploy/deploy.env", "utf8")
    .split("\n").filter((l) => l.includes("="))
    .map((l) => [l.split("=")[0].trim(), l.split("=").slice(1).join("=").trim()])
);
const ACCT = env.CLOUDFLARE_ACCOUNT_ID;
const TOKEN = env.CLOUDFLARE_API_TOKEN;
const PROJECT = "peter-video-maker";
const BRANCH = "main";
const DIST = path.join(__dirname, "dist");
const API = "https://api.cloudflare.com/client/v4";

const TYPES = {
  ".html": "text/html", ".js": "application/javascript", ".css": "text/css",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
  ".ico": "image/x-icon", ".txt": "text/plain", ".webmanifest": "application/manifest+json",
};
const md5 = (buf) => crypto.createHash("md5").update(buf).digest("hex");

async function cf(pathname, init = {}) {
  const r = await fetch(API + pathname, {
    ...init,
    headers: { Authorization: "Bearer " + TOKEN, ...(init.headers || {}) },
  });
  const j = await r.json().catch(() => ({}));
  if (!j.success) throw new Error(pathname + " -> " + JSON.stringify(j.errors || j).slice(0, 400));
  return j.result;
}

(async () => {
  if (!fs.existsSync(path.join(DIST, "_worker.js"))) {
    console.error("run `node frontend/build.js` first");
    process.exit(1);
  }

  // 1. collect static assets (worker _worker.js is not a static asset)
  const assets = fs.readdirSync(DIST)
    .filter((f) => fs.statSync(path.join(DIST, f)).isFile() && f !== "_worker.js")
    .map((f) => {
      const buf = fs.readFileSync(path.join(DIST, f));
      return { path: f, buf, hash: md5(buf), type: TYPES[path.extname(f)] || "application/octet-stream" };
    });
  const manifest = Object.fromEntries(assets.map((a) => ["/" + a.path, a.hash]));

  // 2. upload token (scoped JWT for the asset endpoints)
  const { jwt } = await cf(`/accounts/${ACCT}/pages/projects/${PROJECT}/upload-token`);
  const authJwt = { Authorization: "Bearer " + jwt, "Content-Type": "application/json" };

  // 3. which hashes are missing from the store?
  const missing = await cf("/pages/assets/check-missing", {
    method: "POST", headers: authJwt, body: JSON.stringify({ hashes: assets.map((a) => a.hash) }),
  });
  const toUpload = assets.filter((a) => missing.includes(a.hash));

  // 4. upload missing assets (metadata + base64 content)
  for (let i = 0; i < toUpload.length; i += 50) {
    const batch = toUpload.slice(i, i + 50).map((a) => ({
      key: a.hash, value: a.buf.toString("base64"), base64: true,
      metadata: { contentType: a.type },
    }));
    await cf("/pages/assets/upload", { method: "POST", headers: authJwt, body: JSON.stringify(batch) });
  }
  if (toUpload.length) {
    await cf("/pages/assets/upsert-hashes", {
      method: "POST", headers: authJwt, body: JSON.stringify({ hashes: assets.map((a) => a.hash) }),
    });
  }

  // 5. worker bundle (_worker.bundle = serialized multipart form: metadata + module)
  const workerSrc = fs.readFileSync(path.join(DIST, "_worker.js"));
  const bundleForm = new FormData();
  bundleForm.append("metadata", JSON.stringify({
    main_module: "_worker.js",
    compatibility_date: "2024-11-06",
  }));
  bundleForm.append("_worker.js", new Blob([workerSrc], { type: "application/javascript+module" }), "_worker.js");
  const bundleBlob = await new Response(bundleForm).blob();

  // 6. create the deployment
  const deployForm = new FormData();
  deployForm.append("manifest", JSON.stringify(manifest));
  deployForm.append("branch", BRANCH);
  deployForm.append("_worker.bundle", bundleBlob, "_worker.bundle");
  const dep = await cf(`/accounts/${ACCT}/pages/projects/${PROJECT}/deployments`, {
    method: "POST", body: deployForm,
  });

  console.log("deployed:", dep.url);
  console.log("assets:", assets.length, "| uploaded:", toUpload.length, "| id:", dep.id);
  process.exit(0);
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
