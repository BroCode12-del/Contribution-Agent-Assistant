import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from repository_download import download_selected, safe_destination


class Response(io.BytesIO):
    status = 200


def entry(name, data):
    return {
        "path": name, "type": "blob", "mode": "100644", "size": len(data),
        "sha": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest(),
    }


class DownloaderTests(unittest.TestCase):
    def run_download(self, entries, opener, total=100, per_file=100):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source"
        source.mkdir()
        manifest = {
            "repository": "owner/repo", "commit_sha": "a" * 40,
            "limits": {"max_files": 20, "max_file_bytes": per_file, "max_total_bytes": total},
            "selected_files": entries, "downloaded_files": [], "download_failures": [],
        }
        download_selected(manifest, source, root / "manifest.json", opener)
        self.assertEqual(json.loads((root / "manifest.json").read_text()), manifest)
        return source, manifest

    def test_pinned_download_is_saved_but_not_executed(self):
        data = b"raise RuntimeError('must never execute')\n"
        def opener(request, timeout):
            self.assertIn("/" + "a" * 40 + "/nested/test.py", request.full_url)
            return Response(data)
        root, manifest = self.run_download([entry("nested/test.py", data)], opener)
        self.assertEqual((root / "nested/test.py").read_bytes(), data)
        self.assertEqual(len(manifest["downloaded_files"]), 1)
        self.assertEqual(manifest["status"], "selected_files_downloaded")

    def test_rejects_windows_and_traversal_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("../bad.py", "/bad.py", "x\\bad.py", "C:/bad.py", "CON.py", "x./bad.py", "x:stream.py", "x//bad.py"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    safe_destination(directory, name)

    def test_actual_file_limit(self):
        root, manifest = self.run_download([entry("a.py", b"x")], lambda *a, **k: Response(b"x" * 1000), per_file=10)
        self.assertEqual(manifest["transferred_bytes"], 11)
        self.assertEqual(manifest["download_failures"][0]["reason"], "actual_file_size_limit")
        self.assertFalse((root / "a.py").exists())

    def test_total_limit_stops_later_requests(self):
        calls = []
        def opener(*args, **kwargs):
            calls.append(1)
            return Response(b"x" * 1000)
        _, manifest = self.run_download([entry("a.py", b"x"), entry("b.py", b"y")], opener, total=5)
        self.assertEqual(len(calls), 1)
        self.assertEqual(manifest["transferred_bytes"], 6)
        self.assertEqual(len(manifest["download_failures"]), 2)

    def test_hash_mismatch(self):
        root, manifest = self.run_download([entry("a.py", b"x")], lambda *a, **k: Response(b"y"))
        self.assertEqual(manifest["download_failures"][0]["reason"], "git_blob_hash_mismatch")
        self.assertFalse((root / "a.py").exists())

    def test_case_collision(self):
        data = b"x"
        _, manifest = self.run_download([entry("A.py", data), entry("a.py", data)], lambda *a, **k: Response(data))
        self.assertEqual(len(manifest["downloaded_files"]), 1)
        self.assertEqual(manifest["download_failures"][0]["reason"], "case_insensitive_path_collision")

    def test_http_failure_recorded(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 404, "Not found", {}, None)
        _, manifest = self.run_download([entry("a.py", b"x")], opener)
        self.assertEqual(manifest["download_failures"][0]["reason"], "http_404")


if __name__ == "__main__":
    unittest.main()
