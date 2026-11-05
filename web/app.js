"use strict";
const $ = (id) => document.getElementById(id);
let token = "", currentVideo = null, jobs = [], connected = false, polling = false, inspecting = false;
let catalog = [], mode = "video", batches = [], scope = "single", batchSubmitting = false;
const activeStates = new Set(["queued", "downloading", "processing"]);
const icons = (name) => { const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); const use = document.createElementNS(svg.namespaceURI, "use"); use.setAttribute("href", `#i-${name}`); svg.append(use); return svg; };
const text = (tag, className, content) => { const el = document.createElement(tag); el.className = className; el.textContent = content; return el; };
function message(id, value) { $(id).textContent = value; $(id).hidden = !value; }
function toast(value) { message("toast", value); clearTimeout(toast.timer); toast.timer = setTimeout(() => message("toast", ""), 4500); }
function duration(seconds) { if (!Number.isFinite(seconds)) return ""; const h = Math.floor(seconds / 3600), m = Math.floor(seconds / 60) % 60, s = Math.floor(seconds % 60); return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`; }
function bytes(value) { if (!value) return ""; if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`; if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`; return `${Math.max(1, Math.round(value / 1024))} KB`; }
async function api(path, data, timeout = 100000) {
  const response = await fetch(path, { method: data ? "POST" : "GET", headers: data ? { "Content-Type": "application/json", "X-Frame-Token": token } : {}, body: data ? JSON.stringify(data) : undefined, signal: AbortSignal.timeout(timeout), cache: "no-store" });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Die Anfrage konnte nicht abgeschlossen werden.");
  return result;
}
function niceError(error) { return error.name === "TimeoutError" ? "Die Anfrage dauert zu lange. Bitte versuche es erneut." : error instanceof TypeError ? "Frame ist gerade nicht erreichbar. Prüfe, ob das Startfenster noch geöffnet ist." : error.message; }
function setConnection(online) {
  connected = online;
  $("connection-button").classList.toggle("offline", !online);
  $("connection-label").textContent = online ? "Lokal verbunden" : "Verbindung unterbrochen";
  updateAvailability();
}
function updateAvailability() {
  $("batch-options").disabled = !connected || batchSubmitting;
  $("download-options").disabled = !connected || !currentVideo || inspecting || (mode === "audio" && currentVideo.has_audio === false);
}
function renderOptions(resetQuality = false) {
  const formatSelect = $("format-select"), oldFormat = formatSelect.value, oldQuality = $("quality-select").value;
  const formats = catalog.filter(item => item.kind === mode);
  formatSelect.replaceChildren();
  for (const item of formats) {
    const option = new Option(item.label, item.id);
    if (item.id === "webm" && currentVideo && !currentVideo.webm_heights?.length) option.disabled = true;
    formatSelect.append(option);
  }
  if (formats.some(item => item.id === oldFormat) && ![...formatSelect.options].find(item => item.value === oldFormat)?.disabled) formatSelect.value = oldFormat;
  const selected = catalog.find(item => item.id === formatSelect.value);
  if (!selected) return;
  const qualitySelect = $("quality-select"); qualitySelect.replaceChildren();
  $("quality-label").textContent = mode === "audio" ? "Audioqualität" : "Videoqualität";
  if (mode === "video") {
    const heights = selected.id === "webm" ? currentVideo?.webm_heights : currentVideo?.heights;
    const maximum = heights?.[0];
    qualitySelect.append(new Option(maximum ? `Beste · ${maximum}p${maximum === 2160 ? " / 4K" : maximum >= 4320 ? " / 8K" : ""}` : "Beste verfügbar", "best"));
    for (const h of heights || []) qualitySelect.append(new Option(`${h}p${h === 2160 ? " · 4K" : h === 1080 ? " · Full HD" : h === 720 ? " · HD" : ""}`, String(h)));
    $("quality-hint").textContent = "Original-Bildqualität. Ohne Hochskalieren oder erneute Videokodierung.";
  } else {
    for (const quality of selected.qualities) qualitySelect.append(new Option(quality === "best" ? (["wav", "flac"].includes(selected.id) ? "Quellqualität" : "Beste Quellspur") : `${quality} kbit/s${quality === "320" ? " · Hoch" : ""}`, quality));
    $("quality-hint").textContent = ["wav", "flac"].includes(selected.id) ? "Größere Datei, gleiche Quelle: WAV und FLAC verbessern komprimierten YouTube-Ton nicht." : selected.id === "mp3" ? "Die Bitrate ist das Ausgabeziel. Die Tonqualität hängt immer von der Quelle ab." : "Passende Originalspur bevorzugt. Nur bei Bedarf wird das Audio konvertiert.";
  }
  if (!resetQuality && [...qualitySelect.options].some(option => option.value === oldQuality)) qualitySelect.value = oldQuality;
  $("format-description").textContent = selected.description;
  $("download-button").querySelector("span").textContent = `${selected.id.toUpperCase()} herunterladen`;
  updateAvailability();
}
function setMode(value) {
  mode = value;
  for (const name of ["video", "audio"]) { $("mode-" + name).classList.toggle("active", name === value); $("mode-" + name).setAttribute("aria-pressed", String(name === value)); }
  message("download-error", currentVideo?.has_audio === false && mode === "audio" ? "Für dieses Video ist keine Audiospur verfügbar." : "");
  renderOptions(true);
}
async function health() {
  try {
    const state = await api("/api/health", null, 5000); token = state.token;
    catalog = state.formats || [];
    setConnection(state.ready);
    $("connection-label").textContent = state.ready ? "Lokal verbunden" : "Einrichtung erforderlich";
    message("service-notice", state.ready ? "" : state.setup?.error || state.setup?.message || "Die Download-Werkzeuge sind noch nicht vollständig eingerichtet. Bitte starte Frame mit Start.command.");
    const info = $("system-info"); info.replaceChildren();
    info.append(text("strong", "", "Dein lokales System"), document.createElement("br"));
    info.append(document.createTextNode(`yt-dlp ${state.yt_dlp || "fehlt"} · FFmpeg ${state.ffmpeg ? "bereit" : "fehlt"} · ${state.javascript || "JavaScript-Laufzeit fehlt"}`), document.createElement("br"));
    info.append(document.createTextNode(`Download-Ordner: ${state.download_folder}`));
    renderOptions(); renderBatchOptions();
    return state.ready;
  } catch (error) {
    setConnection(false); message("service-notice", niceError(error));
    $("system-info").textContent = "Der lokale Dienst ist nicht erreichbar. Bitte starte Start.command.";
    return false;
  }
}
function showView(name) {
  $("studio-view").hidden = name !== "studio"; $("downloads-view").hidden = name !== "downloads";
  for (const section of ["studio", "downloads"]) { $("nav-" + section).classList.toggle("active", section === name); if (section === name) $("nav-" + section).setAttribute("aria-current", "page"); else $("nav-" + section).removeAttribute("aria-current"); }
  $("breadcrumb-current").textContent = name === "studio" ? "Downloader" : "Meine Downloads";
  if (name === "downloads") renderJobs();
  window.scrollTo({ top: 0, behavior: "auto" });
}
function showVideo(video) {
  currentVideo = video;
  $("preview-art").hidden = true; $("thumbnail-wrap").hidden = false;
  $("thumbnail").src = video.thumbnail; $("thumbnail").alt = `Vorschaubild: ${video.title}`;
  $("duration").textContent = duration(video.duration); $("duration").hidden = !video.duration;
  $("youtube-link").href = video.url;
  $("video-eyebrow").textContent = "DEIN VIDEO IST BEREIT";
  $("video-title").textContent = video.title; $("video-meta").textContent = `${video.channel}${video.duration ? ` · ${duration(video.duration)}` : ""} · bis zu ${video.max_height}p`;
  renderOptions(true);
}
$("video-url").addEventListener("input", () => { currentVideo = null; $("download-options").disabled = true; message("link-error", ""); });
$("link-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (inspecting) return;
  message("link-error", ""); message("download-error", "");
  if (!connected && !(await health())) return;
  inspecting = true; $("inspect-button").disabled = true; $("inspect-button").querySelector("span").textContent = "Video wird geprüft …"; $("download-options").disabled = true; $("video-url").readOnly = true;
  try { const video = await api("/api/inspect", { url: $("video-url").value.trim() }); showVideo(video); }
  catch (error) { message("link-error", niceError(error)); }
  finally { inspecting = false; $("inspect-button").disabled = false; $("inspect-button").querySelector("span").textContent = "Link prüfen"; $("video-url").readOnly = false; updateAvailability(); }
});
$("paste-button").addEventListener("click", async () => {
  try { const value = await navigator.clipboard.readText(); $("video-url").value = value.trim(); $("video-url").dispatchEvent(new Event("input")); $("video-url").focus(); }
  catch { $("video-url").focus(); toast("Bitte füge den Link mit ⌘V oder Strg+V ein."); }
});
$("download-button").addEventListener("click", async () => {
  if (!currentVideo || !connected) return;
  const video = currentVideo, button = $("download-button"); button.disabled = true; message("download-error", "");
  try {
    const job = await api("/api/jobs", { url: video.url, title: video.title, mode, quality: mode === "video" ? $("quality-select").value : "best", audio_quality: mode === "audio" ? $("quality-select").value : "best", container: $("format-select").value });
    jobs.unshift(job); renderJobs(); toast("Dein Download wurde gestartet."); $("recent-jobs").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) { message("download-error", niceError(error)); }
  finally { button.disabled = false; }
});
function emptyState() {
  const box = text("div", "empty-jobs", ""), icon = text("span", "empty-icon", ""), copy = document.createElement("div");
  icon.append(icons("download")); copy.append(text("strong", "", "Deine Sammlung beginnt hier."), text("p", "", "Sobald du ein Video herunterlädst, findest du es an dieser Stelle."));
  box.append(icon, copy, text("span", "empty-dots", "···")); return box;
}
function jobCard(job) {
  const row = text("article", "job-card", ""), icon = text("div", `job-icon ${job.state}`, ""), body = text("div", "job-body", ""), actions = text("div", "job-actions", "");
  icon.append(icons(job.state === "done" ? "check" : job.state === "error" || job.state === "cancelled" ? "close" : "download"));
  body.append(text("h3", "job-title", job.title || "YouTube-Video"));
  const audio = job.mode === "audio" || ["mp3", "m4a", "opus", "wav", "flac"].includes(job.container);
  const quality = audio ? (job.audio_quality && job.audio_quality !== "best" ? `Ziel: ${job.audio_quality} kbit/s` : "Beste Quellspur") : job.height ? `${job.height}p` : job.quality === "best" ? "Beste Qualität" : `bis ${job.quality}p`;
  const meta = [job.container.toUpperCase(), quality];
  if (job.state === "done") meta.push(bytes(job.size), "Abgeschlossen");
  else if (job.state === "cancelled") meta.push("Abgebrochen");
  else if (job.state === "error") meta.push("Fehlgeschlagen");
  else { meta.push(job.stage || "In der Warteschlange"); if (job.progress != null && job.state === "downloading") meta.push(`${Math.round(job.progress)} %`); if (job.speed && job.state === "downloading") meta.push(`${bytes(job.speed)}/s`); if (job.eta != null && job.state === "downloading") meta.push(`ca. ${duration(job.eta)}`); }
  body.append(text("div", "job-meta", meta.filter(Boolean).join(" · ")));
  if (job.error && job.state === "error") body.append(text("div", "job-meta job-error", job.error));
  if (activeStates.has(job.state)) { const progress = document.createElement("progress"); progress.className = "job-progress"; progress.max = 100; progress.setAttribute("aria-label", job.stage || "Download läuft"); if (job.progress != null && job.state === "downloading") progress.value = job.progress; body.append(progress); }
  if (job.state === "done") { const save = document.createElement("a"); save.className = "job-button"; save.href = `/api/files/${job.id}`; save.download = ""; save.append(icons("download"), document.createTextNode("Datei speichern")); actions.append(save); }
  else if (activeStates.has(job.state)) {
    const cancel = text("button", "job-button cancel", "Abbrechen"); cancel.addEventListener("click", async () => { cancel.disabled = true; try { await api(`/api/jobs/${job.id}/cancel`, {}); await refreshJobs(); } catch (error) { toast(niceError(error)); cancel.disabled = false; } }); actions.append(cancel);
  } else if (!job.batch_id) {
    const retry = text("button", "job-button", "Erneut versuchen"); retry.addEventListener("click", async () => { retry.disabled = true; try { await api("/api/jobs", { url: job.url, quality: job.quality, audio_quality: job.audio_quality || "best", mode: job.mode || "video", container: job.container, title: job.title }); await refreshJobs(); } catch (error) { toast(niceError(error)); retry.disabled = false; } }); actions.append(retry);
  }
  if (!activeStates.has(job.state) && !job.batch_id) {
    const remove = text("button", "job-button cancel", ""); remove.append(icons("close")); remove.title = "Aus Verlauf entfernen (Datei bleibt erhalten)"; remove.setAttribute("aria-label", `Aus Verlauf entfernen: ${job.title}`);
    remove.addEventListener("click", async () => { remove.disabled = true; try { await api(`/api/jobs/${job.id}/remove`, {}); await refreshJobs(); toast("Aus dem Verlauf entfernt. Deine Datei bleibt erhalten."); } catch (error) { toast(niceError(error)); remove.disabled = false; } }); actions.append(remove);
  }
  row.append(icon, body, actions); return row;
}
function replaceJobList(id, list) {
  const container = $(id), previousFocus = document.activeElement, oldRows = [...container.children], focusedRow = previousFocus?.closest(".job-card");
  const focusedIndex = focusedRow ? oldRows.indexOf(focusedRow) : -1;
  container.replaceChildren(...(list.length ? list.map(jobCard) : [emptyState()]));
  if (focusedIndex >= 0 && focusedIndex < container.children.length) { const action = container.children[focusedIndex].querySelector("button,a"); if (action) action.focus({ preventScroll: true }); }
}
function renderJobs() {
  $("download-count").textContent = jobs.length;
  const singles = jobs.filter(j => !j.batch_id);
  $("recent-count").textContent = singles.length ? `(${singles.length})` : "";
  $("recent-single-section").hidden = !singles.length && !!batches.length;
  $("all-jobs").hidden = !singles.length && !!batches.length;
  replaceJobList("recent-jobs", jobs.filter(j => !j.batch_id).slice(0, 3)); replaceJobList("all-jobs", jobs.filter(j => !j.batch_id));
  renderBatches();
  const done = jobs.filter(j => j.state === "done").length, running = jobs.filter(j => activeStates.has(j.state)).length;
  $("download-summary").textContent = `${jobs.length} Downloads · ${done} abgeschlossen${running ? ` · ${running} aktiv` : ""}`;
}
async function refreshJobs() {
  if (polling) return; polling = true;
  try {
    const [next, nextBatches] = await Promise.all([api("/api/jobs", null, 5000), api("/api/batches", null, 5000)]);
    if (JSON.stringify(next) !== JSON.stringify(jobs) || JSON.stringify(nextBatches) !== JSON.stringify(batches)) { jobs = next; batches = nextBatches; renderJobs(); }
    if (!connected) await health();
  }
  catch { if (connected) { setConnection(false); message("service-notice", "Die Verbindung zu Frame wurde unterbrochen. Bitte prüfe, ob das Startfenster noch geöffnet ist."); } }
  finally { polling = false; }
}
$("nav-studio").addEventListener("click", () => showView("studio")); $("nav-downloads").addEventListener("click", () => showView("downloads")); $("show-all").addEventListener("click", () => showView("downloads"));
$("mode-video").addEventListener("click", () => setMode("video")); $("mode-audio").addEventListener("click", () => setMode("audio")); $("format-select").addEventListener("change", () => renderOptions(true));
function openHelp() { health(); $("help-dialog").showModal(); }
$("help-button").addEventListener("click", openHelp); $("connection-button").addEventListener("click", openHelp); $("close-help").addEventListener("click", () => $("help-dialog").close());
$("help-dialog").addEventListener("click", event => { if (event.target === $("help-dialog")) { const bounds = event.target.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) event.target.close(); } });
$("thumbnail").addEventListener("error", () => { $("thumbnail-wrap").hidden = true; $("preview-art").hidden = false; });


function setScope(value) {
  scope = value;
  $("single-download").hidden = value !== "single";
  $("batch-download").hidden = value !== "batch";
  for (const name of ["single", "batch"]) { $("scope-" + name).classList.toggle("active", value === name); $("scope-" + name).setAttribute("aria-pressed", String(value === name)); }
  $("recent-batches-section").hidden = !batches.length;
}
function batchLines() { return $("batch-urls").value.split(/\r?\n/).map(s => s.trim()).filter(Boolean); }
function updateBatchCount() { const count = batchLines().length; $("batch-count").textContent = `${count} ${count === 1 ? "Link" : "Links"} eingefügt · maximal 100`; }
function renderBatchOptions(reset = false) {
  const format = $("batch-format"), previousFormat = format.value, quality = $("batch-quality"), previousQuality = quality.value;
  format.replaceChildren(...catalog.map(item => new Option(`${item.label} · ${item.kind === "video" ? "Video" : "Audio"}`, item.id)));
  if (catalog.some(item => item.id === previousFormat)) format.value = previousFormat;
  const selected = catalog.find(item => item.id === format.value);
  if (!selected) return;
  quality.replaceChildren();
  $("batch-quality-label").textContent = selected.kind === "video" ? "Videoqualität für alle" : "Audioqualität für alle";
  if (selected.kind === "video") {
    quality.append(new Option("Beste je Video", "best"));
    for (const h of [4320,2160,1440,1080,720,480,360,240,144]) quality.append(new Option(`Bis ${h}p${h === 2160 ? " · 4K" : h === 1080 ? " · Full HD" : ""}`, String(h)));
    $("batch-quality-hint").textContent = "Die Auflösung gilt als Obergrenze für alle Videos. Bei geringerer Quellqualität wird die beste passende Spur geladen. Kein Hochskalieren.";
  } else {
    for (const q of selected.qualities) quality.append(new Option(q === "best" ? "Beste Quellqualität" : `${q} kbit/s`, q));
    $("batch-quality-hint").textContent = selected.id === "mp3" ? "Die gewählte Bitrate gilt als Ausgabeziel für alle Dateien. Die Quelle bestimmt die Tonqualität." : selected.description + ". Die Qualität der Quelle wird nicht verbessert.";
  }
  if (!reset && [...quality.options].some(item => item.value === previousQuality)) quality.value = previousQuality;
  updateAvailability();
}
function packageCard(batch) {
  const card = text("article", "batch-card", ""), audio = batch.mode === "audio";
  const quality = audio ? (batch.audio_quality === "best" ? "Quellqualität" : `${batch.audio_quality} kbit/s`) : batch.quality === "best" ? "Beste je Video" : `bis ${batch.quality}p`;
  card.append(text("h3", "", `Paket · ${batch.total} ${batch.total === 1 ? "Datei" : "Dateien"}`));
  card.append(text("div", "job-meta", `${batch.container.toUpperCase()} · ${quality} · ${new Date(batch.created * 1000).toLocaleString("de-DE")} · ${batch.delivery === "zip" ? "ZIP-Paket" : "Einzeldateien"}`));
  const settled = batch.done + batch.error + batch.cancelled;
  const status = `${batch.done} von ${batch.total} fertig${batch.active ? ` · ${batch.active} in Arbeit / Warteschlange` : ""}${batch.error ? ` · ${batch.error} fehlgeschlagen` : ""}${batch.cancelled ? ` · ${batch.cancelled} abgebrochen` : ""}`;
  card.append(text("p", "batch-status", status));
  const progress = document.createElement("progress"); progress.className = "job-progress"; progress.max = batch.total; progress.value = settled; progress.setAttribute("aria-label", status); card.append(progress);
  const actions = text("div", "job-actions", "");
  if (batch.zip_ready) {
    const zip = text("a", "job-button", batch.error || batch.cancelled ? `ZIP mit ${batch.done} ${batch.done === 1 ? "fertiger Datei" : "fertigen Dateien"} speichern` : batch.delivery === "zip" ? "ZIP-Paket speichern" : "Optional als ZIP speichern");
    zip.href = `/api/batches/${batch.id}/zip`; zip.download = "";
    zip.addEventListener("click", () => toast("Das ZIP wird vorbereitet. Bei großen Paketen kann das etwas dauern.")); actions.append(zip);
  }
  function action(label, operation, className = "") {
    const button = text("button", `job-button ${className}`, label);
    button.addEventListener("click", async () => { button.disabled = true; try { await api(`/api/batches/${batch.id}/${operation}`, {}); await refreshJobs(); if (operation === "remove") toast("Paket aus dem Verlauf entfernt. Deine Dateien bleiben erhalten."); } catch (error) { toast(niceError(error)); button.disabled = false; } });
    actions.append(button);
  }
  if (batch.active) action("Paket abbrechen", "cancel", "cancel");
  else { if (batch.error || batch.cancelled) action("Fehlende erneut laden", "retry"); action("Aus Verlauf entfernen", "remove", "cancel"); }
  card.append(actions);
  if (!batch.active && (batch.error || batch.cancelled)) card.append(text("p", "format-description", "Das ZIP enthält nur fertige Dateien. Paket-Info.json führt alle Ergebnisse auf."));
  const details = document.createElement("details"); details.dataset.batch = batch.id;
  details.append(text("summary", "", "Einzeldateien & Fortschritt anzeigen"));
  const list = text("div", "jobs-list", "");
  const byId = new Map(jobs.map(job => [job.id, job]));
  for (const key of batch.jobs) { const job = byId.get(key); if (job) list.append(jobCard(job)); }
  details.append(list); card.append(details); return card;
}
function renderBatches() {
  $("recent-batches-section").hidden = !batches.length;
  for (const id of ["recent-batches", "all-batches"]) {
    const container = $(id), expanded = new Map([...container.querySelectorAll("details")].map(el => [el.dataset.batch, el.open]));
    const focus = document.activeElement, focused = container.contains(focus) ? focus : null;
    const focusBatch = focused?.closest(".batch-card")?.querySelector("details")?.dataset.batch;
    const focusIndex = focused ? [...focused.closest(".batch-card").querySelectorAll("button,a,summary")].indexOf(focused) : -1;
    container.replaceChildren(...batches.map(packageCard));
    for (const detail of container.querySelectorAll("details")) {
      detail.open = expanded.has(detail.dataset.batch) ? expanded.get(detail.dataset.batch) : batches.find(b => b.id === detail.dataset.batch)?.delivery === "files";
      if (detail.dataset.batch === focusBatch && focusIndex >= 0) detail.closest(".batch-card").querySelectorAll("button,a,summary")[focusIndex]?.focus({preventScroll:true});
    }
  }
}
$("scope-single").addEventListener("click", () => setScope("single"));
$("scope-batch").addEventListener("click", () => setScope("batch"));
$("batch-urls").addEventListener("input", () => { updateBatchCount(); message("batch-error", ""); });
$("batch-format").addEventListener("change", () => renderBatchOptions(true));
$("batch-paste").addEventListener("click", async () => { try { const value = await navigator.clipboard.readText(); $("batch-urls").value = [$("batch-urls").value.trim(), value.trim()].filter(Boolean).join("\n"); updateBatchCount(); } catch { toast("Bitte füge die Links mit ⌘V oder Strg+V ein."); } $("batch-urls").focus(); });
$("batch-form").addEventListener("submit", async event => {
  event.preventDefault(); if (batchSubmitting) return;
  message("batch-error", "");
  const urls = batchLines();
  if (!urls.length || urls.length > 100) { message("batch-error", "Bitte füge 1 bis 100 Links ein, einen pro Zeile."); return; }
  if (!connected && !(await health())) return;
  const selected = catalog.find(item => item.id === $("batch-format").value);
  const payload = { urls, container: selected.id, mode: selected.kind, quality: selected.kind === "video" ? $("batch-quality").value : "best", audio_quality: selected.kind === "audio" ? $("batch-quality").value : "best", delivery: $("batch-delivery").value };
  batchSubmitting = true; updateAvailability();
  $("batch-start").querySelector("span").textContent = "Paket wird angelegt …";
  try {
    const batch = await api("/api/batches", payload);
    batches.unshift(batch); renderBatches(); await refreshJobs();
    $("batch-urls").value = ""; updateBatchCount();
    toast(`${batch.total} Downloads vorgemerkt.${batch.duplicates ? ` ${batch.duplicates} doppelte Links übersprungen.` : ""}`);
    $("recent-batches-section").scrollIntoView({behavior:"smooth", block:"start"});
  } catch (error) { message("batch-error", niceError(error)); }
  finally { batchSubmitting = false; updateAvailability(); $("batch-start").querySelector("span").textContent = "Paket herunterladen"; }
});
renderJobs(); health().then(refreshJobs); setInterval(refreshJobs, 1500);

$("stop-service").addEventListener("click", async () => {
  try { await api("/api/shutdown", {}); $("help-dialog").close(); setConnection(false); toast("Frame ist beendet. Zum Starten die Frame-App erneut öffnen."); }
  catch (error) { toast(niceError(error)); }
});
