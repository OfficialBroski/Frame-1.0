"use strict";
const $ = (id) => document.getElementById(id);
let token = "", currentVideo = null, jobs = [], connected = false, polling = false, inspecting = false;
let catalog = [], mode = "video";
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
    message("service-notice", state.ready ? "" : "Die Download-Werkzeuge sind noch nicht vollständig eingerichtet. Bitte starte Frame mit Start.command.");
    const info = $("system-info"); info.replaceChildren();
    info.append(text("strong", "", "Dein lokales System"), document.createElement("br"));
    info.append(document.createTextNode(`yt-dlp ${state.yt_dlp || "fehlt"} · FFmpeg ${state.ffmpeg ? "bereit" : "fehlt"} · ${state.javascript || "JavaScript-Laufzeit fehlt"}`), document.createElement("br"));
    info.append(document.createTextNode(`Download-Ordner: ${state.download_folder}`));
    renderOptions();
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
  } else {
    const retry = text("button", "job-button", "Erneut versuchen"); retry.addEventListener("click", async () => { retry.disabled = true; try { await api("/api/jobs", { url: job.url, quality: job.quality, audio_quality: job.audio_quality || "best", mode: job.mode || "video", container: job.container, title: job.title }); await refreshJobs(); } catch (error) { toast(niceError(error)); retry.disabled = false; } }); actions.append(retry);
  }
  if (!activeStates.has(job.state)) {
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
  $("recent-count").textContent = jobs.length ? `(${jobs.length})` : "";
  replaceJobList("recent-jobs", jobs.slice(0, 3)); replaceJobList("all-jobs", jobs);
  const done = jobs.filter(j => j.state === "done").length, running = jobs.filter(j => activeStates.has(j.state)).length;
  $("download-summary").textContent = `${jobs.length} Downloads · ${done} abgeschlossen${running ? ` · ${running} aktiv` : ""}`;
}
async function refreshJobs() {
  if (polling) return; polling = true;
  try { const next = await api("/api/jobs", null, 5000); if (JSON.stringify(next) !== JSON.stringify(jobs)) { jobs = next; renderJobs(); } if (!connected) await health(); }
  catch { if (connected) { setConnection(false); message("service-notice", "Die Verbindung zu Frame wurde unterbrochen. Bitte prüfe, ob das Startfenster noch geöffnet ist."); } }
  finally { polling = false; }
}
$("nav-studio").addEventListener("click", () => showView("studio")); $("nav-downloads").addEventListener("click", () => showView("downloads")); $("show-all").addEventListener("click", () => showView("downloads"));
$("mode-video").addEventListener("click", () => setMode("video")); $("mode-audio").addEventListener("click", () => setMode("audio")); $("format-select").addEventListener("change", () => renderOptions(true));
function openHelp() { health(); $("help-dialog").showModal(); }
$("help-button").addEventListener("click", openHelp); $("connection-button").addEventListener("click", openHelp); $("close-help").addEventListener("click", () => $("help-dialog").close());
$("help-dialog").addEventListener("click", event => { if (event.target === $("help-dialog")) { const bounds = event.target.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) event.target.close(); } });
$("thumbnail").addEventListener("error", () => { $("thumbnail-wrap").hidden = true; $("preview-art").hidden = false; });
renderJobs(); health().then(refreshJobs); setInterval(refreshJobs, 1500);
