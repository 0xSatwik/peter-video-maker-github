const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
};
const agent = async (path, body) => {
  const r = await fetch((localStorage.getItem("pv_agent") || "") + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-access-key": key() },
    body: JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
};
const key = () => localStorage.getItem("pv_key") || "";
const headers = () => ({ "Content-Type": "application/json", "x-access-key": key() });

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
      if (j.status === "done") {
        clearInterval(poller); tick();
        if (j.temp_url) { $("dl").href = j.temp_url; show($("dl"), true); }
      }
      tick();
    } catch (e) { $("stage").textContent = "poll error: " + e.message; }
  };
  await poll();
  timer = setInterval(tick, 1000);
  poller = setInterval(poll, 10000);
}

$("unlock").onclick = async () => {
  const k = $("key").value.trim();
  const a = $("agentUrl").value.trim().replace(/\/$/, "");
  if (a) localStorage.setItem("pv_agent", a);
  if (!k) return;
  localStorage.setItem("pv_key", k);
  try { await api("/api/status?id=", { headers: headers() }); }
  catch (e) {
    if (e.message === "unauthorized") { $("gateMsg").textContent = "Wrong key."; return; }
  }
  $("gate").classList.add("hidden");
  show($("app"), true);
  const last = localStorage.getItem("pv_job");
  if (last) showJob(last);
  else if (localStorage.getItem("pv_draft")) restoreDraft();
};

$("draft").onclick = async () => {
  const topic = $("topic").value.trim();
  if (!topic) return;
  $("draft").disabled = true;
  $("draftState").textContent = "agent researching live web...";
  try {
    const j = await agent("/api/plan", {
      topic, max_tokens: parseInt($("maxtokens").value || "600", 10),
    });
    agentToken = j.token;
    $("scriptBox").value = j.script;
    $("draftState").textContent = `drafted (research: ${j.digest_chars} chars)`;
    localStorage.setItem("pv_draft", JSON.stringify({
      topic, script: j.script, token: j.token, state: $("draftState").textContent,
    }));
    show($("app"), false); show($("draftCard"), true);
  } catch (e) { $("draftState").textContent = "failed: " + e.message; }
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
};

if (key()) {
  $("gate").classList.add("hidden");
  $("agentUrl").value = localStorage.getItem("pv_agent") || "";
  show($("app"), true);
  const last = localStorage.getItem("pv_job");
  if (last) showJob(last);
  else restoreDraft();
}
