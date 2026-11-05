#!/usr/bin/env python3
"""Exercise the packaged binary: cold setup, detached service, worker codecs, shutdown."""
import argparse
import concurrent.futures
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from formats import VERSION


class Silent(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',type=Path)
    args=parser.parse_args()
    executable=args.executable or ROOT/'build/desktop'/('Frame.app/Contents/MacOS/Frame' if sys.platform=='darwin' else 'Frame/Frame.exe' if os.name=='nt' else 'Frame/Frame')
    with tempfile.TemporaryDirectory(prefix='frame-release-test-') as temporary:
        folder=Path(temporary)
        env=dict(os.environ,FRAME_APP_DATA=str(folder/'config'),FRAME_DATA_DIR=str(folder/'downloads'))
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        state=None
        launcher=subprocess.run([str(executable),'--no-browser','--port',str(port)],env=env,capture_output=True,timeout=45)
        assert launcher.returncode==0,(launcher.returncode,launcher.stderr,(folder/'config/server.log').read_text(errors='replace') if (folder/'config/server.log').exists() else 'No server log')
        try:
            for _ in range(180):
                with urllib.request.urlopen(base+'/api/health',timeout=3) as response: state=json.load(response)
                assert not state.get('setup',{}).get('error'),state
                if state['ready']: break
                time.sleep(1)
            else: raise AssertionError('First-run setup did not finish')
            assert state['version']==VERSION and state['javascript']=='node',state
            # A second launch must reuse the existing service.
            second=subprocess.run([str(executable),'--no-browser','--port',str(port)],env=env,capture_output=True,timeout=20)
            assert second.returncode==0,second.stderr
            with urllib.request.urlopen(base+'/') as response: assert b'Mehrere Links / Paket' in response.read()
            ffmpeg=folder/'config/tools/ffmpeg-0.8.1'/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')
            assert ffmpeg.is_file()
            source=folder/'sources';source.mkdir()
            with wave.open(str(source/'audio.wav'),'wb') as audio:
                audio.setparams((1,2,48000,0,'NONE','not compressed'))
                audio.writeframes(b''.join(struct.pack('<h',int(10000*math.sin(2*math.pi*440*i/48000))) for i in range(48000)))
            subprocess.run([str(ffmpeg),'-v','error','-f','lavfi','-i','color=c=blue:s=320x180:r=10','-i',str(source/'audio.wav'),'-t','1','-c:v','libx264','-c:a','aac',str(source/'video.mp4')],check=True,capture_output=True,timeout=30)
            http=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Silent,directory=str(source)))
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            def worker(container,name):
                job=uuid.uuid4().hex
                payload={'id':job,'url':f'http://127.0.0.1:{http.server_address[1]}/{name}','container':container,'audio_quality':'192' if container=='mp3' else 'best','quality':'best'}
                result=subprocess.run([str(executable),'--frame-worker'],input=json.dumps(payload),text=True,capture_output=True,env=env,timeout=60)
                assert result.returncode==0,(result.stdout,result.stderr)
                events=[json.loads(line[6:]) for line in result.stdout.splitlines() if line.startswith('FRAME ')]
                assert events and events[-1]['state']=='done',events
                file=folder/'downloads'/job/events[-1]['file']
                subprocess.run([str(ffmpeg),'-v','error','-i',str(file),'-f','null','-'],check=True,capture_output=True,timeout=30)
                return container
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    futures=[pool.submit(worker,'mp3','audio.wav'),pool.submit(worker,'mp4','video.mp4')]
                    for future in futures: print('Frozen worker and full decode:',future.result())
            finally:
                http.shutdown();http.server_close();thread.join()
            print('PASS: native launcher, first-run SHA-256 download, detached service, reuse, web assets, MP3/MP4 workers.')
        finally:
            if state:
                request=urllib.request.Request(base+'/api/shutdown',data=b'{}',headers={'Content-Type':'application/json','X-Frame-Token':state['token']})
                with urllib.request.urlopen(request,timeout=10) as response: assert json.load(response)['stopping']
                # Wait until the service releases files, particularly on Windows.
                for _ in range(40):
                    try:
                        urllib.request.urlopen(base+'/api/health',timeout=.3).close()
                        time.sleep(.1)
                    except OSError: break


if __name__=='__main__': main()
