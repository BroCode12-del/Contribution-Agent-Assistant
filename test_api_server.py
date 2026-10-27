"""UI contract and action-boundary tests; no external services are called."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import api_server as app


class QuietHandler(app.Handler):
    def log_message(self, *args):
        pass


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.LocalServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        app.JOBS.clear()

    def get(self, path):
        with urlopen(self.base + path, timeout=5) as response:
            return response.read(), response.headers

    def post(self, value, origin=None, token=None):
        request = Request(self.base + "/api/actions", data=json.dumps(value).encode(),
                          headers={"Content-Type": "application/json", "Origin": origin or self.base,
                                   "X-Session-Token": token if token is not None else app.SESSION_TOKEN})
        return urlopen(request, timeout=5)

    def test_saved_review_includes_source_and_analysis(self):
        body, _ = self.get("/api/review")
        value = json.loads(body)
        self.assertEqual([row["id"] for row in value["evidence"]], ["E1", "E2", "E3"])
        self.assertEqual(value["analysis"]["review_id"], value["review_id"])
        self.assertIn("ranking", value)

    def test_demo_is_explicitly_separate_and_private(self):
        body, _ = self.get("/api/demo")
        value = json.loads(body)
        self.assertIn("separate", value["scope"])
        self.assertFalse(value["outreach"]["sending_allowed"])
        self.assertEqual(value["state"]["latest_decision"]["attempts_used"], 3)

    def test_assets_have_restricted_policy_and_no_cache(self):
        for path in ("/", "/app.js", "/style.css"):
            body, headers = self.get(path)
            self.assertTrue(body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])

    def test_secrets_and_traversal_are_not_served(self):
        for path in ("/.env", "/api/review?review_id=../../.env", "/../api_server.py"):
            with self.assertRaises(HTTPError) as error:
                self.get(path)
            self.assertIn(error.exception.code, (400, 404))
            error.exception.close()

    def test_cross_origin_and_missing_token_are_rejected(self):
        for kwargs in ({"origin": "https://example.com"}, {"token": ""}):
            with self.assertRaises(HTTPError) as error:
                self.post({"action": "memory"}, **kwargs)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()

    def test_invalid_actions_and_non_github_urls_are_rejected(self):
        for payload in ({"action": "shell", "command": "anything"}, {"action": "fetch", "url": "http://localhost:3000/"}):
            with self.assertRaises(HTTPError) as error:
                self.post(payload)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()

    def test_second_server_cannot_share_the_same_port(self):
        with self.assertRaises(OSError):
            app.LocalServer(("127.0.0.1", self.server.server_port), QuietHandler)

    def test_busy_action_cannot_start_second_worker(self):
        app.JOBS["existing"] = {"status": "running"}
        with self.assertRaisesRegex(ValueError, "already running"):
            app.start_action({"action": "memory"})

    def test_fetch_worker_collects_only_its_new_review(self):
        app.JOBS["job"] = {"status": "running"}
        new_id = "a" * 32
        with patch.object(app, "run_script", side_effect=[f"Review ID: {new_id}", "collected"]) as run:
            app.action_worker("job", {"action": "fetch", "url": "https://github.com/owner/repo"})
        self.assertEqual(app.JOBS["job"]["result"]["review_id"], new_id)
        self.assertEqual(run.call_args_list[1].kwargs["input_text"], new_id + "\n")

    def test_provider_failure_is_reported_not_claimed_success(self):
        app.JOBS["job"] = {"status": "running"}
        with patch.object(app, "run_script", side_effect=ValueError("Nightshift did not return an assessment.")):
            app.action_worker("job", {"action": "analyse", "review_id": app.REVIEW_ID})
        self.assertEqual(app.JOBS["job"]["status"], "failed")
        self.assertNotIn("result", app.JOBS["job"])

    def test_memory_worker_returns_actual_comparison(self):
        app.JOBS["job"] = {"status": "running"}
        comparison = {"without_memory": {"next_action": "review_submission_provenance"}, "with_memory": {"next_action": "request_independent_evidence"}}
        with patch.object(app, "run_script", return_value=json.dumps(comparison) + "\nPASS: test"):
            app.action_worker("job", {"action": "memory"})
        self.assertEqual(app.JOBS["job"]["result"]["comparison"], comparison)


if __name__ == "__main__":
    unittest.main()
