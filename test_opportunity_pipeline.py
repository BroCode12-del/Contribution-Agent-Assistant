"""Step 10 offline tests; no real GitHub or Nightshift requests."""

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from opportunity_pipeline import (
    GitHub, GitHubFailure, assess_one, discover, fingerprint, preferences_checked,
    refresh_candidate, review_order, validate_assessment, write_json, source_spans, materialize_assessment,
)
from run_opportunities import provider_error, save_ranking


PREFERENCES = {
    "opportunity_type": "open_source_contribution", "max_candidates": 5,
    "language": "Python", "preferred_labels": ["good first issue", "help wanted"],
    "blocked_labels": ["Needs Discussion"], "require_open_issue": True, "exclude_pull_requests": True,
}
EVIDENCE = {"review_id": "a" * 32, "repository": "source/repo", "commit_sha": "b" * 40,
            "evidence": [{"id": "E1", "observation": "Calls pandas.read_csv to load CSV data"}]}


def issue(number=1):
    return {"repository_url": "https://api.github.com/repos/owner/repo", "number": number,
            "html_url": f"https://github.com/owner/repo/issues/{number}", "title": "Import CSV data",
            "body": "Add a CSV import test. Private data is already excluded.",
            "state": "open", "labels": [], "locked": False, "assignees": []}


class FakeGitHub:
    def __init__(self, routes):
        self.routes = routes

    def get(self, route):
        value = self.routes[route]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value), False


class ApiResponse(io.BytesIO):
    headers = {}

    def geturl(self):
        return "https://api.github.com/example"


class DiscoveryTests(unittest.TestCase):
    def test_preferences_reject_large_scope(self):
        for key, value in (("max_candidates", 100), ("max_candidates", True), ("language", "JavaScript"),
                           ("preferred_labels", ['bad" qualifier']), ("require_open_issue", False)):
            with self.subTest(key=key):
                preferences = copy.deepcopy(PREFERENCES)
                preferences[key] = value
                with self.assertRaises(ValueError):
                    preferences_checked(preferences)

    def test_two_searches_deduplicate_and_cap_results(self):
        class Search:
            def __init__(self): self.calls = 0
            def get(self, route):
                self.calls += 1
                return {"items": [issue(n) for n in range(1, 7)], "total_count": 6, "incomplete_results": False}, False
        search = Search()
        candidates, queries, errors = discover(search, PREFERENCES)
        self.assertEqual(search.calls, 2)
        self.assertEqual(len(candidates), 5)
        self.assertEqual(len({row["candidate_id"] for row in candidates}), 5)
        self.assertEqual(len(queries), 2)
        self.assertFalse(errors)

    def test_search_failure_not_fabricated_as_empty_success(self):
        class Failure:
            def get(self, route): raise GitHubFailure("http_403")
        candidates, queries, failures = discover(Failure(), PREFERENCES)
        self.assertEqual(candidates, [])
        self.assertEqual(queries, [])
        self.assertEqual(len(failures), 2)

    def test_http_failure_and_request_budget(self):
        def failing(request, timeout):
            raise HTTPError(request.full_url, 403, "fixture", {}, None)
        github = GitHub(opener=failing, request_limit=1)
        with self.assertRaisesRegex(GitHubFailure, "http_403"):
            github.get("/example")
        with self.assertRaisesRegex(GitHubFailure, "request_budget"):
            github.get("/example")

    def test_api_response_size_and_json(self):
        for content, reason in ((b"x" * 2_000_001, "size_limit"), (b"not json", "invalid_api_json")):
            with self.subTest(reason=reason):
                github = GitHub(opener=lambda *a, **k: ApiResponse(content))
                with self.assertRaisesRegex(GitHubFailure, reason): github.get("/example")


class StatusTests(unittest.TestCase):
    def routes(self, row=None):
        return {
            "/repos/owner/repo/issues/1": row or issue(),
            "/repos/owner/repo": {"archived": False, "disabled": False},
            "/repos/owner/repo/issues/1/comments?per_page=20&page=1": [],
            "/repos/owner/repo/issues/1/timeline?per_page=30&page=1": [],
        }

    def refresh(self, routes):
        return refresh_candidate(FakeGitHub(routes), {"repository": "owner/repo", "issue_number": 1, "candidate_id": "owner/repo#1"}, PREFERENCES)

    def test_basic_open_issue_is_needs_review_never_confirmed(self):
        candidate = self.refresh(self.routes())
        self.assertEqual(candidate["availability"], "needs_review")
        self.assertTrue(candidate["review_required"])

    def test_assigned_closed_locked_and_blocked_label(self):
        for changes, blocker in (({"assignees": [{"login": "someone"}]}, "already_assigned"),
                                 ({"state": "closed"}, "issue_not_open"), ({"locked": True}, "issue_locked"),
                                 ({"labels": [{"name": "needs discussion"}]}, "blocked_label"),
                                 ({"pull_request": {}}, "is_pull_request")):
            with self.subTest(blocker=blocker):
                row = issue(); row.update(changes)
                candidate = self.refresh(self.routes(row))
                self.assertIn(blocker, candidate["blockers"])
                self.assertEqual(candidate["availability"], "hold")

    def test_repository_archive_and_comment_restriction(self):
        routes = self.routes()
        routes["/repos/owner/repo"] = {"archived": True}
        routes["/repos/owner/repo/issues/1/comments?per_page=20&page=1"] = [{"body": "Please hold off until approval."}]
        candidate = self.refresh(routes)
        self.assertIn("repository_archived", candidate["blockers"])
        self.assertIn("possible_text_restriction_needs_review", candidate["blockers"])

    def test_private_repository_is_not_an_open_source_recommendation(self):
        routes = self.routes()
        routes["/repos/owner/repo"] = {"private": True, "archived": False}
        candidate = self.refresh(routes)
        self.assertIn("repository_not_public", candidate["blockers"])
        self.assertEqual(candidate["availability"], "hold")

    def test_open_pr_reference_is_conservative_hold(self):
        routes = self.routes()
        routes["/repos/owner/repo/issues/1/timeline?per_page=30&page=1"] = [{"source": {"issue": {"pull_request": {}, "state": "open", "html_url": "https://github.com/owner/repo/pull/2"}}}]
        # GitHub uses a populated pull_request object on timeline issue references.
        routes["/repos/owner/repo/issues/1/timeline?per_page=30&page=1"][0]["source"]["issue"]["pull_request"] = {"url": "https://api.github.com/repos/owner/repo/pulls/2"}
        candidate = self.refresh(routes)
        self.assertIn("referenced_open_pull_request_needs_review", candidate["blockers"])

    def test_failed_check_is_unknown_and_partial_pagination_visible(self):
        routes = self.routes()
        routes["/repos/owner/repo/issues/1/comments?per_page=20&page=1"] = GitHubFailure("http_403")
        candidate = self.refresh(routes)
        self.assertEqual(candidate["availability"], "unknown")
        self.assertFalse(candidate["context_complete"])
        self.assertEqual(candidate["check_failures"][0]["stage"], "comments")

    def test_missing_issue_recorded(self):
        routes = self.routes()
        routes["/repos/owner/repo/issues/1"] = GitHubFailure("http_404")
        candidate = self.refresh(routes)
        self.assertEqual(candidate["availability"], "unknown")
        self.assertFalse(candidate["body"])


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {"candidate_id": "owner/repo#1", "body": issue()["body"]}
        self.assessment = {
            "candidate_id": "owner/repo#1",
            "requirements": [{"statement": "Add a CSV import test.", "source_quote": "Add a CSV import test."}],
            "fit": [], "gaps": ["Tests are not established by supplied evidence."], "review_notes": ["Needs review."],
        }

    def test_exact_quotes_and_empty_fit_accepted(self):
        self.assertEqual(validate_assessment(json.dumps(self.assessment), "stop", self.candidate, EVIDENCE), self.assessment)

    def test_numbered_sources_copy_exact_original_text_and_offsets(self):
        candidate = {"candidate_id": "owner/repo#1", "body": "Préface. Add **CSV export** in `history.py`. Private data is already excluded. Include a test."}
        catalog = source_spans(candidate["body"])
        self.assertTrue(all(candidate["body"][row["start_char"]:row["end_char"]] == row["text"] for row in catalog))
        self.assertFalse(any("already" in row["text"] for row in catalog))
        span = next(row for row in catalog if "CSV export" in row["text"])
        payload = {**self.assessment, "requirements": [{"statement": "Add a CSV export action.", "source_span_id": span["id"]}]}
        result = materialize_assessment(json.dumps(payload), "stop", candidate, EVIDENCE)
        self.assertEqual(result["requirements"][0]["source_quote"], "Add **CSV export** in `history.py`.")
        changed = copy.deepcopy(result); changed["requirements"][0]["start_char"] += 1
        with self.assertRaisesRegex(ValueError, "source_span_mismatch"):
            validate_assessment(json.dumps(changed), "stop", candidate, EVIDENCE)

    def test_unknown_sources_and_generated_quotes_are_rejected(self):
        for requirement, reason in (({"statement": "Claim", "source_span_id": "Q999"}, "unknown_source_span_id"),
                                    ({"statement": "Claim", "source_span_id": "Q1", "source_quote": "invented"}, "generated_quote_not_allowed")):
            with self.assertRaisesRegex(ValueError, reason):
                materialize_assessment(json.dumps({**self.assessment, "requirements": [requirement]}), "stop", self.candidate, EVIDENCE)

    def test_existing_behavior_only_does_not_trigger_model_call(self):
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: self.fail("No model call expected"))))
        with self.assertRaisesRegex(ValueError, "no_reviewable_source_spans"):
            assess_one(client, "fixture", {"candidate_id": "owner/repo#1", "body": "Private data is already excluded."}, EVIDENCE)

    def test_stream_records_only_allowlisted_provider_provenance(self):
        chunks = [
            SimpleNamespace(meterless={"routed_model": "fixture/model", "from_cache": False, "receipt_id": "fixture-receipt", "api_key": "must-not-copy"}, choices=[]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=json.dumps({**self.assessment, "requirements": [{"statement": "Add a CSV import test.", "source_span_id": "Q1"}]})), finish_reason="stop")]),
        ]
        class Stream:
            def __enter__(self): return iter(chunks)
            def __exit__(self, *args): pass
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: Stream())))
        provenance = {}
        result = assess_one(client, "fixture/model", self.candidate, EVIDENCE, provenance)
        self.assertEqual(result["requirements"][0]["source_quote"], self.assessment["requirements"][0]["source_quote"])
        self.assertFalse(provenance["from_cache"])
        self.assertEqual(provenance["receipt_id"], "fixture-receipt")
        self.assertNotIn("api_key", provenance)

    def test_invalid_response_is_kept_as_diagnostic_not_assessment(self):
        class Stream:
            def __enter__(self):
                return iter([SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="not JSON"), finish_reason="stop")])])
            def __exit__(self, *args): pass
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: Stream())))
        with self.assertRaises(ValueError) as result:
            assess_one(client, "fixture/model", self.candidate, EVIDENCE)
        self.assertEqual(result.exception.validation_code, "invalid_json")
        self.assertEqual(result.exception.response_text, "not JSON")

    def test_wrong_candidate_and_bad_citation_rejected(self):
        for changes in ({"candidate_id": "other/repo#8"}, {"fit": [{"statement": "Claim", "evidence_ids": ["E99"]}]}):
            value = copy.deepcopy(self.assessment); value.update(changes)
            with self.assertRaises(ValueError): validate_assessment(json.dumps(value), "stop", self.candidate, EVIDENCE)

    def test_invented_and_existing_behavior_quotes_rejected(self):
        for quote in ("Invented requirement", "Private data is already excluded."):
            value = copy.deepcopy(self.assessment)
            value["requirements"][0]["source_quote"] = quote
            with self.assertRaises(ValueError): validate_assessment(json.dumps(value), "stop", self.candidate, EVIDENCE)

    def test_incomplete_stream_never_accepted(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_assessment(json.dumps(self.assessment), "length", self.candidate, EVIDENCE)

    def test_stream_error_closes_and_does_not_return_partial_assessment(self):
        class BrokenStream:
            closed = False
            def __enter__(self): return self
            def __exit__(self, *args): self.closed = True
            def __iter__(self):
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content='{"candidate_id":'), finish_reason=None)])
                raise RuntimeError("provider failed fixture")
        stream = BrokenStream()
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: stream)))
        with self.assertRaises(RuntimeError): assess_one(client, "meterless/auto", self.candidate, EVIDENCE)
        self.assertTrue(stream.closed)


class RankingTests(unittest.TestCase):
    def candidates(self):
        return [
            {"candidate_id": "a/export#1", "title": "Export CSV", "url": "fixture", "availability": "needs_review", "blockers": []},
            {"candidate_id": "b/import#2", "title": "Import CSV", "url": "fixture", "availability": "needs_review", "blockers": []},
            {"candidate_id": "c/assigned#3", "title": "Import CSV", "url": "fixture", "availability": "hold", "blockers": ["already_assigned"]},
        ]

    def test_reading_overlap_first_held_last(self):
        candidates = self.candidates()
        assessments = {row["candidate_id"]: {"status": "assessed"} for row in candidates}
        rows = review_order(candidates, assessments, EVIDENCE)
        self.assertEqual([row["candidate_id"] for row in rows], ["b/import#2", "a/export#1", "c/assigned#3"])
        self.assertEqual(rows[0]["topic_evidence_ids"], ["E1"])
        self.assertTrue(all(row["human_review_required"] for row in rows))
        self.assertTrue(all(row["suitable_for_implementation"] is None for row in rows))

    def test_failed_model_assessment_not_presented_as_success(self):
        candidates = self.candidates()
        assessments = {"b/import#2": {"status": "failed", "error": {"type": "APIError"}}, "a/export#1": {"status": "assessed"}}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            status = {"discovery_id": "d" * 32, "run_id": "e" * 32, "checked_at": "fixture"}
            ranking = save_ranking(folder, EVIDENCE, status, candidates, assessments)
            self.assertEqual(ranking["status"], "partial_assessments")
            self.assertEqual(ranking["assessment_failures"], 1)
            failed = next(row for row in ranking["candidates"] if row["candidate_id"] == "b/import#2")
            self.assertIsNone(failed["assessment"])
            self.assertEqual(failed["assessment_status"], "failed")

    def test_fingerprint_and_atomic_json(self):
        self.assertEqual(fingerprint({"a": 1, "b": 2}), fingerprint({"b": 2, "a": 1}))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "x.json"
            write_json(target, {"status": "fixture"})
            self.assertEqual(json.loads(target.read_text()), {"status": "fixture"})
            self.assertFalse(target.with_suffix(".json.tmp").exists())

    def test_transient_windows_file_lock_is_retried(self):
        original_replace = Path.replace
        attempts = []
        def replace(path, target):
            attempts.append(1)
            if len(attempts) < 3:
                raise PermissionError("fixture sharing violation")
            return original_replace(path, target)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "x.json"
            target.write_text('{"old": true}')
            with patch.object(Path, "replace", replace), patch("opportunity_pipeline.time.sleep"):
                write_json(target, {"new": True})
            self.assertEqual(json.loads(target.read_text()), {"new": True})
            self.assertEqual(len(attempts), 3)

    def test_permanent_lock_keeps_previous_valid_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "x.json"
            target.write_text('{"old": true}')
            with patch.object(Path, "replace", side_effect=PermissionError("fixture")), patch("opportunity_pipeline.time.sleep"):
                with self.assertRaises(PermissionError): write_json(target, {"new": True})
            self.assertEqual(json.loads(target.read_text()), {"old": True})

    def test_error_reporting_does_not_copy_sensitive_body(self):
        error = Exception("sensitive key in exception message")
        error.body = {"api_key": "secret", "error": {"code": "provider_error"}}
        reported = provider_error(error)
        self.assertNotIn("secret", json.dumps(reported))
        self.assertNotIn("sensitive", json.dumps(reported))

    def test_streaming_empty_response_error_is_normalized(self):
        error = Exception("raw diagnostic must not be copied")
        error.body = {"message": "nvidia/fixture-model_empty_response", "api_key": "secret"}
        value = provider_error(error)
        self.assertEqual(value["detail"], "empty_response")
        self.assertNotIn("secret", json.dumps(value))


if __name__ == "__main__":
    unittest.main()
