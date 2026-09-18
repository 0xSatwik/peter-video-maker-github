const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
};
const AGENT_URL = "https://peter-agent.onrender.com";

const key = () => localStorage.getItem("pv_key") || "";
const headers = () => ({ "Content-Type": "application/json", "x-access-key": key() });
const agent = async (path, body) => {
  const r = await fetch((localStorage.getItem("pv_agent") || AGENT_URL) + path, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
};

let timer = null, poller = null, startedAt = 0, doneAt = 0, agentToken = null;

function fmt(ms) {
  const s = Math.floor(ms / 1000);
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
function tick() {
  $("elapsed").textContent = fmt((doneAt || Date.now()) - startedAt);
}
function stagePct(stage) {
  const m = { queued: 5, script_ready: 12, gh_queued: 20, kaggle_tts: 55, assembling: 80, done: 100, error: 100 };
  return m[stage] ?? 10;
}

function show(el, on) { el.classList.toggle("hidden", !on); }

async function showJob(id) {
  show($("app"), false); show($("draftCard"), false); show($("job"), true);
  $("jobId").textContent = id.slice(0, 8);
  clearInterval(poller); clearInterval(timer);
  const poll = async () => {
    try {
      const j = await api("/api/status?id=" + encodeURIComponent(id), { headers: headers() });
      startedAt = j.created_at; doneAt = j.done_at || 0;
      $("stage").textContent = j.status + (j.progress ? " — " + j.progress : "");
      $("barFill").style.width = stagePct(j.status) + "%";
      if (j.script) $("script").textContent = j.script;
      if (j.status === "done" || j.status === "error") {
        clearInterval(poller); tick(); loadHistory();
        if (j.status === "done" && j.temp_url) { $("dl").href = j.temp_url; show($("dl"), true); }
      }
      tick();
    } catch (e) { $("stage").textContent = "poll error: " + e.message; }
  };
  await poll();
  timer = setInterval(tick, 1000);
  poller = setInterval(poll, 10000);
}

// Fire-and-forget warm-up: the Render free tier sleeps after ~15 min idle, so
// ping /health as soon as the page loads to start waking the agent.
function warmAgent() {
  try {
    fetch((localStorage.getItem("pv_agent") || AGENT_URL) + "/health", { cache: "no-store" }).catch(() => {});
  } catch { /* ignore */ }
}

$("unlock").onclick = async () => {
  warmAgent();
  const k = $("key").value.trim();
  if (!k) return;
  localStorage.setItem("pv_key", k);
  try { await api("/api/status?id=", { headers: headers() }); }
  catch (e) {
    if (e.message === "unauthorized") { $("gateMsg").textContent = "Wrong key."; localStorage.removeItem("pv_key"); return; }
  }
  $("gate").classList.add("hidden");
  show($("app"), true); show($("history"), true);
  loadHistory();
  const last = localStorage.getItem("pv_job");
  if (last) showJob(last);
  else if (localStorage.getItem("pv_draft")) restoreDraft();
};

/* ---------- history (D1) ---------- */
async function loadHistory() {
  try {
    const j = await api("/api/jobs", { headers: headers() });
    const ul = $("historyList");
    ul.innerHTML = "";
    const jobs = j.jobs || [];
    $("historyEmpty").classList.toggle("hidden", jobs.length > 0);
    for (const job of jobs) {
      const li = document.createElement("li");
      const cls = job.status === "done" ? "done" : (job.status === "error" ? "error" : "working");
      const label = job.status === "done" ? "ready" : (job.status === "error" ? "failed" : "working");
      li.innerHTML = `<span class="badge ${cls}">${label}</span>` +
        `<span class="t"></span><span class="d"></span>`;
      li.querySelector(".t").textContent = job.topic || "(untitled)";
      li.querySelector(".d").textContent = new Date(job.created_at).toLocaleString();
      li.onclick = () => {
        if (job.status === "done" && job.temp_url) window.open(job.temp_url, "_blank", "noopener");
        else { localStorage.setItem("pv_job", job.id); showJob(job.id); }
      };
      ul.appendChild(li);
    }
  } catch { /* history is optional */ }
}
$("refresh").onclick = loadHistory;

$("draft").onclick = async () => {
  const topic = $("topic").value.trim();
  if (!topic) return;
  $("draft").disabled = true;
  const t0 = Date.now();
  // The Render free tier sleeps after ~15 min idle: the first request can take
  // 30-90s to wake it. Show a live timer so it never looks like a hang.
  $("draftState").textContent = "agent starting (may take up to ~60s if waking)...";
  const tickDraft = setInterval(() => {
    const s = Math.round((Date.now() - t0) / 1000);
    $("draftState").textContent = s < 8
      ? "agent starting (may take up to ~60s if waking)..."
      : `agent working: researching live web + writing (${s}s)`;
  }, 1000);
  try {
    const j = await agent("/api/plan", {
      topic, max_tokens: parseInt($("maxtokens").value || "600", 10),
    });
    agentToken = j.token;
    $("scriptBox").value = j.script;
    const steps = (j.steps || []).length;
    $("draftState").textContent =
      `drafted in ${Math.round((Date.now() - t0) / 1000)}s · ${steps} agent steps · research ${j.digest_chars} chars`;
    localStorage.setItem("pv_draft", JSON.stringify({
      topic, script: j.script, token: j.token, state: $("draftState").textContent,
    }));
    show($("app"), false); show($("draftCard"), true);
  } catch (e) {
    $("draftState").textContent = `failed after ${Math.round((Date.now() - t0) / 1000)}s: ${e.message} — the agent may still be waking, try again in 30s`;
  }
  clearInterval(tickDraft);
  $("draft").disabled = false;
};

$("revise").onclick = async () => {
  const instruction = $("instruction").value.trim();
  const script = $("scriptBox").value.trim();
  if (!instruction || !script) return;
  $("revise").disabled = true;
  $("draftState").textContent = "agent revising...";
  try {
    const j = await agent("/api/revise", { token: agentToken, instruction, script });
    agentToken = j.token || agentToken;
    $("scriptBox").value = j.script;
    $("draftState").textContent = "revised";
    localStorage.setItem("pv_draft", JSON.stringify({
      topic: $("topic").value.trim(), script: j.script, token: agentToken, state: "revised",
    }));
    $("instruction").value = "";
  } catch (e) { $("draftState").textContent = "failed: " + e.message; }
  $("revise").disabled = false;
};

$("approve").onclick = async () => {
  const script = $("scriptBox").value.trim();
  const topic = $("topic").value.trim() || JSON.parse(localStorage.getItem("pv_draft") || "{}").topic;
  if (!script || !topic) return;
  $("approve").disabled = true;
  try {
    const j = await api("/api/generate", {
      method: "POST", headers: headers(),
      body: JSON.stringify({ topic, script }),
    });
    localStorage.setItem("pv_job", j.id);
    localStorage.removeItem("pv_draft");
    startedAt = Date.now(); doneAt = 0;
    showJob(j.id);
  } catch (e) { alert("Failed: " + e.message); }
  $("approve").disabled = false;
};

$("back").onclick = () => {
  show($("draftCard"), false); show($("app"), true);
};

function restoreDraft() {
  try {
    const d = JSON.parse(localStorage.getItem("pv_draft"));
    if (d && d.script) {
      $("topic").value = d.topic || "";
      $("scriptBox").value = d.script;
      agentToken = d.token || null;
      $("draftState").textContent = d.state || "draft restored";
      show($("app"), false); show($("draftCard"), true);
    }
  } catch { /* ignore */ }
}

$("reset").onclick = () => {
  localStorage.removeItem("pv_job");
  clearInterval(poller); clearInterval(timer);
  show($("job"), false); show($("dl"), false);
  $("app").classList.remove("hidden");
  loadHistory();
};

if (key()) {
  warmAgent();
  $("gate").classList.add("hidden");
  show($("app"), true); show($("history"), true);
  loadHistory();
  const last = localStorage.getItem("pv_job");
  if (last) showJob(last);
  else restoreDraft();
}
