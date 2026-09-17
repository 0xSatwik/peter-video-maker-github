const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
  return j;
};
const key = () => localStorage.getItem("pv_key") || "";
const headers = () => ({ "Content-Type": "application/json", "x-access-key": key() });

let timer = null, poller = null, startedAt = 0, doneAt = 0;

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

async function showJob(id) {
  $("app").classList.add("hidden");
  $("job").classList.remove("hidden");
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
        if (j.temp_url) { $("dl").href = j.temp_url; $("dl").classList.remove("hidden"); }
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
  if (!k) return;
  localStorage.setItem("pv_key", k);
  try {
    await api("/api/status?id=ping", { headers: headers() });
  } catch (e) { /* ping validates key; ignore job error below */ }
  // validate by attempting a lightweight authed call
  try {
    await api("/api/status?id=", { headers: headers() });
  } catch (e) {
    if (e.message === "unauthorized") { $("gateMsg").textContent = "Wrong key."; return; }
  }
  $("gate").classList.add("hidden");
  $("app").classList.remove("hidden");
  const last = localStorage.getItem("pv_job");
  if (last) showJob(last);
};

$("go").onclick = async () => {
  const topic = $("topic").value.trim();
  if (!topic) return;
  $("go").disabled = true;
  try {
    const j = await api("/api/generate", {
      method: "POST", headers: headers(),
      body: JSON.stringify({ topic, max_tokens: parseInt($("maxtokens").value || "600", 10) }),
    });
    localStorage.setItem("pv_job", j.id);
    startedAt = Date.now(); doneAt = 0;
    showJob(j.id);
  } catch (e) { alert("Failed: " + e.message); }
  $("go").disabled = false;
};

$("reset").onclick = () => {
  localStorage.removeItem("pv_job");
  clearInterval(poller); clearInterval(timer);
  $("job").classList.add("hidden");
  $("dl").classList.add("hidden");
  $("app").classList.remove("hidden");
};

// auto-resume after refresh
if (key()) {
  $("gate").classList.add("hidden");
  $("app").classList.remove("hidden");
  const last = localStorage.getItem("pv_job");
  if (last) showJob(last);
}
