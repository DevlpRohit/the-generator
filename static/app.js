/* Master AI Video Maker — Flask SSE frontend */

/* ── Pre-fill topic from URL ?topic= param ───────── */
(function () {
  const p = new URLSearchParams(location.search);
  const t = p.get("topic");
  if (t) {
    const el = document.getElementById("topic-input");
    if (el) el.value = t;
  }
})();

/* ── Live word-count estimate for duration inputs ── */
(function () {
  const minEl = document.getElementById("duration-min");
  const secEl = document.getElementById("duration-sec");
  const label = document.getElementById("dur-words");
  if (!minEl || !secEl || !label) return;
  function update() {
    const mins = Math.max(0, parseInt(minEl.value) || 0);
    const secs = Math.max(0, Math.min(59, parseInt(secEl.value) || 0));
    const total = mins * 60 + secs;
    const words = Math.round(total * 2.5);  // ~150 wpm
    label.textContent = total < 5 ? "≈ 10 words (min 10s)" :
                        `≈ ${words} words · ~${mins}m${secs.toString().padStart(2,"0")}s`;
  }
  minEl.addEventListener("input", update);
  secEl.addEventListener("input", update);
  update();
})();

/* ── Fetch trending topics (shared between topic-research and niche-search) ── */
async function fetchTrends({ keyword = "", niche = "" } = {}) {
  const r = await fetch("/research/fetch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ keyword, niche }),
  });
  const d = await r.json();
  if (d.error) throw new Error(d.error);

  const panel = document.getElementById("trends-panel");
  const list  = document.getElementById("trends-list");
  const topics = [...(d.trending_topics || []), ...(d.title_suggestions || [])];

  list.innerHTML = topics.map(t =>
    `<li onclick="pickTrend('${escAttr(t)}')">${escHtml(t)}</li>`
  ).join("") || "<li style='color:var(--muted)'>No results found</li>";

  panel.style.display = "block";
}

/* ── Topic-based research (uses Topic field as keyword) ── */
const researchBtn = document.getElementById("research-btn");
if (researchBtn) {
  researchBtn.addEventListener("click", async () => {
    const kw = (document.getElementById("topic-input")?.value || "").trim();
    if (!kw) { alert("Enter a topic first to research trends"); return; }

    researchBtn.textContent = "Fetching…";
    researchBtn.disabled = true;
    try {
      await fetchTrends({ keyword: kw });
    } catch (e) {
      showError("Research error: " + e.message);
    } finally {
      researchBtn.textContent = "\u{1F4C8} Research Trending Topics";
      researchBtn.disabled = false;
    }
  });
}

/* ── Niche-based search (uses Niche dropdown) ── */
const nicheSearchBtn = document.getElementById("niche-search-btn");
if (nicheSearchBtn) {
  nicheSearchBtn.addEventListener("click", async () => {
    const niche = (document.getElementById("niche-select")?.value || "").trim();
    if (!niche) { alert("Select a niche first"); return; }

    nicheSearchBtn.textContent = "Searching…";
    nicheSearchBtn.disabled = true;
    try {
      await fetchTrends({ keyword: niche, niche });
    } catch (e) {
      showError("Niche search error: " + e.message);
    } finally {
      nicheSearchBtn.textContent = "\u{1F50D} Find Trending in Niche";
      nicheSearchBtn.disabled = false;
    }
  });
}

function pickTrend(topic) {
  const el = document.getElementById("topic-input");
  if (el) el.value = topic;
  const panel = document.getElementById("trends-panel");
  if (panel) panel.style.display = "none";
}

/* ── Risky-niche monetization warning ─────────────── */
(function () {
  const sel  = document.getElementById("niche-select");
  const warn = document.getElementById("niche-warning");
  if (!sel || !warn) return;
  function update() {
    const opt  = sel.selectedOptions[0];
    const risk = opt && opt.dataset ? opt.dataset.risk : "";
    if (risk) {
      warn.innerHTML = "⚠️ <strong>Monetization risk:</strong> " + escHtml(risk);
      warn.style.display = "block";
    } else {
      warn.style.display = "none";
    }
  }
  sel.addEventListener("change", update);
  update();
})();

/* ── Job persistence across page navigations ─────── */
const JOB_KEY = "mvm_active_job";

function saveJob(id) { try { localStorage.setItem(JOB_KEY, id); } catch (_) {} }
function loadJob()   { try { return localStorage.getItem(JOB_KEY); } catch (_) { return null; } }
function clearJob()  { try { localStorage.removeItem(JOB_KEY); } catch (_) {} }

/* ── Track running state (no beforeunload prompt — user can navigate freely) ── */
let jobIsRunning = false;

/* ── Form submission ──────────────────────────────── */
const form = document.getElementById("gen-form");
if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();

    const btn = document.getElementById("generate-btn");
    btn.disabled = true;
    btn.textContent = "Starting…";

    const data = new FormData(form);

    try {
      const r = await fetch("/generate", { method: "POST", body: data });
      const d = await r.json();
      if (d.error) throw new Error(d.error);
      saveJob(d.job_id);
      startSSE(d.job_id);
    } catch (e) {
      showError("Error: " + e.message);
      btn.disabled = false;
      btn.textContent = "⚡ Generate Video";
    }
  });
}

/* ── Auto-resume an active job on page load ──────── */
function probeJob(id) {
  return new Promise((resolve) => {
    const es = new EventSource("/progress/" + id);
    const cleanup = (val) => { try { es.close(); } catch (_) {} resolve(val); };
    es.onmessage = (e) => {
      try { cleanup(JSON.parse(e.data)); } catch (_) { cleanup(null); }
    };
    es.onerror = () => cleanup(null);
    setTimeout(() => cleanup(null), 5000);
  });
}

(async function resumeIfRunning() {
  const id = loadJob();
  if (!id) return;

  const onIndex = !!document.getElementById("progress-card");
  const job = await probeJob(id);
  if (!job) { clearJob(); return; }

  if (job.status === "running") {
    if (onIndex) {
      startSSE(id);
    } else {
      // On Projects/Trends pages — show floating banner with live progress
      showRunningBanner(id);
    }
  } else if (job.status === "done") {
    if (onIndex) {
      const fc = document.querySelector(".form-card");
      if (fc) fc.style.display = "none";
      showResult(job);
    }
    clearJob();
  } else {
    clearJob();
  }
})();

/* ── Floating "video still generating" banner for non-home pages ── */
function showRunningBanner(id) {
  if (document.getElementById("running-banner")) return;
  const banner = document.createElement("a");
  banner.id = "running-banner";
  banner.href = "/";
  banner.innerHTML = `
    <span class="pulse-dot"></span>
    <span>
      <strong>Generating video…</strong>
      <span id="banner-step" style="color:#aaa;margin-left:6px">Working…</span>
    </span>
    <span id="banner-pct" style="margin-left:auto;font-weight:700;color:#fff">0%</span>
  `;
  banner.style.cssText = `
    position:fixed; bottom:16px; right:16px; z-index:1000;
    display:flex; align-items:center; gap:10px;
    background:#1a1a1a; border:1px solid #ff0000;
    border-radius:8px; padding:10px 14px;
    box-shadow:0 4px 16px rgba(255,0,0,.25);
    color:#f1f1f1; font-size:.88rem;
    text-decoration:none; min-width:280px;
  `;
  // Inject pulsing-dot CSS once
  if (!document.getElementById("pulse-style")) {
    const st = document.createElement("style");
    st.id = "pulse-style";
    st.textContent = `
      .pulse-dot{display:inline-block;width:10px;height:10px;border-radius:50%;
        background:#ff0000;animation:pulse 1.4s infinite}
      @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
    `;
    document.head.appendChild(st);
  }
  document.body.appendChild(banner);

  // Live-update via SSE
  const es = new EventSource("/progress/" + id);
  es.onmessage = (e) => {
    try {
      const j = JSON.parse(e.data);
      const pct = document.getElementById("banner-pct");
      const step = document.getElementById("banner-step");
      if (pct) pct.textContent = (j.progress || 0) + "%";
      if (step) step.textContent = j.step || "";
      if (j.status === "done") {
        es.close();
        banner.innerHTML = `<span style="color:#22c55e">&#10003;</span>
          <span><strong>Video ready</strong> — click to view</span>`;
        banner.style.borderColor = "#22c55e";
        clearJob();
      } else if (j.status === "error" || j.status === "not_found") {
        es.close();
        banner.remove();
        clearJob();
      }
    } catch (_) {}
  };
  es.onerror = () => es.close();
}

/* ── SSE progress ─────────────────────────────────── */
let evtSource = null;
let currentJobId = null;

/* ── Stop button (always visible while job runs) ──── */
const stopBtn = document.getElementById("stop-btn");
if (stopBtn) {
  stopBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    if (!confirm("Stop video generation? Any work in progress will be discarded.")) return;
    stopBtn.disabled = true;
    stopBtn.textContent = "Stopping…";
    try {
      await fetch("/job/" + currentJobId + "/cancel", { method: "POST" });
    } catch (_) {}
  });
}

/* ── Script edit panel ───────────────────────────── */
function showEditPanel(jobId, paragraphs) {
  const progCard = document.getElementById("progress-card");
  const editCard = document.getElementById("edit-card");
  const wrap     = document.getElementById("edit-paragraphs");
  if (!editCard || !wrap) return;

  // Only build once
  if (wrap.dataset.built !== "1") {
    wrap.innerHTML = "";
    paragraphs.forEach((p, i) => {
      const block = document.createElement("div");
      block.className = "field";
      block.style.marginBottom = "12px";
      block.innerHTML = `
        <label style="display:flex;justify-content:space-between;align-items:center">
          <span>Paragraph ${i + 1} <small style="color:var(--muted)">(scene ${i + 1})</small></span>
          <span style="color:var(--muted);font-size:.78rem" id="wc-${i}"></span>
        </label>
        <textarea id="edit-p-${i}" rows="4" style="width:100%;font-size:.92rem;line-height:1.5">${escHtml(p)}</textarea>
      `;
      wrap.appendChild(block);

      const ta = block.querySelector("textarea");
      const wc = block.querySelector(`#wc-${i}`);
      const update = () => {
        const words = ta.value.trim().split(/\s+/).filter(Boolean);
        const n = words.length;
        const secs = Math.round(n / 2.5);  // ~150 wpm = 2.5 words/sec
        const timeStr = secs < 60 ? `~${secs}s` : `~${Math.floor(secs/60)}m${secs%60}s`;
        wc.textContent = `${n} words · ${timeStr}`;
      };
      ta.addEventListener("input", update);
      update();
    });
    wrap.dataset.built = "1";
  }

  if (progCard) progCard.style.display = "none";
  editCard.style.display = "block";
}

async function resumeJob(paragraphs, force) {
  const r = await fetch("/job/" + currentJobId + "/resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paragraphs, force: !!force }),
  });
  return r.json();
}

const continueBtn = document.getElementById("continue-btn");
if (continueBtn) {
  const resetBtn = () => {
    continueBtn.disabled = false;
    continueBtn.textContent = "✅ Continue with Edited Script";
  };
  continueBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    const textareas = document.querySelectorAll("#edit-paragraphs textarea");
    const paragraphs = Array.from(textareas).map(t => t.value.trim()).filter(Boolean);
    if (paragraphs.length === 0) {
      alert("Need at least one paragraph to continue.");
      return;
    }
    continueBtn.disabled = true;
    continueBtn.textContent = "Resuming…";
    try {
      let d = await resumeJob(paragraphs, false);
      // Monetization-Safe Mode nudge: script wasn't edited.
      if (d.needs_confirmation) {
        resetBtn();
        if (!confirm(d.message + "\n\nContinue without editing?")) return;
        continueBtn.disabled = true;
        continueBtn.textContent = "Resuming…";
        d = await resumeJob(paragraphs, true);
      }
      if (d.error) throw new Error(d.error);
      // The SSE will pick up the running state and hide the edit panel.
    } catch (e) {
      showError("Resume failed: " + e.message);
      resetBtn();
    }
  });
}

const cancelEditBtn = document.getElementById("cancel-edit-btn");
if (cancelEditBtn) {
  cancelEditBtn.addEventListener("click", async () => {
    if (!currentJobId) return;
    if (!confirm("Cancel this video?")) return;
    try {
      await fetch("/job/" + currentJobId + "/cancel", { method: "POST" });
    } catch (_) {}
  });
}

function startSSE(jobId) {
  const formCard   = document.querySelector(".form-card");
  const progCard   = document.getElementById("progress-card");
  const resultCard = document.getElementById("result-card");

  if (formCard)   formCard.style.display   = "none";
  if (progCard)   progCard.style.display   = "block";
  if (resultCard) resultCard.style.display = "none";

  // Reset edit panel so a NEW job gets a fresh form
  const wrap = document.getElementById("edit-paragraphs");
  if (wrap) wrap.dataset.built = "0";

  currentJobId = jobId;
  jobIsRunning = true;

  if (evtSource) evtSource.close();
  evtSource = new EventSource("/progress/" + jobId);

  evtSource.onmessage = (e) => {
    const job = JSON.parse(e.data);
    currentJobId = jobId;

    setProgress(job.progress || 0, job.step || "");

    if (job.status === "paused_script") {
      showEditPanel(jobId, job.paragraphs || []);
    } else if (job.status === "running") {
      // Hide edit panel if it was open and pipeline has resumed
      const ec = document.getElementById("edit-card");
      if (ec) ec.style.display = "none";
      if (progCard) progCard.style.display = "block";
    }

    if (job.status === "done") {
      evtSource.close();
      jobIsRunning = false;
      clearJob();
      const ec = document.getElementById("edit-card");
      if (ec) ec.style.display = "none";
      showResult(job);
    } else if (job.status === "error" || job.status === "not_found" || job.status === "cancelled") {
      evtSource.close();
      jobIsRunning = false;
      clearJob();
      const ec = document.getElementById("edit-card");
      if (ec) ec.style.display = "none";
      if (formCard) formCard.style.display = "block";
      if (progCard) progCard.style.display = "none";
      if (job.status === "cancelled") {
        showError("Generation stopped.");
      } else {
        showError(job.error || "Job not found");
      }
      const btn = document.getElementById("generate-btn");
      if (btn) { btn.disabled = false; btn.textContent = "⚡ Generate Video"; }
    }
  };

  evtSource.onerror = () => {
    // Network blip — try one auto-reconnect after 2s; only give up on second failure
    evtSource.close();
    setTimeout(() => {
      if (!jobIsRunning) return;
      const retry = new EventSource("/progress/" + jobId);
      retry.onmessage = evtSource && evtSource.onmessage ? evtSource.onmessage : null;
      evtSource = retry;
      retry.onerror = () => {
        retry.close();
        jobIsRunning = false;
        if (formCard) formCard.style.display = "block";
        if (progCard) progCard.style.display = "none";
        showError("Connection to server lost. Refresh to reconnect — the video may still be processing.");
        const btn = document.getElementById("generate-btn");
        if (btn) { btn.disabled = false; btn.textContent = "⚡ Generate Video"; }
      };
    }, 2000);
  };
}

function setProgress(pct, label) {
  const fill  = document.getElementById("progress-fill");
  const step  = document.getElementById("step-label");
  const pctEl = document.getElementById("pct-label");
  if (fill)  fill.style.width  = pct + "%";
  if (step)  step.textContent  = label;
  if (pctEl) pctEl.textContent = pct + "%";
}

/* ── Show result ──────────────────────────────────── */
function showResult(job) {
  const progCard   = document.getElementById("progress-card");
  const resultCard = document.getElementById("result-card");
  if (progCard)   progCard.style.display   = "none";
  if (resultCard) resultCard.style.display = "block";

  const video = document.getElementById("result-video");
  if (video && job.video_url) {
    video.src = job.video_url;
    video.load();
  }

  const metaTitle = document.getElementById("meta-title");
  if (metaTitle) metaTitle.textContent = job.title || "";

  const copyTitle = document.getElementById("copy-title");
  if (copyTitle) copyTitle.value = job.title || "";

  const copyTags = document.getElementById("copy-tags");
  if (copyTags) copyTags.value = (job.tags || []).join(", ");

  const copyDesc = document.getElementById("copy-desc");
  if (copyDesc) copyDesc.value = job.description || "";

  const dl = document.getElementById("download-btn");
  if (dl && job.video_url) dl.href = job.video_url;

  const openFolder = document.getElementById("open-folder-btn");
  if (openFolder && job.folder_name) {
    openFolder.onclick = () => fetch("/open_folder/" + job.folder_name);
  }

  // AI-disclosure note — only show when this video's visuals are realistic.
  const discNote = document.getElementById("disclosure-note");
  if (discNote) {
    if (job.requires_ai_disclosure === false) {
      discNote.style.display = "none";
    } else {
      discNote.style.display = "";
      discNote.innerHTML = "⚠️ Realistic visuals — set <strong>“Altered or synthetic "
        + "content”</strong> to YES in YouTube Studio before publishing.";
    }
  }

  // Pre-publish compliance checklist (populates #compliance-panel).
  if (job.folder_name) loadCompliance(job.folder_name);

  const ytBtn = document.getElementById("yt-upload-btn");
  if (ytBtn && job.folder_name) {
    const folder = job.folder_name;
    ytBtn.dataset.folder = folder;

    async function doUpload(force) {
      ytBtn.disabled = true;
      ytBtn.textContent = "Uploading…";
      try {
        const r = await fetch("/upload_youtube/" + folder, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: !!force }),
        });
        const d = await r.json();

        // Compliance gate blocked the upload — show issues and offer override.
        if (d.needs_force) {
          if (d.compliance) renderCompliance(d.compliance);
          const crit = ((d.compliance && d.compliance.checks) || [])
            .filter(c => c.severity === "critical" && !c.pass)
            .map(c => "• " + c.label + " — " + c.detail).join("\n");
          ytBtn.disabled = false;
          ytBtn.textContent = "▶ Upload to YouTube (Private Draft)";
          if (confirm("This video failed monetization checks:\n\n" + crit
              + "\n\nUpload anyway as a Private draft?")) {
            return doUpload(true);
          }
          return;
        }

        if (d.error) throw new Error(d.error);
        ytBtn.textContent = "✓ Uploaded — view in YouTube Studio";
        ytBtn.style.color = "#22c55e";
        ytBtn.style.borderColor = "#22c55e";
        // Surface the Studio AI-disclosure reminder when one was returned.
        if (d.disclosure_reminder) {
          const discNote = document.getElementById("disclosure-note");
          if (discNote) { discNote.style.display = ""; discNote.textContent = d.disclosure_reminder; }
        }
        if (d.url) {
          ytBtn.onclick = () => window.open(d.url, "_blank");
          ytBtn.disabled = false;
        }
      } catch (e) {
        ytBtn.disabled = false;
        ytBtn.textContent = "▶ Upload to YouTube (Private Draft)";
        showError("YouTube upload failed: " + e.message);
      }
    }

    ytBtn.onclick = () => {
      if (!confirm("Upload this video to YouTube as a Private draft?")) return;
      doUpload(false);
    };
  }
}

/* ── Pre-publish compliance gate ──────────────────── */
function renderCompliance(report) {
  const panel = document.getElementById("compliance-panel");
  const list  = document.getElementById("compliance-list");
  const score = document.getElementById("compliance-score");
  if (!panel || !list || !report || !report.checks) return;

  panel.style.display = "block";
  panel.classList.toggle("has-critical", report.critical_failed > 0);
  if (score) {
    score.textContent = report.passed + "/" + report.total + " passed";
    score.className = "compliance-score " + (report.critical_failed > 0 ? "bad" : "good");
  }
  list.innerHTML = report.checks.map(c => {
    const icon = c.pass ? "✓" : (c.severity === "critical" ? "✕" : "⚠");
    const cls  = c.pass ? "ok" : (c.severity === "critical" ? "crit" : "warn");
    return `<li class="cc-${cls}"><span class="cc-icon">${icon}</span>`
         + `<span class="cc-body"><strong>${escHtml(c.label)}</strong>`
         + `<small>${escHtml(c.detail || "")}</small></span></li>`;
  }).join("");
}

async function loadCompliance(folder) {
  try {
    const r = await fetch("/compliance/" + folder);
    const report = await r.json();
    if (report && report.checks) renderCompliance(report);
    return report;
  } catch (_) { return null; }
}

/* ── Copy helpers ─────────────────────────────────── */
function copyField(id) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.value).then(() => {
    showToast("Copied!");
  }).catch(() => {
    el.select();
    document.execCommand("copy");
    showToast("Copied!");
  });
}

function showToast(msg) {
  let t = document.getElementById("copy-toast");
  if (!t) {
    t = document.createElement("div");
    t.id = "copy-toast";
    t.style.cssText = "position:fixed;bottom:24px;right:24px;background:var(--red);" +
      "color:#fff;padding:10px 20px;border-radius:6px;font-size:.9rem;" +
      "opacity:0;transition:opacity .3s;pointer-events:none;z-index:999";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.opacity = "1";
  setTimeout(() => t.style.opacity = "0", 1800);
}

/* ── Error helpers ────────────────────────────────── */
function showError(msg) {
  const el = document.getElementById("error-msg");
  if (!el) return;
  el.textContent = msg;
  el.style.display = "block";
}

function hideError() {
  const el = document.getElementById("error-msg");
  if (el) el.style.display = "none";
}

/* ── HTML escape helpers ──────────────────────────── */
function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escAttr(s) {
  return String(s).replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}
