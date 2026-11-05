#!/usr/bin/env python3
"""Frame: local-only YouTube download service and web UI (Python 3.11+)."""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import importlib.metadata
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import tempfile
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse
import uuid
import webbrowser
from functools import lru_cache
from formats import FORMATS, VERSION, download_options, validate_options

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("FRAME_DATA_DIR", str(ROOT / "downloads"))).resolve()
JOBS: dict = {}
BATCHES: dict = {}
MAX_BATCH = 100
MAX_QUEUED = 200
ZIP_SLOT = threading.BoundedSemaphore(1)
PROCESSES: dict = {}
LOCK = threading.RLock()
TOKEN = secrets.token_urlsafe(32)
SETUP = {"message": "", "error": ""}
POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2)
PORT = 8765
INSPECT_SLOTS = threading.BoundedSemaphore(2)


def youtube_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Bitte füge einen gültigen YouTube-Link ein.")
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        raise ValueError("Bitte füge einen vollständigen YouTube-Link mit https:// ein.")
    host = (parsed.hostname or "").lower()
    if parsed.port not in (None, 80, 443):
        raise ValueError("Dieser YouTube-Link wird nicht unterstützt.")
    if host == "youtu.be":
        video_id = parsed.path.strip("/")
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = parsed.path.strip("/").split("/")
            video_id = parts[1] if len(parts) == 2 and parts[0] in ("shorts", "live", "embed") else ""
    else:
        raise ValueError("Hier funktionieren ausschließlich Links zu YouTube-Videos.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("Der Link enthält keine gültige Video-ID. Bitte prüfe ihn noch einmal.")
    return "https://www.youtube.com/watch?v=" + video_id


def supported_runtime(name, path):
    try:
        output = subprocess.check_output([path, "--version"], text=True, timeout=5)
        match = re.search(r"(?:v|deno\s+)(\d+)\.(\d+)", output)
        return bool(match and tuple(map(int, match.groups())) >= ((22, 0) if name == "node" else (2, 3)))
    except (OSError, subprocess.SubprocessError):
        return False


@lru_cache(maxsize=1)
def runtime_path():
    try:
        local = json.loads((ROOT / "frame.local.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        local = {}
    configured = os.environ.get("FRAME_JS_RUNTIME") or local.get("javascript_runtime", "")
    if configured:
        name, separator, path = configured.partition(":")
        if separator and name in ("deno", "node") and Path(path).is_file() and supported_runtime(name, path):
            return name, path
    for name in ("deno", "node"):
        for path in (str(ROOT / ".runtime" / name / "bin" / name), shutil.which(name),
                     f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", str(Path.home() / ".deno/bin" / name)):
            if path and Path(path).is_file() and supported_runtime(name, path):
                return name, path
    return None, None


def ffmpeg_path():
    configured = os.environ.get("FRAME_FFMPEG")
    if configured and Path(configured).is_file():
        return configured
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError):
        return None


def dependencies():
    try:
        version = importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        version = None
    js_name, _ = runtime_path()
    ffmpeg = ffmpeg_path()
    return {"ready": bool(version and ffmpeg and js_name), "version": VERSION, "formats": FORMATS, "yt_dlp": version,
            "ffmpeg": bool(ffmpeg), "javascript": js_name, "download_folder": str(DATA), "setup": dict(SETUP)}


def worker_command(mode):
    if getattr(sys, "frozen", False):
        return [sys.executable, "--frame-worker" if mode == "--worker" else "--frame-inspect"]
    return [sys.executable, str(ROOT / "server.py"), mode]


class QuietLogger:
    def debug(self, message):
        pass
    def warning(self, message):
        pass
    def error(self, message):
        pass


def base_options():
    name, path = runtime_path()
    opts = {"quiet": True, "no_warnings": True, "logger": QuietLogger(),
            "noplaylist": True, "socket_timeout": 20, "retries": 2,
            "extractor_retries": 1, "fragment_retries": 2,
            "cachedir": str(DATA / ".cache"), "windowsfilenames": True,
            "ffmpeg_location": ffmpeg_path()}
    if name:
        opts["js_runtimes"] = {name: {"path": path}}
    return opts


def public_error(message):
    value = re.sub(r"\x1b\[[0-9;]*m", "", str(message))
    low = value.lower()
    if "sign in" in low or "confirm you’re not a bot" in low or "confirm you're not a bot" in low:
        return "YouTube verlangt für dieses Video eine Anmeldung oder eine Bot-Prüfung. Dieser Download ist hier derzeit nicht möglich."
    if "private" in low or "members-only" in low:
        return "Dieses Video ist privat oder nur für Mitglieder zugänglich."
    if "unavailable" in low or "not available" in low or "removed" in low:
        return "Das Video ist nicht verfügbar oder in deiner Region gesperrt."
    if "403" in low or "forbidden" in low:
        return "YouTube hat den Abruf abgelehnt. Bitte aktualisiere die Werkzeuge mit Aktualisieren.command und versuche es erneut."
    if "timed out" in low or "timeout" in low:
        return "YouTube antwortet gerade nicht. Bitte versuche es gleich noch einmal."
    if "requested format" in low:
        return "Diese Qualität ist für das Video nicht verfügbar. Lade die Videoinformationen erneut."
    if any(x in low for x in ("resolve", "connection", "network", "nodename")):
        return "Die Verbindung zu YouTube ist fehlgeschlagen. Bitte prüfe deine Internetverbindung."
    return "Der Download konnte nicht abgeschlossen werden. " + value.replace("ERROR: ", "")[-300:]


def inspect_video(url):
    import yt_dlp
    with yt_dlp.YoutubeDL(base_options()) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info or info.get("is_live") or info.get("live_status") == "is_upcoming":
        raise ValueError("Bitte wähle ein abgeschlossenes Video. Laufende und geplante Livestreams werden nicht unterstützt.")
    heights = sorted({int(f["height"]) for f in info.get("formats", [])
                      if f.get("height") and f.get("vcodec") != "none" and not f.get("has_drm")}, reverse=True)
    if not heights:
        raise ValueError("Für dieses Video ist kein herunterladbares Videoformat verfügbar.")
    return {"url": url, "id": info["id"], "title": info.get("title", "YouTube-Video"),
            "channel": info.get("uploader", "YouTube"), "duration": info.get("duration"),
            "thumbnail": "https://i.ytimg.com/vi/" + info["id"] + "/hqdefault.jpg",
            "heights": heights, "max_height": max(heights),
            "has_audio": any(f.get("acodec") not in (None, "none") and not f.get("has_drm") for f in info.get("formats", [])),
            "webm_heights": sorted({int(f["height"]) for f in info.get("formats", []) if f.get("height") and f.get("ext") == "webm" and f.get("vcodec") != "none" and not f.get("has_drm")}, reverse=True)}


def emit(data):
    print("FRAME " + json.dumps(data, ensure_ascii=False), flush=True)


def download_worker(payload):
    import yt_dlp
    job_dir = DATA / payload["id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    selected = validate_options(payload)
    audio = selected["mode"] == "audio"
    opts = base_options()
    opts.update(download_options(payload, job_dir))

    def progress(data):
        status = data.get("status")
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        downloaded = data.get("downloaded_bytes", 0)
        info = data.get("info_dict", {})
        stream = "Audiospur" if audio or info.get("vcodec") == "none" else "Videospur"
        emit({"state": "downloading", "stage": stream + " wird geladen",
              **({"title": info["title"]} if info.get("title") else {}),
              "progress": min(100, round(downloaded / total * 100, 1)) if total else None,
              "downloaded": downloaded, "total": total, "speed": data.get("speed"), "eta": data.get("eta")})
        if status == "finished":
            emit({"state": "processing", "stage": "Audio wird vorbereitet" if audio else "Video wird vorbereitet", "progress": None})

    def postprocess(data):
        emit({"state": "processing", "stage": "Audio wird konvertiert" if audio else "Bild und Ton werden zusammengefügt", "progress": None})

    opts["progress_hooks"] = [progress]
    opts["postprocessor_hooks"] = [postprocess]
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(payload["url"], download=True)
    files = [p for p in job_dir.iterdir() if p.suffix.lower() == "." + payload["container"] and p.is_file()]
    if len(files) != 1:
        raise RuntimeError("Die fertige Datei wurde nicht gefunden.")
    emit({"state": "done", "stage": "Download abgeschlossen", "progress": 100,
          "file": files[0].name, "size": files[0].stat().st_size,
          "title": info.get("title", "YouTube-Video"), "height": None if audio else info.get("height"),
          "audio_bitrate": info.get("abr") if audio and selected["audio_quality"] == "best" else None})


def save_jobs():
    DATA.mkdir(parents=True, exist_ok=True)
    temporary = DATA / ".history.tmp"
    temporary.write_text(json.dumps(JOBS, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(DATA / ".history.json")
    temporary = DATA / ".batches.tmp"
    temporary.write_text(json.dumps(BATCHES, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(DATA / ".batches.json")


def load_jobs():
    try:
        stored = json.loads((DATA / ".batches.json").read_text(encoding="utf-8"))
        BATCHES.update({key: batch for key, batch in stored.items() if re.fullmatch(r"[a-f0-9]{32}", key)})
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        stored = json.loads((DATA / ".history.json").read_text(encoding="utf-8"))
        for key, job in stored.items():
            if not re.fullmatch(r"[a-f0-9]{32}", key):
                continue
            if job.get("state") not in ("done", "error", "cancelled"):
                job.update(state="error", error="Der Download wurde beim Beenden unterbrochen. Bitte starte ihn erneut.")
            JOBS[key] = job
    except (OSError, ValueError, TypeError):
        pass


def batch_urls(value):
    lines = value.splitlines() if isinstance(value, str) else value
    if not isinstance(lines, list) or not 1 <= len(lines) <= MAX_BATCH:
        raise ValueError(f"Bitte füge 1 bis {MAX_BATCH} Links ein, einen pro Zeile.")
    urls = []
    duplicates = 0
    for index, line in enumerate(lines, 1):
        if isinstance(line, str) and not line.strip():
            continue
        try:
            url = youtube_url(line)
        except ValueError as error:
            raise ValueError(f"Zeile {index}: {error}") from error
        if url in urls:
            duplicates += 1
        else:
            urls.append(url)
    if not urls:
        raise ValueError("Bitte füge mindestens einen YouTube-Link ein.")
    return urls, duplicates


def new_job(url, selected, title="YouTube-Video", batch_id=None):
    job = {"id": uuid.uuid4().hex, "url": url, **selected, "created": time.time(),
           "state": "queued", "stage": "In der Warteschlange", "progress": None, "title": title}
    if batch_id:
        job["batch_id"] = batch_id
    JOBS[job["id"]] = job
    return job


def completed_file(job):
    if job.get("state") != "done" or not job.get("file"):
        return None
    folder = (DATA / job["id"]).resolve()
    file = (folder / job["file"]).resolve()
    return file if folder.parent == DATA.resolve() and file.parent == folder and file.is_file() else None


def batch_summary(batch):
    items = [JOBS[key] for key in batch["jobs"] if key in JOBS]
    counts = {state: sum(j["state"] == state for j in items) for state in ("done", "error", "cancelled")}
    active = sum(j["state"] in ("queued", "downloading", "processing") for j in items)
    return {**batch, **counts, "total": len(batch["jobs"]), "active": active,
            "zip_ready": bool(counts["done"] and not active)}


def cleanup_partial(job_id):
    folder = DATA / job_id
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def submit_job(job):
    job["attempt"] = uuid.uuid4().hex
    POOL.submit(execute_job, job["id"], job["attempt"])


def execute_job(job_id, attempt):
    with LOCK:
        job = JOBS.get(job_id)
        if not job or job["state"] != "queued" or job.get("attempt") != attempt:
            return
        job.update(state="downloading", stage="Verbindung zu YouTube wird aufgebaut")
        proc = subprocess.Popen(worker_command("--worker"),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", start_new_session=os.name != "nt")
        PROCESSES[job_id] = proc
        proc.stdin.write(json.dumps(job) + "\n")
        proc.stdin.close()
    last_save = 0
    try:
        for line in proc.stdout:
            if not line.startswith("FRAME "):
                continue
            data = json.loads(line[6:])
            with LOCK:
                if job["state"] == "cancelled":
                    continue
                job.update(data)
                if time.time() - last_save > 2 or data.get("state") in ("done", "error"):
                    save_jobs()
                    last_save = time.time()
        code = proc.wait()
        with LOCK:
            if job["state"] == "cancelled":
                cleanup_partial(job_id)
            elif code != 0 or job["state"] != "done":
                job.update(state="error", error=job.get("error") or "Der Download wurde unerwartet beendet. Bitte versuche es erneut.")
                cleanup_partial(job_id)
            save_jobs()
    except Exception:
        with LOCK:
            job.update(state="error", error="Der Download wurde unterbrochen. Bitte versuche es erneut.")
            save_jobs()
    finally:
        with LOCK:
            PROCESSES.pop(job_id, None)


def stop_process(proc):
    with contextlib.suppress(ProcessLookupError, OSError):
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)


class Handler(BaseHTTPRequestHandler):
    server_version = "Frame/" + VERSION

    def log_message(self, fmt, *args):
        pass

    def local_request(self):
        return self.headers.get("Host") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def send_data(self, data, code=200, content_type="application/json; charset=utf-8", extra=None):
        body = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict, list)) else data
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https://i.ytimg.com; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(body)

    def do_GET(self):
        if not self.local_request():
            return self.send_data({"error": "Zugriff nur über localhost erlaubt."}, 403)
        path = urlparse(self.path).path
        if path == "/api/health":
            return self.send_data({**dependencies(), "token": TOKEN})
        if path == "/api/jobs":
            with LOCK:
                return self.send_data(sorted(JOBS.values(), key=lambda j: j["created"], reverse=True))
        if path == "/api/batches":
            with LOCK:
                return self.send_data([batch_summary(b) for b in sorted(BATCHES.values(), key=lambda b: b["created"], reverse=True)])
        match = re.fullmatch(r"/api/batches/([a-f0-9]{32})/zip", path)
        if match:
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return self.send_data({"error": "Dieser Zugriff ist nicht erlaubt."}, 403)
            return self.send_batch_zip(match[1])
        match = re.fullmatch(r"/api/files/([a-f0-9]{32})", path)
        if match:
            with LOCK:
                job = dict(JOBS.get(match[1], {}))
            if job.get("state") != "done" or not job.get("file"):
                return self.send_data({"error": "Die Datei ist noch nicht fertig."}, 404)
            folder = (DATA / match[1]).resolve()
            file = (folder / job["file"]).resolve()
            if file.parent != folder or not file.is_file():
                return self.send_data({"error": "Die Datei wurde verschoben oder gelöscht."}, 404)
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(file.stat().st_size))
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(file.name))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            with file.open("rb") as handle, contextlib.suppress(BrokenPipeError, ConnectionResetError):
                shutil.copyfileobj(handle, self.wfile)
            return
        assets = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/styles.css": "styles.css", "/favicon.svg": "favicon.svg"}
        if path in assets:
            file = ROOT / "web" / assets[path]
            return self.send_data(file.read_bytes(), content_type=(mimetypes.guess_type(file.name)[0] or "text/plain") + "; charset=utf-8")
        return self.send_data({"error": "Nicht gefunden."}, 404)

    def send_batch_zip(self, batch_id):
        with LOCK:
            batch = BATCHES.get(batch_id)
            if not batch:
                return self.send_data({"error": "Paket nicht gefunden."}, 404)
            summary = batch_summary(batch)
            if not summary["zip_ready"]:
                return self.send_data({"error": "Bitte warte, bis das Paket beendet ist. Mindestens eine Datei muss fertig sein."}, 409)
            files = [(index, completed_file(JOBS.get(key, {}))) for index, key in enumerate(batch["jobs"], 1)]
            if sum(file is not None for _, file in files) != summary["done"]:
                return self.send_data({"error": "Eine fertige Datei wurde verschoben oder gelöscht. Bitte lade sie erneut herunter."}, 409)
            manifest = {"files": [{"url": JOBS[key]["url"], "state": JOBS[key]["state"],
                                    "title": JOBS[key]["title"], "error": JOBS[key].get("error")}
                                   for key in batch["jobs"] if key in JOBS]}
        if not ZIP_SLOT.acquire(blocking=False):
            return self.send_data({"error": "Ein ZIP wird bereits vorbereitet. Bitte warte einen Moment."}, 429)
        headers_sent = False
        try:
            # Disk-backed ZIP64: large packages never accumulate in RAM; removed after delivery.
            with tempfile.TemporaryFile(dir=DATA) as temporary:
                with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
                    for index, file in files:
                        if file:
                            archive.write(file, f"{index:03d} - {file.name}")
                    archive.writestr("Paket-Info.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                size = temporary.tell()
                temporary.seek(0)
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(size))
                self.send_header("Content-Disposition", f'attachment; filename="Frame-Paket-{batch_id[:8]}.zip"')
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                headers_sent = True
                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    shutil.copyfileobj(temporary, self.wfile, length=1024 * 1024)
        except OSError:
            # Before headers, report disk/missing-file errors as a normal API response.
            if headers_sent:
                self.close_connection = True
            else:
                self.send_data({"error": "Das ZIP konnte nicht erstellt werden. Bitte prüfe den freien Speicherplatz und die Dateien."}, 507)
        finally:
            ZIP_SLOT.release()

    def do_POST(self):
        if not self.local_request() or self.headers.get("X-Frame-Token") != TOKEN:
            return self.send_data({"error": "Bitte lade die Seite erneut."}, 403)
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"):
            return self.send_data({"error": "Dieser Zugriff ist nicht erlaubt."}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 262144:
                raise ValueError("Die Anfrage ist ungültig.")
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("Die Anfrage ist ungültig.")
            path = urlparse(self.path).path
            if path == "/api/setup/retry":
                if not getattr(sys, "frozen", False):
                    return self.send_data({"error": "Bitte aktualisiere die Werkzeuge über den Frame-Starter."}, 400)
                from runtime_setup import start_setup
                start_setup(SETUP)
                return self.send_data({"starting": True}, 202)
            if path == "/api/shutdown":
                with LOCK:
                    if any(j["state"] in ("queued", "downloading", "processing") for j in JOBS.values()):
                        return self.send_data({"error": "Es laufen noch Downloads. Bitte warte oder brich sie zuerst ab."}, 409)
                self.send_data({"stopping": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if path == "/api/batches":
                urls, duplicates = batch_urls(data.get("urls"))
                selected = validate_options(data)
                if not dependencies()["ready"]:
                    return self.send_data({"error": "Die Download-Werkzeuge fehlen. Bitte starte Start.command."}, 503)
                with LOCK:
                    active = sum(j["state"] in ("queued", "downloading", "processing") for j in JOBS.values())
                    if active + len(urls) > MAX_QUEUED:
                        return self.send_data({"error": f"Maximal {MAX_QUEUED} Downloads dürfen gleichzeitig vorgemerkt sein. Bitte warte kurz."}, 429)
                    batch_id = uuid.uuid4().hex
                    items = [new_job(url, selected, f"Video {index}", batch_id) for index, url in enumerate(urls, 1)]
                    batch = {"id": batch_id, "created": time.time(), "jobs": [j["id"] for j in items],
                             "delivery": data.get("delivery", "files") if data.get("delivery") in ("files", "zip") else "files",
                             "duplicates": duplicates, **selected}
                    BATCHES[batch_id] = batch
                    for job in items:
                        submit_job(job)
                    save_jobs()
                    return self.send_data(batch_summary(batch), 202)
            match = re.fullmatch(r"/api/batches/([a-f0-9]{32})/(cancel|retry|remove)", path)
            if match:
                with LOCK:
                    batch = BATCHES.get(match[1])
                    if not batch:
                        return self.send_data({"error": "Paket nicht gefunden."}, 404)
                    items = [JOBS[key] for key in batch["jobs"] if key in JOBS]
                    action = match[2]
                    if action == "cancel":
                        for job in items:
                            if job["state"] in ("queued", "downloading", "processing"):
                                job.update(state="cancelled", stage="Abgebrochen")
                                if job["id"] in PROCESSES:
                                    stop_process(PROCESSES[job["id"]])
                    else:
                        if batch_summary(batch)["active"] or any(j["id"] in PROCESSES for j in items):
                            return self.send_data({"error": "Bitte warte, bis das Paket beendet ist."}, 409)
                        if action == "remove":
                            for job in items:
                                JOBS.pop(job["id"])
                            BATCHES.pop(batch["id"])
                        else:
                            retry = [j for j in items if j["state"] in ("error", "cancelled")]
                            if sum(j["state"] in ("queued", "downloading", "processing") for j in JOBS.values()) + len(retry) > MAX_QUEUED:
                                return self.send_data({"error": "Die Warteschlange ist voll. Bitte warte kurz."}, 429)
                            for job in retry:
                                job.pop("error", None)
                                job.update(state="queued", stage="In der Warteschlange", progress=None, speed=None, eta=None)
                                submit_job(job)
                    save_jobs()
                    return self.send_data({"removed": True} if action == "remove" else batch_summary(batch))
            if path == "/api/inspect":
                url = youtube_url(data.get("url"))
                if not dependencies()["ready"]:
                    return self.send_data({"error": "Bitte starte Frame über Start.command, um die Werkzeuge einzurichten."}, 503)
                if not INSPECT_SLOTS.acquire(blocking=False):
                    return self.send_data({"error": "Es laufen bereits zwei Videoabfragen. Bitte warte einen Moment."}, 429)
                try:
                    result = subprocess.run(worker_command("--inspect"),
                                            input=json.dumps({"url": url}), capture_output=True, text=True,
                                            encoding="utf-8", timeout=90)
                    response = json.loads(result.stdout)
                    return self.send_data(response, 200 if result.returncode == 0 else 422)
                finally:
                    INSPECT_SLOTS.release()
            if path == "/api/jobs":
                url = youtube_url(data.get("url"))
                selected = validate_options(data)
                if not dependencies()["ready"]:
                    return self.send_data({"error": "Die Download-Werkzeuge fehlen. Bitte starte Start.command."}, 503)
                with LOCK:
                    if sum(j["state"] in ("queued", "downloading", "processing") for j in JOBS.values()) >= MAX_QUEUED:
                        return self.send_data({"error": "Deine Warteschlange ist voll. Bitte warte, bis ein Download fertig ist."}, 429)
                    job_id = uuid.uuid4().hex
                    job = {"id": job_id, "url": url, **selected,
                           "created": time.time(), "state": "queued", "stage": "In der Warteschlange", "progress": None,
                           "title": str(data.get("title", "YouTube-Video"))[:300]}
                    JOBS[job_id] = job
                    submit_job(job)
                    save_jobs()
                    return self.send_data(dict(job), 202)
            match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})/cancel", path)
            if match:
                with LOCK:
                    job = JOBS.get(match[1])
                    if not job:
                        return self.send_data({"error": "Download nicht gefunden."}, 404)
                    if job["state"] not in ("done", "error", "cancelled"):
                        job.update(state="cancelled", stage="Abgebrochen")
                        if match[1] in PROCESSES:
                            stop_process(PROCESSES[match[1]])
                        save_jobs()
                    return self.send_data(dict(job))
            match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})/remove", path)
            if match:
                with LOCK:
                    job = JOBS.get(match[1])
                    if not job:
                        return self.send_data({"error": "Download nicht gefunden."}, 404)
                    if job["state"] not in ("done", "error", "cancelled") or match[1] in PROCESSES:
                        return self.send_data({"error": "Bitte warte, bis der Download beendet ist."}, 409)
                    if job.get("batch_id") in BATCHES:
                        return self.send_data({"error": "Bitte entferne das gesamte Paket aus dem Verlauf. Die Dateien bleiben erhalten."}, 409)
                    JOBS.pop(match[1])
                    save_jobs()
                    return self.send_data({"removed": True})
            return self.send_data({"error": "Nicht gefunden."}, 404)
        except ValueError as error:
            return self.send_data({"error": str(error)}, 400)
        except subprocess.TimeoutExpired:
            return self.send_data({"error": "Die Videoabfrage hat zu lange gedauert. Bitte versuche es erneut."}, 504)
        except Exception:
            return self.send_data({"error": "Die Anfrage konnte nicht verarbeitet werden. Bitte versuche es erneut."}, 500)


def main(argv=None):
    global PORT
    parser = argparse.ArgumentParser(description="Frame – YouTube-Downloader im Browser")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect or args.worker:
        try:
            payload = json.load(sys.stdin)
            if args.inspect:
                print(json.dumps(inspect_video(youtube_url(payload["url"])), ensure_ascii=False))
            else:
                download_worker(payload)
        except Exception as error:
            if args.inspect:
                print(json.dumps({"error": public_error(error)}, ensure_ascii=False))
            else:
                emit({"state": "error", "error": public_error(error)})
            sys.exit(1)
        return
    PORT = args.port
    DATA.mkdir(parents=True, exist_ok=True)
    load_jobs()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as error:
        import errno
        if error.errno == errno.EADDRINUSE:
            print(f"Port {PORT} ist bereits belegt. Läuft Frame schon? Öffne http://127.0.0.1:{PORT}")
        else:
            print(f"Frame konnte den lokalen Dienst nicht starten: {error}")
        sys.exit(1)
    print(f"\n  Frame läuft: http://127.0.0.1:{PORT}\n  Downloads: {DATA}\n  Beenden: Ctrl+C\n", flush=True)
    if args.open:
        threading.Timer(0.7, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with LOCK:
            for proc in PROCESSES.values():
                stop_process(proc)
        POOL.shutdown(wait=True, cancel_futures=True)
        server.server_close()


if __name__ == "__main__":
    main()
