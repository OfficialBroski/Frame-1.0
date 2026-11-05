#!/usr/bin/env python3
"""Build a native portable app on its target OS; never bundle local user data."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from formats import VERSION
from runtime_setup import platform_key


def vendor_node():
    import certifi
    key = platform_key()
    item = json.loads((ROOT/'resources/node-downloads.json').read_text())[key]
    cache = ROOT/'.build-runtime'/key
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache/('node.exe' if os.name=='nt' else 'node')
    if binary.is_file() and (cache/'LICENSE').is_file():
        return binary
    archive = cache/item['filename']
    import urllib.request
    if not archive.exists():
        with urllib.request.urlopen(item['url'],context=ssl.create_default_context(cafile=certifi.where()),timeout=60) as response, archive.open('wb') as output:
            shutil.copyfileobj(response,output)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=item['sha256']:
        archive.unlink()
        raise RuntimeError('Node.js SHA-256 verification failed')
    if archive.suffix=='.zip':
        with zipfile.ZipFile(archive) as package:
            for suffix,destination in (('/node.exe',binary),('/LICENSE',cache/'LICENSE')):
                name=next(name for name in package.namelist() if name.endswith(suffix))
                destination.write_bytes(package.read(name))
    else:
        with tarfile.open(archive) as package:
            for suffix,destination in (('/bin/node',binary),('/LICENSE',cache/'LICENSE')):
                entry=next(entry for entry in package.getmembers() if entry.name.endswith(suffix))
                with package.extractfile(entry) as source, destination.open('wb') as output:
                    shutil.copyfileobj(source,output)
    binary.chmod(0o755)
    return binary


def icons():
    from PIL import Image, ImageDraw
    folder=ROOT/'build/icons'
    folder.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGBA',(1024,1024),(0,0,0,0))
    draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((55,55,969,969),radius=205,fill='#b9f1cf')
    stroke='#173422'
    draw.line([(512,246),(512,631)],fill=stroke,width=63)
    draw.line([(354,479),(512,637),(670,479)],fill=stroke,width=63,joint='curve')
    draw.line([(280,672),(280,777),(744,777),(744,672)],fill=stroke,width=63,joint='curve')
    image.save(folder/'Frame.png')
    image.save(folder/'Frame.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    if sys.platform=='darwin':
        image.save(folder/'Frame.icns')
    return folder


def licenses(node):
    folder=ROOT/'build/licenses'
    folder.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'resources/Python-LICENSE.txt',folder/'Python-LICENSE.txt')
    shutil.copy2(node.parent/'LICENSE',folder/'Node.js-LICENSE.txt')
    for distribution in importlib.metadata.distributions():
        name=distribution.metadata.get('Name','unknown')
        if name.lower() in ('pillow','pip','setuptools','packaging','pyinstaller-hooks-contrib','altgraph','macholib','pefile','pywin32-ctypes'):
            continue
        for entry in distribution.files or []:
            if '.dist-info/' in str(entry) and any(value in entry.name.lower() for value in ('license','copying','notice')):
                file=Path(distribution.locate_file(entry))
                if file.is_file(): shutil.copy2(file,folder/(name+'-'+entry.name))
    return folder


def build():
    import PyInstaller.__main__
    node=vendor_node()
    artwork=icons()
    notice=licenses(node)
    args=[str(ROOT/'desktop.py'),'--noconfirm','--clean','--onedir','--name','Frame',
          '--distpath',str(ROOT/'build/desktop'),'--workpath',str(ROOT/'build/pyinstaller'),
          '--specpath',str(ROOT/'build'), '--add-data',f'{ROOT / "web"}:web',
          '--add-data',f'{ROOT / "resources"}:resources', '--add-data',f'{ROOT / "LICENSE"}:.',
          '--add-data',f'{ROOT / "THIRD_PARTY_NOTICES.md"}:.', '--add-data',f'{notice}:licenses',
          '--add-binary',f'{node}:vendor','--collect-all','yt_dlp','--collect-all','yt_dlp_ejs',
          '--copy-metadata','yt-dlp','--copy-metadata','certifi',
          '--hidden-import','server','--hidden-import','runtime_setup','--hidden-import','certifi',
          '--exclude-module','imageio_ffmpeg','--exclude-module','PIL','--exclude-module','tkinter']
    # Preserve supplemental trust files provided by the build's Python distribution.
    # Standard python.org/GitHub Python does not normally have these files.
    for trust_file in Path(ssl.__file__).parent.glob('*.pem'):
        args += ['--add-data',f'{trust_file}:.']
    if sys.platform in ('darwin','win32'):
        args += ['--windowed','--icon',str(artwork/('Frame.icns' if sys.platform=='darwin' else 'Frame.ico'))]
    if sys.platform=='darwin':
        args += ['--osx-bundle-identifier','local.frame.downloader']
        # PyInstaller accepts a generated spec to customize CFBundleVersion afterward; re-sign before release.
    PyInstaller.__main__.run(args)
    app=ROOT/'build/desktop'/('Frame.app' if sys.platform=='darwin' else 'Frame')
    if sys.platform=='darwin':
        import plistlib
        plist=app/'Contents/Info.plist'
        data=plistlib.loads(plist.read_bytes())
        data.update(CFBundleShortVersionString=VERSION,CFBundleVersion=VERSION,LSMinimumSystemVersion='14.0',LSApplicationCategoryType='public.app-category.utilities')
        plist.write_bytes(plistlib.dumps(data))
        subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
        subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    return app


def package(app):
    destination=ROOT/'dist'
    destination.mkdir(exist_ok=True)
    key=platform_key()
    name={'darwin-arm64':'macOS-AppleSilicon','darwin-x64':'macOS-Intel','win32-x64':'Windows-x64','linux-x64':'Linux-x64'}[key]
    output=destination/f'Frame-v{VERSION}-{name}'
    if sys.platform=='darwin':
        output=Path(str(output)+'.zip')
        subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(output)],check=True)
    elif os.name=='nt':
        output=Path(str(output)+'.zip')
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(app.rglob('*')):
                if file.is_file(): archive.write(file,'Frame/'+file.relative_to(app).as_posix())
    else:
        output=Path(str(output)+'.tar.gz')
        with tarfile.open(output,'w:gz',dereference=False) as archive:
            archive.add(app,arcname='Frame')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n')
    print('Release:',output)
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--package-only',action='store_true')
    args=parser.parse_args()
    app=ROOT/'build/desktop'/('Frame.app' if sys.platform=='darwin' else 'Frame') if args.package_only else build()
    package(app)
