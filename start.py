#!/usr/bin/env python3
"""Create an isolated runtime on first launch, then start Frame."""
import os
from pathlib import Path
import subprocess
import sys
import venv
import urllib.request
import webbrowser
import argparse

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".runtime"
PYTHON = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    if sys.version_info < (3, 11):
        if PYTHON.is_file():
            os.execv(str(PYTHON), [str(PYTHON), str(ROOT / "start.py"), *sys.argv[1:]])
        print("Frame benötigt Python 3.11 oder neuer. Bitte installiere es von https://www.python.org/downloads/.")
        return 1
    parser = argparse.ArgumentParser(description="Frame – lokaler Video- und Audio-Downloader")
    parser.add_argument("--update", action="store_true", help="Download-Werkzeuge aktualisieren")
    parser.add_argument("--check", action="store_true", help="Einrichtung prüfen, ohne Installation oder Start")
    parser.add_argument("--no-browser", action="store_true", help="Browser nicht automatisch öffnen")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    update = args.update
    url = f"http://127.0.0.1:{args.port}"
    if args.check:
        if PYTHON.is_file() and Path(sys.prefix).resolve() != ENV.resolve():
            os.execv(str(PYTHON), [str(PYTHON), str(ROOT / "start.py"), *sys.argv[1:]])
        from server import dependencies
        state = dependencies()
        print(f"yt-dlp: {state['yt_dlp'] or 'fehlt'}\nFFmpeg: {'bereit' if state['ffmpeg'] else 'fehlt'}\nJavaScript: {state['javascript'] or 'Node.js 22+ oder Deno 2.3+ installieren'}")
        return 0 if state["ready"] else 1
    if not update:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as response:
                running = response.headers.get("Server", "").startswith("Frame/")
            if running:
                if not args.no_browser:
                    webbrowser.open(url)
                print("Frame läuft bereits: " + url)
                return 0
        except OSError:
            pass
    external = os.environ.get("FRAME_PYTHON")
    if external and Path(external).is_file():
        python = Path(external)
    else:
        python = PYTHON
        if not python.is_file():
            print("Frame wird einmalig eingerichtet …", flush=True)
            venv.create(ENV, with_pip=True)
    ready = subprocess.run([str(python), "-c", "import yt_dlp, yt_dlp_ejs, imageio_ffmpeg"], capture_output=True).returncode == 0
    if not ready or update:
        subprocess.run([str(python), "-m", "pip", "install", "--no-cache-dir", "--upgrade", "-r", str(ROOT / "requirements.txt")], check=True)
    # yt-dlp needs a modern JavaScript runtime for YouTube's player challenges.
    from server import runtime_path
    if not runtime_path()[0]:
        print("Bitte installiere zusätzlich Node.js 22+ von https://nodejs.org/ oder Deno 2.3+ von https://deno.com/.")
        return 1
    if update:
        print("\nWerkzeuge aktualisiert. Starte Frame jetzt erneut.")
        return 0
    command = [str(python), str(ROOT / "server.py"), "--port", str(args.port)]
    if not args.no_browser:
        command.append("--open")
    os.execv(str(python), command)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError:
        print("\nDie Einrichtung ist fehlgeschlagen. Bitte prüfe deine Internetverbindung und starte erneut.")
        sys.exit(1)
