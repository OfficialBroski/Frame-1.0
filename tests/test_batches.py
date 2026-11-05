"""Package API: atomic admission, shared settings, retries and real ZIP delivery."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

import server

URL1 = "https://youtu.be/jNQXAC9IVRw"
URL2 = "https://youtu.be/BaW_jenozKc"


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DATA = Path(self.temp.name)
        server.JOBS.clear()
        server.BATCHES.clear()
        self.pool = patch.object(server.POOL, "submit").start()
        self.dependencies = patch.object(server, "dependencies", return_value={"ready": True}).start()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        server.PORT = self.http.server_address[1]
        self.base = f"http://127.0.0.1:{server.PORT}"
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        patch.stopall()
        self.temp.cleanup()

    def request(self, path, payload=None, headers=None):
        request = urllib.request.Request(self.base + path, data=None if payload is None else json.dumps(payload).encode(),
            headers={"X-Frame-Token": server.TOKEN, "Content-Type": "application/json", **(headers or {})})
        try:
            return urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            return error

    def create(self, **extra):
        with self.request("/api/batches", {"urls": [URL1, URL2], "container": "mp4", "quality": "720", **extra}) as response:
            self.assertEqual(response.code, 202)
            return json.load(response)

    def finish(self, batch, failed=False):
        for index, key in enumerate(batch["jobs"]):
            job = server.JOBS[key]
            if failed and index == 1:
                job.update(state="error", error="Video nicht verfügbar")
                continue
            folder = server.DATA / key
            folder.mkdir(exist_ok=True)
            (folder / "Gleicher Titel ä.mp4").write_bytes(b"fixture-" + bytes([index]))
            job.update(state="done", file="Gleicher Titel ä.mp4", size=9)

    def test_shared_settings_deduplication_and_persistence(self):
        batch = self.create(urls=[URL1, URL1, URL2], container="mp3", audio_quality="192", delivery="zip")
        self.assertEqual((batch["total"], batch["duplicates"]), (2, 1))
        self.assertEqual(self.pool.call_count, 2)
        for job in server.JOBS.values():
            self.assertEqual((job["mode"], job["container"], job["audio_quality"]), ("audio", "mp3", "192"))
        self.finish(batch)
        server.save_jobs()
        server.JOBS.clear()
        server.BATCHES.clear()
        server.load_jobs()
        self.assertEqual(server.batch_summary(server.BATCHES[batch["id"]])["done"], 2)

    def test_atomic_validation_and_limits(self):
        for urls in ([URL1, "file:///etc/passwd"], [], [URL1] * 101):
            with self.request("/api/batches", {"urls": urls}) as response:
                self.assertEqual(response.code, 400)
            self.assertEqual(server.JOBS, {})
        for index in range(server.MAX_QUEUED - 1):
            server.JOBS[str(index)] = {"state": "queued"}
        with self.request("/api/batches", {"urls": [URL1, URL2]}) as response:
            self.assertEqual(response.code, 429)
        self.assertEqual(server.BATCHES, {})

    def test_full_hundred_link_package_is_admitted_with_shared_video_cap(self):
        urls = [f"https://youtu.be/{index:011d}" for index in range(100)]
        batch = self.create(urls=urls, quality="1080")
        self.assertEqual((batch["total"], self.pool.call_count), (100, 100))
        self.assertTrue(all(job["quality"] == "1080" for job in server.JOBS.values()))

    def test_zip_waits_then_delivers_unique_files_and_failure_manifest(self):
        batch = self.create()
        route = f"/api/batches/{batch['id']}/zip"
        with self.request(route) as response:
            self.assertEqual(response.code, 409)
        self.finish(batch)
        with self.request(route) as response:
            self.assertEqual(response.code, 200)
            self.assertIn("attachment", response.headers["Content-Disposition"])
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("001 - Gleicher Titel ä.mp4"), b"fixture-\0")
                self.assertEqual(archive.read("002 - Gleicher Titel ä.mp4"), b"fixture-\1")
        server.JOBS[batch["jobs"][1]].update(state="error", error="Testfehler")
        with self.request(route) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                self.assertEqual(len(archive.namelist()), 2)
                self.assertEqual(json.loads(archive.read("Paket-Info.json"))["files"][1]["error"], "Testfehler")
        with self.request(route, headers={"Sec-Fetch-Site": "cross-site"}) as response:
            self.assertEqual(response.code, 403)

    def test_cancel_retry_ignores_stale_work_and_remove_keeps_files(self):
        batch = self.create()
        job = server.JOBS[batch["jobs"][0]]
        old_attempt = job["attempt"]
        with self.request(f"/api/batches/{batch['id']}/cancel", {}) as response:
            self.assertEqual(json.load(response)["cancelled"], 2)
        with self.request(f"/api/batches/{batch['id']}/retry", {}) as response:
            self.assertEqual(json.load(response)["active"], 2)
        self.assertNotEqual(job["attempt"], old_attempt)
        with patch.object(server.subprocess, "Popen") as process:
            server.execute_job(job["id"], old_attempt)
            process.assert_not_called()
        self.finish(batch)
        file = server.completed_file(job)
        with self.request(f"/api/jobs/{job['id']}/remove", {}) as response:
            self.assertEqual(response.code, 409)
        with self.request(f"/api/batches/{batch['id']}/remove", {}) as response:
            self.assertEqual(response.code, 200)
        self.assertTrue(file.is_file())
        self.assertFalse(server.JOBS or server.BATCHES)

    def test_missing_file_or_path_escape_does_not_enter_zip(self):
        batch = self.create()
        self.finish(batch)
        job = server.JOBS[batch["jobs"][0]]
        job["file"] = "../outside.mp4"
        (server.DATA / "outside.mp4").write_bytes(b"private")
        with self.request(f"/api/batches/{batch['id']}/zip") as response:
            self.assertEqual(response.code, 409)


if __name__ == "__main__":
    unittest.main()
