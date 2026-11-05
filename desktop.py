"""Portable desktop entry point. The browser is the UI; no system Python is needed."""
from __future__ import annotations
import argparse
import contextlib
import ctypes
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser


def resources():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))


def app_data():
    if os.environ.get('FRAME_APP_DATA'):
        return Path(os.environ['FRAME_APP_DATA'])
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Frame'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/Frame'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'frame'


def configure():
    root = resources()
    os.environ.setdefault('FRAME_DATA_DIR', str(Path.home() / 'Downloads/Frame-Medien'))
    os.environ.setdefault('FRAME_APP_DATA', str(app_data()))
    if getattr(sys, 'frozen', False):
        os.environ['FRAME_JS_RUNTIME'] = 'node:' + str(root / 'vendor' / ('node.exe' if os.name == 'nt' else 'node'))
        from runtime_setup import ffmpeg_destination
        os.environ['FRAME_FFMPEG'] = str(ffmpeg_destination())
        # Use the CA bundle shipped with the application on every supported OS.
        import certifi
        os.environ.setdefault('SSL_CERT_FILE', certifi.where())


def command(*arguments):
    if getattr(sys, 'frozen', False):
        return [sys.executable, *arguments]
    return [sys.executable, '-u', str(Path(__file__).resolve()), *arguments]


def restore_streams():
    """Windowed Windows bootloaders leave sys.std* unset, even for piped workers."""
    for name, descriptor, mode in [('stdin',0,'r'), ('stdout',1,'w'), ('stderr',2,'w')]:
        if getattr(sys, name) is not None:
            continue
        try:
            if os.name == 'nt':
                import msvcrt
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.GetStdHandle.restype = ctypes.c_void_p
                handle = kernel.GetStdHandle({0:-10,1:-11,2:-12}[descriptor])
                if not handle or handle == ctypes.c_void_p(-1).value:
                    raise OSError('No standard handle')
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY if mode == 'r' else os.O_WRONLY)
            else:
                fd = os.dup(descriptor)
            setattr(sys, name, os.fdopen(fd, mode, encoding='utf-8', buffering=1))
        except OSError:
            setattr(sys, name, open(os.devnull, mode, encoding='utf-8'))


def health(port):
    request = urllib.request.Request(f'http://127.0.0.1:{port}/api/health')
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            if response.status == 200 and response.headers.get('Server','').startswith('Frame/'):
                return json.load(response)
    except (OSError, ValueError) as error:
        if os.environ.get('FRAME_DEBUG') and sys.stderr:
            print('Health:', repr(error), file=sys.stderr)
    return None


def open_page(url):
    # External desktop tools must not inherit PyInstaller's bundled library paths.
    original = dict(os.environ)
    try:
        for key in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH'):
            if key + '_ORIG' in os.environ:
                os.environ[key] = os.environ[key + '_ORIG']
            else:
                os.environ.pop(key, None)
        if os.name == 'nt' and getattr(sys, 'frozen', False):
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        return webbrowser.open(url)
    finally:
        os.environ.clear()
        os.environ.update(original)
        if os.name == 'nt' and getattr(sys, 'frozen', False):
            ctypes.windll.kernel32.SetDllDirectoryW(str(resources()))


def show_error(error, log):
    folder = app_data()
    folder.mkdir(parents=True, exist_ok=True)
    page = folder / 'start-error.html'
    page.write_text('<!doctype html><meta charset="utf-8"><title>Frame – Start</title>'
        '<body style="background:#111719;color:#d6efdf;font:18px/1.6 system-ui;padding:8vw">'
        '<h1>Frame konnte nicht starten.</h1><p>' + html.escape(str(error)) +
        '</p><p>Bitte schließe eine ältere Frame-Version und öffne Frame erneut.</p><p>Startprotokoll: ' +
        html.escape(str(log)) + '</p></body>', encoding='utf-8')
    open_page(page.as_uri())


def main():
    configure()
    if sys.argv[1:2] == ['--frame-worker'] or sys.argv[1:2] == ['--frame-inspect']:
        restore_streams()
        import server
        server.main(['--worker' if sys.argv[1] == '--frame-worker' else '--inspect'])
        return 0
    if sys.argv[1:2] == ['--frame-server']:
        restore_streams()
        import server
        if getattr(sys, 'frozen', False):
            from runtime_setup import start_setup
            start_setup(server.SETUP)
        server.main(sys.argv[2:])
        return 0
    parser = argparse.ArgumentParser(description='Frame – Video- und Audio-Downloader')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Port muss zwischen 1024 und 65535 liegen.')
    folder = app_data()
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / 'server.log'
    child = None
    try:
        running = health(args.port)
        if running and running.get('setup',{}).get('error'):
            request = urllib.request.Request(f'http://127.0.0.1:{args.port}/api/setup/retry',data=b'{}',
                headers={'Content-Type':'application/json','X-Frame-Token':running['token']})
            with urllib.request.urlopen(request,timeout=5): pass
        if not running:
            if log.exists() and log.stat().st_size > 2_000_000:
                log.replace(folder / 'server-previous.log')
            with log.open('ab') as output:
                child = subprocess.Popen(command('--frame-server','--port',str(args.port)),
                    stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                    start_new_session=os.name != 'nt',
                    creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS) if os.name == 'nt' else 0)
            for _ in range(100):
                if health(args.port):
                    break
                if child.poll() is not None:
                    raise RuntimeError('Der lokale Dienst konnte nicht gestartet werden. Möglicherweise ist der Port bereits belegt.')
                time.sleep(.2)
            else:
                raise RuntimeError('Der Start dauert zu lange. Bitte versuche es erneut.')
        if not args.no_browser:
            if not open_page(f'http://127.0.0.1:{args.port}/'):
                raise RuntimeError(f'Bitte öffne http://127.0.0.1:{args.port}/ in deinem Browser.')
        return 0
    except Exception as error:
        with log.open('a', encoding='utf-8') as output:
            output.write('\n' + repr(error) + '\n')
        if not args.no_browser:
            show_error(error, log)
        elif sys.stderr:
            print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
