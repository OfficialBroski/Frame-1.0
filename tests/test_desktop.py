"""Portable entry point and verified first-run runtime acquisition."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import desktop
import runtime_setup
import server


class DesktopTests(unittest.TestCase):
    def test_frozen_workers_use_app_executable_not_a_python_script(self):
        with patch.object(server.sys,'frozen',True,create=True):
            self.assertEqual(server.worker_command('--worker'),[server.sys.executable,'--frame-worker'])
            self.assertEqual(server.worker_command('--inspect'),[server.sys.executable,'--frame-inspect'])

    def test_configurable_user_data_is_outside_readonly_bundle(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ,{'FRAME_APP_DATA':temporary}):
            self.assertEqual(desktop.app_data(),Path(temporary))
            self.assertEqual(runtime_setup.ffmpeg_destination().parent.parent,Path(temporary)/'tools')

    def test_runtime_download_rejects_hash_mismatch_and_extracts_only_expected_file(self):
        content=io.BytesIO()
        with zipfile.ZipFile(content,'w') as archive:
            archive.writestr('imageio_ffmpeg/binaries/ffmpeg-fixture',b'fixture executable')
            archive.writestr('imageio_ffmpeg-0.8.1.dist-info/licenses/LICENSE',b'fixture license')
        payload=content.getvalue()
        for valid in (False,True):
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                (root/'resources').mkdir()
                item={'url':'https://files.pythonhosted.org/fixture.whl','size':len(payload),'sha256':hashlib.sha256(payload).hexdigest() if valid else '0'*64}
                (root/'resources/ffmpeg-downloads.json').write_text(json.dumps({'fixture':item}))
                destination=root/'tools/ffmpeg'
                state={}
                with patch.object(desktop,'resources',return_value=root), patch.object(runtime_setup,'platform_key',return_value='fixture'), patch.object(runtime_setup,'ffmpeg_destination',return_value=destination), patch.object(runtime_setup.urllib.request,'urlopen',return_value=io.BytesIO(payload)):
                    if valid:
                        runtime_setup.install_ffmpeg(state)
                        self.assertEqual(destination.read_bytes(),b'fixture executable')
                        self.assertEqual((destination.parent/'LICENSE').read_bytes(),b'fixture license')
                    else:
                        with self.assertRaises(RuntimeError): runtime_setup.install_ffmpeg(state)
                        self.assertFalse(destination.exists())


if __name__=='__main__': unittest.main()
