"""Offline integration tests with generated media, never a YouTube account."""
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import imageio_ffmpeg
import yt_dlp

from formats import FORMATS, download_options, validate_options


class FixtureHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class MediaConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        fixtures = [
            ("video.webm", ["-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10", "-t", "1", "-an", "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8"]),
            ("audio.webm", ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1", "-c:a", "libopus"]),
            ("audio.m4a", ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1", "-c:a", "aac"]),
        ]
        for name, args in fixtures:
            subprocess.run([cls.ffmpeg, "-y", "-v", "error", *args, str(cls.root / name)], check=True, capture_output=True)
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(FixtureHandler, directory=str(cls.root)))
        cls.base = f"http://127.0.0.1:{cls.http.server_address[1]}/"
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.temporary.cleanup()

    def convert(self, container, audio_quality="best"):
        directory = self.root / (container + audio_quality)
        directory.mkdir(exist_ok=True)
        payload = {"container": container, "audio_quality": audio_quality, "quality": "180"}
        opts = download_options(payload, directory)
        opts.update(quiet=True, no_warnings=True, cachedir=False, ffmpeg_location=self.ffmpeg)
        formats = [
            {"format_id": "v", "url": self.base + "video.webm", "ext": "webm", "vcodec": "vp9", "acodec": "none", "height": 180, "width": 320, "tbr": 150},
            {"format_id": "a", "url": self.base + "audio.webm", "ext": "webm", "vcodec": "none", "acodec": "opus", "abr": 128},
            {"format_id": "aac", "url": self.base + "audio.m4a", "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 120},
        ]
        with contextlib.redirect_stdout(io.StringIO()), yt_dlp.YoutubeDL(opts) as ydl:
            ydl.process_ie_result({"id": "fixture", "title": "Frame test", "extractor": "test", "duration": 1, "formats": formats}, download=True)
        files = list(directory.glob("*." + container))
        self.assertEqual(len(files), 1, list(directory.iterdir()))
        result = subprocess.run([self.ffmpeg, "-hide_banner", "-i", str(files[0])], capture_output=True, text=True)
        self.assertIn("Audio:", result.stderr)
        decode = subprocess.run([self.ffmpeg, "-v", "error", "-i", str(files[0]), "-f", "null", "-"], capture_output=True, text=True)
        self.assertEqual(decode.returncode, 0, decode.stderr)
        return result.stderr

    def test_all_audio_formats_produce_playable_audio_without_video(self):
        for item in FORMATS:
            if item["kind"] != "audio":
                continue
            with self.subTest(format=item["id"]):
                output = self.convert(item["id"], item["default_quality"])
                self.assertNotIn("Video:", output)

    def test_all_video_containers_keep_video_and_audio(self):
        for container in ("mp4", "mkv", "webm"):
            with self.subTest(format=container):
                self.assertIn("Video:", self.convert(container))

    def test_mp3_bitrate_selection_is_honored(self):
        for bitrate in ("128", "320"):
            with self.subTest(bitrate=bitrate):
                self.assertIn(f"{bitrate} kb/s", self.convert("mp3", bitrate))

    def test_invalid_format_combinations_are_rejected(self):
        for data in ({"container": "exe"}, {"container": "mp3", "mode": "video"},
                     {"container": "mp3", "audio_quality": "9999"}, {"container": "wav", "audio_quality": "320"},
                     {"container": "mp4", "quality": "../../outside"}):
            with self.subTest(request=data), self.assertRaises(ValueError):
                validate_options(data)


if __name__ == "__main__":
    unittest.main()
