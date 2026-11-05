"""Exercise local HTTP boundaries and file access with isolated temporary data."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server
from formats import VERSION


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        server.DATA = Path(cls.temp.name)
        server.JOBS.clear()
        server.BATCHES.clear()
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        server.PORT = cls.http.server_address[1]
        cls.base = f"http://127.0.0.1:{server.PORT}"
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, data=None, headers=None):
        headers = {"X-Frame-Token": server.TOKEN, "Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            return urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            return error

    def test_health_and_interface(self):
        with self.request("/api/health") as r:
            result = json.load(r)
            self.assertEqual(len(result["formats"]), 8)
            self.assertEqual(result["version"], VERSION)
        with self.request("/") as r:
            self.assertEqual(r.status, 200)
            self.assertIn(b"Nur Audio", r.read())

    def test_rejects_external_origin_wrong_host_and_missing_token(self):
        for headers in ({"Origin": "https://external.invalid"}, {"Host": "external.invalid"}, {"X-Frame-Token": ""}):
            with self.subTest(headers=headers), self.request("/api/jobs", {}, headers) as r:
                self.assertEqual(r.code, 403)

    def test_rejects_non_youtube_sources(self):
        for url in ("file:///etc/passwd", "http://127.0.0.1/internal", "https://youtube.com.evil.invalid/watch?v=jNQXAC9IVRw"):
            with self.subTest(url=url), self.request("/api/inspect", {"url": url}) as r:
                self.assertEqual(r.code, 400)

    def test_file_access_does_not_escape_job_directory(self):
        jobid = "a" * 32
        outside = server.DATA / "outside.mp3"
        outside.write_bytes(b"outside")
        (server.DATA / jobid).mkdir(exist_ok=True)
        server.JOBS[jobid] = {"state": "done", "file": "../outside.mp3"}
        with self.request("/api/files/" + jobid) as r:
            self.assertEqual(r.code, 404)
        server.JOBS.pop(jobid)

    def test_finished_file_delivered_as_attachment(self):
        jobid = "b" * 32
        folder = server.DATA / jobid
        folder.mkdir(exist_ok=True)
        (folder / "Ton mit Umlaut ä.mp3").write_bytes(b"sample-audio")
        server.JOBS[jobid] = {"state": "done", "file": "Ton mit Umlaut ä.mp3"}
        with self.request("/api/files/" + jobid) as r:
            self.assertEqual(r.read(), b"sample-audio")
            self.assertIn("attachment", r.headers["Content-Disposition"])
            self.assertIn("%C3%A4", r.headers["Content-Disposition"])
        server.JOBS.pop(jobid)


if __name__ == "__main__":
    unittest.main()
