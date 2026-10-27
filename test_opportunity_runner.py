"""Offline runner checks for checkpoints, resume, freshness, and retry caps."""

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import run_opportunities as runner
from opportunity_pipeline import ASSESSMENT_CONTRACT, ASSESSMENT_INSTRUCTIONS, assessment_input, fingerprint


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.review_id = "a" * 32
        self.discovery_id = "d" * 32
        self.run_id = "e" * 32
        review = self.root / "reviews" / self.review_id
        (review / "source").mkdir(parents=True)
        source = b'import pandas as pd\npd.read_csv("x.csv")\n'
        (review / "source" / "code.py").write_bytes(source)
        common = {"review_id": self.review_id, "repository": "owner/repo", "commit_sha": "b" * 40}
        manifest = {**common, "downloaded_files": [{"file": "code.py", "sha256": hashlib.sha256(source).hexdigest()}]}
        self.evidence = {**common, "evidence": [{"id": "E1", "file": "code.py", "verification": "static_code_only", "observation": "Calls pandas.read_csv to load CSV data"}]}
        for filename, value in (("manifest.json", manifest), ("evidence.json", self.evidence)):
            (review / filename).write_text(json.dumps(value))
        preferences = {
            "opportunity_type": "open_source_contribution", "max_candidates": 5,
            "language": "Python", "preferred_labels": ["good first issue", "help wanted"],
            "blocked_labels": ["Needs Discussion"], "require_open_issue": True, "exclude_pull_requests": True,
        }
        (self.root / "opportunity_preferences.json").write_text(json.dumps(preferences))
        self.candidate = {"candidate_id": "target/repo#1", "repository": "target/repo", "issue_number": 1,
                          "title": "Import CSV", "body": "Add a CSV import test.", "url": "https://github.com/target/repo/issues/1",
                          "availability": "needs_review", "blockers": [], "checked_at": runner.now()}
        self.folder = self.root / "discoveries" / self.discovery_id / "runs" / self.review_id / self.run_id
        self.folder.mkdir(parents=True)
        self.status = {"review_id": self.review_id, "discovery_id": self.discovery_id, "run_id": self.run_id,
                       "assessment_contract": ASSESSMENT_CONTRACT,
                       "checked_at": runner.now(), "evidence_sha256": fingerprint(self.evidence), "candidates": [self.candidate]}
        self.save_status()

    def save_status(self):
        (self.folder / "status_checks.json").write_text(json.dumps(self.status))

    def invoke(self, *extra):
        argv = ["run_opportunities.py", "--review-id", self.review_id, "--discovery-id", self.discovery_id, "--run-id", self.run_id, *extra]
        with patch.object(runner, "PROJECT", self.root), patch("sys.argv", argv), patch.object(runner, "load_dotenv"), contextlib.redirect_stdout(io.StringIO()):
            runner.main()

    def test_no_ai_writes_partial_ranking_without_provider(self):
        with patch("openai.OpenAI") as client:
            self.invoke("--no-ai")
            client.assert_not_called()
        ranking = json.loads((self.folder / "ranking.json").read_text())
        self.assertEqual(ranking["status"], "partial_assessments")
        self.assertEqual(ranking["candidates"][0]["assessment_status"], "not_requested")

    def test_targeted_retry_preserves_other_failure_without_calling_provider(self):
        self.write_cached("failed", 1)
        other = {**self.candidate, "candidate_id": "other/repo#2"}
        self.status["candidates"].append(other)
        self.save_status()
        with patch("openai.OpenAI") as client, patch.object(runner, "assess_one") as assess:
            self.invoke("--candidate-id", other["candidate_id"], "--no-ai", "--retry-failed")
            client.assert_not_called()
            assess.assert_not_called()
        ranking = json.loads((self.folder / "ranking.json").read_text())
        original = next(row for row in ranking["candidates"] if row["candidate_id"] == self.candidate["candidate_id"])
        self.assertEqual(original["assessment_status"], "failed")

    def test_unknown_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "not in this run"):
            self.invoke("--candidate-id", "unknown/repo#3", "--no-ai")

    def test_stale_status_and_changed_evidence_rejected(self):
        self.status["checked_at"] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.save_status()
        with self.assertRaisesRegex(ValueError, "24 hours"): self.invoke("--no-ai")
        self.status["checked_at"] = runner.now()
        self.status["evidence_sha256"] = "wrong"
        self.save_status()
        with self.assertRaisesRegex(ValueError, "evidence changed"): self.invoke("--no-ai")

    def test_modified_download_blocks_runner(self):
        (self.root / "reviews" / self.review_id / "source" / "code.py").write_text("# edited")
        with self.assertRaisesRegex(ValueError, "source changed"): self.invoke("--no-ai")

    def test_cached_success_resumes_without_another_assessment(self):
        assessment = {"candidate_id": self.candidate["candidate_id"],
                      "requirements": [{"statement": "Add a test", "source_quote": "Add a CSV import test."}],
                      "fit": [], "gaps": ["Tests not established."], "review_notes": ["Needs review."]}
        self.write_cached("assessed", 1, assessment)
        with patch("openai.OpenAI"), patch.object(runner, "assess_one") as assess:
            self.invoke()
            assess.assert_not_called()
        ranking = json.loads((self.folder / "ranking.json").read_text())
        self.assertEqual(ranking["status"], "assessed_needs_human_review")

    def write_cached(self, status, attempts, assessment=None):
        key = fingerprint({"input": assessment_input(self.candidate, self.evidence), "instructions": ASSESSMENT_INSTRUCTIONS})
        path = self.folder / "assessments" / (hashlib.sha256(self.candidate["candidate_id"].encode()).hexdigest() + ".json")
        path.parent.mkdir(exist_ok=True)
        value = {"status": status, "attempt_count": attempts, "input_sha256": key, "error": {"type": "APIError"}}
        if assessment is not None: value["assessment"] = assessment
        path.write_text(json.dumps(value))

    def test_failed_assessment_not_retried_without_flag(self):
        self.write_cached("failed", 1)
        with patch("openai.OpenAI"), patch.object(runner, "assess_one") as assess:
            self.invoke()
            assess.assert_not_called()

    def test_retry_cap_stops_at_two(self):
        self.write_cached("failed", 2)
        with patch("openai.OpenAI"), patch.object(runner, "assess_one") as assess:
            self.invoke("--retry-failed")
            assess.assert_not_called()

    def test_known_blocker_is_held_without_requesting_ai(self):
        self.status["candidates"][0].update(availability="hold", blockers=["already_assigned"])
        self.save_status()
        with patch("openai.OpenAI") as client, patch.object(runner, "assess_one") as assess:
            self.invoke()
            client.assert_not_called(); assess.assert_not_called()
        ranking = json.loads((self.folder / "ranking.json").read_text())
        self.assertEqual(ranking["status"], "review_complete_with_holds")
        self.assertEqual(ranking["held_without_ai"], 1)
        self.assertEqual(ranking["candidates"][0]["assessment_status"], "held")

    def test_interrupted_request_keeps_its_attempt_and_requires_retry_flag(self):
        self.write_cached("in_progress", 1)
        with patch.object(runner, "assess_one") as assess:
            self.invoke()
            assess.assert_not_called()
        path = next((self.folder / "assessments").glob("*.json"))
        record = json.loads(path.read_text())
        self.assertEqual(record["attempt_count"], 1)
        self.assertEqual(record["error"]["type"], "InterruptedRequest")

    def test_changed_input_does_not_reset_the_budget(self):
        self.write_cached("failed", 2)
        self.status["candidates"][0]["body"] += " More work."
        self.save_status()
        with self.assertRaisesRegex(ValueError, "Previous attempts are preserved"):
            self.invoke("--retry-failed")

    def test_older_contract_refuses_new_inference_but_allows_inspection(self):
        self.status.pop("assessment_contract")
        self.save_status()
        with self.assertRaisesRegex(ValueError, "earlier assessment contract"):
            self.invoke()
        with patch.object(runner, "assess_one") as assess:
            self.invoke("--no-ai")
            assess.assert_not_called()

    def test_attempt_checkpoint_exists_before_inference(self):
        assessment = {"candidate_id": self.candidate["candidate_id"], "requirements": [{"statement": "Add a test", "source_quote": self.candidate["body"]}],
                      "fit": [], "gaps": ["Tests not established."], "review_notes": ["Needs review."]}
        def complete(*args, **kwargs):
            checkpoint = json.loads(next((self.folder / "assessments").glob("*.json")).read_text())
            self.assertEqual(checkpoint["status"], "in_progress")
            self.assertEqual(checkpoint["attempt_count"], 1)
            return assessment
        with patch.dict("os.environ", {"METERLESS_BASE_URL": "http://127.0.0.1:1/v1", "METERLESS_RUNTIME_TOKEN": "fixture", "METERLESS_MODEL": "fixture/model"}), patch("openai.OpenAI"), patch.object(runner, "assess_one", side_effect=complete) as assess:
            self.invoke()
            self.assertEqual(assess.call_count, 1)

    def test_invalid_cached_success_cannot_trigger_third_request(self):
        self.write_cached("assessed", 2, {"candidate_id": "wrong"})
        with patch("openai.OpenAI") as client, patch.object(runner, "assess_one") as assess:
            self.invoke("--retry-failed")
            client.assert_not_called(); assess.assert_not_called()
        record = json.loads(next((self.folder / "assessments").glob("*.json")).read_text())
        self.assertEqual(record["attempt_count"], 2)
        self.assertEqual(record["error"]["type"], "RetryLimit")

    def prior_fixture(self, status, count, assessment=None):
        self.write_cached(status,count,assessment)
        current=next((self.folder/'assessments').glob('*.json'))
        value=json.loads(current.read_text())
        value.update(assessment_contract=ASSESSMENT_CONTRACT,candidate_id=self.candidate['candidate_id'],review_id=self.review_id)
        other=self.folder.parent/('f'*32)/'assessments';other.mkdir(parents=True)
        (other/current.name).write_text(json.dumps(value));current.unlink()

    def test_fresh_status_run_reuses_exact_input_assessment_without_ai(self):
        assessment={'candidate_id':self.candidate['candidate_id'],'requirements':[{'statement':'Add a test','source_quote':self.candidate['body']}],
                    'fit':[],'gaps':['Tests not established.'],'review_notes':['Needs review.']}
        self.prior_fixture('assessed',1,assessment)
        with patch('openai.OpenAI') as client:
            self.invoke();client.assert_not_called()
        record=json.loads(next((self.folder/'assessments').glob('*.json')).read_text())
        self.assertEqual(record['attempt_count'],0)
        self.assertTrue(record['application_cache']['reused'])

    def test_fresh_status_run_retains_exact_input_exhausted_failure(self):
        self.prior_fixture('failed',2)
        with patch('openai.OpenAI') as client:
            self.invoke('--retry-failed');client.assert_not_called()
        record=json.loads(next((self.folder/'assessments').glob('*.json')).read_text())
        self.assertEqual(record['attempt_count'],2)
        self.assertEqual(record['status'],'failed')

    def test_changed_issue_input_is_not_reused(self):
        self.prior_fixture('failed',2)
        self.status['candidates'][0]['body']+=' Changed requirement.';self.save_status()
        self.invoke('--no-ai')
        record=json.loads(next((self.folder/'assessments').glob('*.json')).read_text())
        self.assertEqual(record['status'],'not_requested')
        self.assertNotIn('application_cache',record)


if __name__ == "__main__":
    unittest.main()
