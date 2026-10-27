"""Offline Step 9 checks; all generated reviews live in temporary folders."""

import contextlib
import copy
import hashlib
import io
import json
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError


PROJECT = Path(__file__).parent
REVIEW_ID = "a" * 32


class FetchFailureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        shutil.copy2(PROJECT / "fetch_repository.py", self.folder / "fetch_repository.py")

    def run_fetch(self, url="https://github.com/owner/repo", responses=(), error=None):
        with (
            patch("builtins.input", return_value=url),
            patch("urllib.request.urlopen", side_effect=error or responses) as request,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            try:
                runpy.run_path(str(self.folder / "fetch_repository.py"), run_name="__main__")
            except SystemExit as stopped:
                return str(stopped), request.call_count
        return None, request.call_count

    def test_invalid_url_never_contacts_network(self):
        for url in ("http://github.com/owner/repo", "https://example.com/owner/repo", "https://github.com/owner/repo/tree/main", "https://github.com/owner/repo?x=1"):
            with self.subTest(url=url):
                message, calls = self.run_fetch(url)
                self.assertIn("Enter a repository URL", message)
                self.assertEqual(calls, 0)

    def test_not_found_and_rate_limit_messages(self):
        for status, expected in ((404, "not publicly accessible"), (403, "rate limits"), (429, "rate limits")):
            with self.subTest(status=status):
                error = HTTPError("https://api.github.com/", status, "fixture", {}, None)
                try:
                    message, _ = self.run_fetch(error=error)
                    self.assertIn(expected, message)
                finally:
                    error.close()

    def test_connection_failure(self):
        message, _ = self.run_fetch(error=URLError("offline fixture"))
        self.assertIn("Could not reach GitHub", message)

    def test_timeout(self):
        message, _ = self.run_fetch(error=TimeoutError("fixture"))
        self.assertIn("Could not reach GitHub", message)

    def test_private_repository_rejected(self):
        message, _ = self.run_fetch(responses=[io.BytesIO(b'{"private":true}')])
        self.assertIn("Only public repositories", message)

    def test_truncated_listing_rejected_before_review_creation(self):
        responses = [
            io.BytesIO(json.dumps({"private": False, "full_name": "owner/repo", "default_branch": "main"}).encode()),
            io.BytesIO(json.dumps({"sha": "b" * 40, "commit": {"tree": {"sha": "c" * 40}}}).encode()),
            io.BytesIO(b'{"truncated":true,"tree":[]}'),
        ]
        message, calls = self.run_fetch(responses=responses)
        self.assertIn("complete file listing", message)
        self.assertEqual(calls, 3)
        self.assertFalse((self.folder / "reviews").exists())


class ReviewFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        for name in ("collect_repository.py", "check_review.py"):
            shutil.copy2(PROJECT / name, self.folder / name)
        self.review = self.folder / "reviews" / REVIEW_ID
        self.source = self.review / "source"
        self.source.mkdir(parents=True)
        self.manifest = {
            "review_id": REVIEW_ID, "repository": "fixture/repo", "commit_sha": "b" * 40,
            "downloaded_files": [],
            "excluded_files": [{"file": "excluded.py", "reason": "file_size_limit"}],
            "download_failures": [{"file": "missing.py", "reason": "http_404"}],
        }
        self.add_source("good.py", b'import pandas as pd\npd.read_csv("data.csv")\n')

    def add_source(self, name, data):
        (self.source / name).write_bytes(data)
        self.manifest["downloaded_files"].append({"file": name, "sha256": hashlib.sha256(data).hexdigest()})

    def run_script(self, name):
        (self.review / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(self.folder / name)], input=REVIEW_ID + "\n",
            capture_output=True, text=True, timeout=10,
        )

    def test_manifest_only_scan_records_parse_failures_and_coverage(self):
        self.add_source("broken.py", b"def broken(\n")
        self.add_source("encoding.py", b"\xff\xfe\xfa")
        (self.source / "unlisted.py").write_text('import pandas as pd\npd.read_csv("extra.csv")', encoding="utf-8")
        completed = self.run_script("collect_repository.py")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads((self.review / "evidence.json").read_text())
        self.assertEqual([item["file"] for item in report["evidence"]], ["good.py"])
        self.assertEqual({item["reason"] for item in report["skipped_files"]}, {"syntax_error", "encoding_error"})
        self.assertIs(report["all_python_files_parsed"], False)
        self.assertEqual(report["excluded_files"], self.manifest["excluded_files"])
        self.assertEqual(report["download_failures"], self.manifest["download_failures"])

    def test_changed_file_rejected_without_new_evidence(self):
        (self.source / "good.py").write_text("# modified", encoding="utf-8")
        completed = self.run_script("collect_repository.py")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("File changed since download", completed.stderr)
        self.assertFalse((self.review / "evidence.json").exists())

    def test_missing_file_rejected(self):
        (self.source / "good.py").unlink()
        completed = self.run_script("collect_repository.py")
        self.assertIn("Cannot read downloaded file", completed.stderr)
        self.assertNotEqual(completed.returncode, 0)

    def test_empty_downloads_rejected(self):
        self.manifest["downloaded_files"] = []
        completed = self.run_script("collect_repository.py")
        self.assertIn("No successfully downloaded files", completed.stderr)

    def make_analysis(self):
        completed = self.run_script("collect_repository.py")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        # Synthetic analysis fixture; this test does not call an AI provider.
        analysis = {key: self.manifest[key] for key in ("review_id", "repository", "commit_sha")}
        analysis["observations"] = [{"statement": "Fixture observation", "evidence_ids": ["E1"]}]
        return analysis

    def test_matching_review_passes(self):
        analysis = self.make_analysis()
        (self.review / "analysis.json").write_text(json.dumps(analysis))
        completed = self.run_script("check_review.py")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PASS:", completed.stdout)

    def test_mixed_review_and_invented_citation_rejected(self):
        analysis = self.make_analysis()
        for key, value, message in (
            ("review_id", "c" * 32, "Review IDs do not match"),
            ("repository", "other/repository", "Repository or commit"),
            ("commit_sha", "c" * 40, "Repository or commit"),
            ("observations", [{"evidence_ids": ["E99"]}], "unknown evidence"),
        ):
            with self.subTest(key=key):
                changed = copy.deepcopy(analysis)
                changed[key] = value
                (self.review / "analysis.json").write_text(json.dumps(changed))
                completed = self.run_script("check_review.py")
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(message, completed.stderr)


if __name__ == "__main__":
    unittest.main()
