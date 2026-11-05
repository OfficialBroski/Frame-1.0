"""First-run acquisition of FFmpeg directly from its upstream PyPI distributor."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import sys
import tempfile
import threading
import urllib.request
import zipfile

SETUP_LOCK = threading.Lock()


def platform_key():
    architecture = {'aarch64':'arm64','arm64':'arm64','amd64':'x64','x86_64':'x64'}.get(platform.machine().lower())
    key = f'{sys.platform}-{architecture}'
    if key not in ('darwin-arm64','darwin-x64','win32-x64','linux-x64'):
        raise RuntimeError('Diese Plattform wird von diesem Frame-Download nicht unterstützt.')
    return key


def ffmpeg_destination():
    from desktop import app_data
    return Path(os.environ.get('FRAME_APP_DATA', str(app_data()))) / 'tools/ffmpeg-0.8.1' / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')


def install_ffmpeg(state):
    from desktop import resources
    import certifi
    destination = ffmpeg_destination()
    if destination.is_file():
        state.update(message='', error='')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((resources() / 'resources/ffmpeg-downloads.json').read_text())
    item = manifest[platform_key()]
    state.update(message='Erster Start: Die Medienwerkzeuge werden automatisch eingerichtet …', error='')
    context = ssl.create_default_context(cafile=certifi.where())
    with tempfile.TemporaryDirectory(prefix='.setup-', dir=destination.parent) as temporary:
        wheel = Path(temporary) / 'ffmpeg.whl'
        digest = hashlib.sha256()
        received = 0
        with urllib.request.urlopen(item['url'], context=context, timeout=30) as source, wheel.open('wb') as output:
            while block := source.read(1024 * 1024):
                received += len(block)
                if received > item['size']:
                    raise RuntimeError('Die Werkzeug-Datei hat eine unerwartete Größe.')
                output.write(block)
                digest.update(block)
                state['message'] = f'Erster Start: Medienwerkzeuge werden geladen … {round(received / item["size"] * 100)} %'
        if received != item['size'] or digest.hexdigest() != item['sha256']:
            raise RuntimeError('Die Werkzeug-Datei konnte nicht sicher geprüft werden. Bitte starte Frame erneut.')
        with zipfile.ZipFile(wheel) as archive:
            matches = [name for name in archive.namelist() if name.startswith('imageio_ffmpeg/binaries/ffmpeg-') and not name.endswith('/')]
            if len(matches) != 1:
                raise RuntimeError('Das Werkzeugpaket hat ein unbekanntes Format.')
            candidate = Path(temporary) / destination.name
            with archive.open(matches[0]) as source, candidate.open('wb') as output:
                shutil.copyfileobj(source, output)
            candidate.chmod(0o755)
            candidate.replace(destination)
            for name in archive.namelist():
                if '.dist-info/' in name and ('license' in name.lower() or name.endswith('METADATA')):
                    (destination.parent / Path(name).name).write_bytes(archive.read(name))
    state.update(message='', error='')


def start_setup(state):
    if not SETUP_LOCK.acquire(blocking=False):
        return
    def run():
        try:
            install_ffmpeg(state)
        except Exception as error:
            import traceback
            traceback.print_exc()
            state.update(message='', error='Die automatische Einrichtung ist fehlgeschlagen. Bitte prüfe deine Internetverbindung und starte Frame erneut. ' + str(error))
        finally:
            SETUP_LOCK.release()
    threading.Thread(target=run, daemon=True, name='frame-first-run').start()
