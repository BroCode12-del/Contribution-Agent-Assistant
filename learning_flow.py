"""Persist one opportunity's bounded practice → feedback → decision → draft flow.

Only structured outputs are graded. No submitted Python is executed.
"""
import csv
import hashlib
import io
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from base64 import b64encode

from dotenv import dotenv_values
from opportunity_pipeline import check_id, fingerprint, now, validate_assessment, write_json

PROJECT = Path(__file__).parent
RUNTIME_ROOT = Path(__file__).parent
ORIGINS = {"unverified", "self_reported_independent", "ai_assisted", "ai_written_reference"}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def task(flow_id, sequence):
    csv_text = "external_id,rating\n0007,8\n0042,6\n" if sequence == 1 else "external_id,rating\n0009,10\n0031,7\n"
    return {"task_id": f"{flow_id}-P{sequence}", "sequence": sequence,
            "title": "Preserve identifiers in a CSV ratings import",
            "generation_method": "fixed_template_selected_from_csv_import_gap",
            "instructions": "Use Python/pandas or reason through this small CSV import. Return a JSON list of objects with external_id and rating. Preserve identifier strings with leading zeros and keep ratings numeric. Paste the resulting records below. The checker measures the submitted output, not your source code or authorship.",
            "input_csv": csv_text,
            "success_criteria": ["Two records with external_id and rating only.", "Identifier strings retain their leading zeros and original order.", "Ratings are numeric and match the input."],
            "scope_note": "A toy CSV-import subskill exercise, not the actual Trakt format, JavaScript implementation, or a fix for the selected issue."}


def expected_records(practice):
    return [{"external_id": row["external_id"], "rating": int(row["rating"])} for row in csv.DictReader(io.StringIO(practice["input_csv"]))]


def evaluate(practice, answer):
    expected = expected_records(practice)
    valid_rows = isinstance(answer, list) and len(answer) == len(expected) and all(isinstance(row, dict) for row in answer)
    columns = valid_rows and all(set(row) == {"external_id", "rating"} for row in answer)
    identifiers = valid_rows and all(isinstance(row.get("external_id"), str) and row["external_id"] == correct["external_id"] for row, correct in zip(answer, expected))
    ratings = valid_rows and all(type(row.get("rating")) in (int, float) and row["rating"] == correct["rating"] for row, correct in zip(answer, expected))
    checks = [{"name": name, "passed": bool(value)} for name, value in (
        ("Two record objects", valid_rows), ("Expected columns only", columns),
        ("Identifier strings preserve leading zeros and order", identifiers), ("Expected numeric ratings", ratings))]
    return {"checks": checks, "all_passed": all(row["passed"] for row in checks),
            "measurement": "Structured output on one fixed input; submitted Python was not executed.",
            "independent_ability_established": False}


def flow_file(flow_id):
    return PROJECT / "learning_flows" / check_id(flow_id) / "flow.json"


def get_flow(flow_id):
    flow = load(flow_file(flow_id))
    if flow["flow_id"] != flow_id:
        raise ValueError("Flow identity mismatch.")
    return flow


def list_flows(review_id):
    check_id(review_id)
    rows = []
    for file in (PROJECT / "learning_flows").glob("*/flow.json"):
        value = load(file)
        if value["review_id"] == review_id:
            rows.append({"flow_id": value["flow_id"], "candidate_id": value["candidate_id"], "created_at": value["created_at"]})
    return sorted(rows, key=lambda row: row["created_at"], reverse=True)


def memory(flow, attempt=None):
    payload = {"flow_id": flow["flow_id"]}
    if attempt:
        payload.update(attempt_id=attempt["attempt_id"], origin=attempt["submission_origin"], all_passed=attempt["results"]["all_passed"])
    runner = RUNTIME_ROOT / "meterless-hmem/reference/node_modules/tsx/dist/cli.mjs"
    result = subprocess.run(["node", str(runner), str(RUNTIME_ROOT / "learning_memory.mts"), "remember" if attempt else "recall"],
                            input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", timeout=40, cwd=PROJECT,
                            env={**os.environ, "LEARNING_MEMORY_ROOT": str(PROJECT / ".hmem" / "learning")})
    if result.returncode:
        return {"status": "unavailable", "memories": [], "reason": "H-MEM did not complete; provenance remains unverified."}
    value = json.loads(result.stdout)
    return {"status": "recalled", "checked_at": now(), **value}


def recommendation(flow, recalled):
    attempts = flow["attempts"]
    if not attempts:
        return {"next_action": "complete_csv_import_practice", "reason": "CSV import mapping and tests are not established by the static evidence.", "opportunity_decision": "needs_review", "memory_ids": []}
    latest = attempts[-1]
    assisted = [item for item in recalled.get("memories", []) if item.get("origin") in {"ai_written_reference", "ai_assisted"}]
    ids = [item["id"] for item in assisted]
    if len(attempts) >= flow["max_attempts"]:
        action, reason = "stop_for_user_review", "The three-attempt limit is reached. A person must review the recorded results and assistance."
    elif not latest["results"]["all_passed"]:
        action, reason = "revise_import_result", "Review the failed checks before attempting a contribution."
    elif recalled.get("status") != "recalled":
        action, reason = "review_submission_provenance", "The output passed, but assistance history could not be retrieved."
    elif assisted:
        action, reason = "request_independent_evidence", "H-MEM recalled AI assistance. Passing output does not establish independent ability."
    else:
        action, reason = "review_measured_practice", "The output passed the fixed-input checks. Code quality, authorship and issue readiness still need review."
    return {"next_action": action, "reason": reason, "opportunity_decision": "hold" if flow["availability"] == "hold" else "needs_review", "memory_ids": ids}


def make_draft(flow):
    latest = flow["attempts"][-1]
    passed = sum(row["passed"] for row in latest["results"]["checks"])
    origins = sorted({row["submission_origin"] for row in flow["attempts"]})
    text = (f"I am exploring {flow['candidate_id']} and would like to understand a suitably small next step after reviewing the issue's current availability. "
            f"Limited static analysis of {flow['repository']} found pandas.read_csv calls ({', '.join(flow['evidence_ids'])}); this does not establish my authorship or mastery. "
            f"A related toy CSV-import output was checked: {passed}/4 checks passed. Recorded assistance: {', '.join(origins)}. "
            "These checks did not execute my Python code or establish independent ability, and they do not demonstrate a fix for this issue. "
            "The saved recommendation remains review-required; I am not claiming implementation readiness.")
    return {"draft": text, "draft_status": "private_review_only", "sending_allowed": False, "sent": False,
            "generation_method": "template_from_bound_evidence_and_measured_feedback", "flow_id": flow["flow_id"],
            "candidate_id": flow["candidate_id"], "review_id": flow["review_id"], "evidence_ids": flow["evidence_ids"],
            "review_notes": ["Source observations are static, not proof of authorship or mastery.", "Practice measured submitted data on fixed inputs, not general code correctness.", "Assistance is declared or recorded; independence is not verified.", "Availability is a dated snapshot. Review all claims and current issue context before any outreach."]}


def query_zetaris(flow):
    """Use the actual engine to join this flow's fresh records, not O1 tables."""
    def literal(value):
        encoded = b64encode(str(value).encode("utf-8")).decode("ascii")
        return f"decode(unbase64('{encoded}'), 'UTF-8')"
    evidence_rows = ",".join("(" + ",".join(literal(row[key]) for key in ("id", "file", "code")) + ")" for row in flow["evidence"])
    opportunity = ",".join(literal(flow[key]) for key in ("flow_id", "candidate_id", "url", "availability"))
    sql = f"SELECT e.evidence_id,e.file_path,e.code,o.flow_id,o.candidate_id,o.url,o.availability FROM (VALUES {evidence_rows}) AS e(evidence_id,file_path,code) CROSS JOIN (VALUES ({opportunity})) AS o(flow_id,candidate_id,url,availability)"
    settings = dotenv_values(RUNTIME_ROOT / ".env")
    request = Request("http://localhost:3000/api/proxy/query/sql/start", data=json.dumps({"select": sql, "pageLimit": 20}).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + settings["ZETARIS_API_KEY"], "X-Org-ID": settings["ZETARIS_ORG_ID"]}, method="POST")
    with urlopen(request, timeout=60) as response:
        rows = json.load(response).get("records", [])
    if len(rows) != len(flow["evidence"]) or any(row.get("flow_id") != flow["flow_id"] or row.get("candidate_id") != flow["candidate_id"] for row in rows):
        raise ValueError("Zetaris did not return the expected flow-linked evidence rows.")
    return {"status": "queried", "checked_at": now(), "records": rows,
            "source_kind": "inline_query_values", "note": "Actual Zetaris join of this review's evidence and selected issue. Inputs are query-local values, not newly registered persistent tables."}


def create_flow(review_id, discovery_id, run_id, candidate_id):
    from run_opportunities import load_review
    evidence = load_review(check_id(review_id))
    folder = PROJECT / "discoveries" / check_id(discovery_id) / "runs" / review_id / check_id(run_id)
    status = load(folder / "status_checks.json")
    if status["review_id"] != review_id or status["evidence_sha256"] != fingerprint(evidence):
        raise ValueError("Opportunity run and review evidence differ.")
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(status["checked_at"])).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError("Refresh opportunity statuses before starting a learning flow.")
    candidate = next((row for row in status["candidates"] if row["candidate_id"] == candidate_id), None)
    if not candidate or candidate.get("blockers") or candidate.get("availability") != "needs_review":
        raise ValueError("Choose an unblocked, checked candidate; held or unknown issues cannot start this contribution flow.")
    record = load(folder / "assessments" / (hashlib.sha256(candidate_id.encode()).hexdigest() + ".json"))
    if record["status"] != "assessed":
        raise ValueError("A validated candidate assessment is required first.")
    validate_assessment(json.dumps(record["assessment"]), "stop", candidate, evidence)
    if "csv" not in (candidate["title"] + " " + candidate["body"]).lower():
        raise ValueError("This practice template supports CSV-related opportunities only.")
    key = fingerprint({"review_id": review_id, "candidate_id": candidate_id, "evidence_sha256": fingerprint(evidence), "template": "csv-output-v1"})
    for item in list_flows(review_id):
        previous = get_flow(item["flow_id"])
        if previous["binding_key"] == key or (previous["candidate_id"] == candidate_id and previous["evidence_sha256"] == fingerprint(evidence) and previous.get("practice_template_version", "csv-output-v1") == "csv-output-v1"):
            return previous
    flow_id = uuid.uuid4().hex
    flow = {"flow_id": flow_id, "binding_key": key, "practice_template_version": "csv-output-v1", "created_at": now(), "review_id": review_id,
            "repository": evidence["repository"], "commit_sha": evidence["commit_sha"],
            "discovery_id": discovery_id, "run_id": run_id, "candidate_id": candidate_id, "url": candidate["url"],
            "availability": candidate["availability"], "availability_checked_at": status["checked_at"],
            "assessment": record["assessment"], "assessment_sha256": fingerprint(record["assessment"]),
            "evidence": evidence["evidence"], "evidence_ids": [row["id"] for row in evidence["evidence"]],
            "evidence_sha256": fingerprint(evidence), "active_task": task(flow_id, 1), "attempts": [], "max_attempts": 3,
            "memory": {"status": "not_recalled", "memories": []}, "zetaris": {"status": "pending"}, "outreach": None}
    flow["initial_recommendation"] = recommendation(flow, flow["memory"])
    flow["recommendation"] = flow["initial_recommendation"]
    write_json(flow_file(flow_id), flow)
    return sync_flow(flow_id)


def sync_flow(flow_id):
    flow = get_flow(flow_id)
    try:
        flow["zetaris"] = query_zetaris(flow)
    except (OSError, ValueError, KeyError):
        flow["zetaris"] = {"status": "unavailable", "note": "Zetaris join did not complete. No successful query is claimed; retry when Docker/credentials are ready."}
    write_json(flow_file(flow_id), flow)
    return flow


def submit(flow_id, answer=None, origin="unverified", example=None):
    flow = get_flow(flow_id)
    if len(flow["attempts"]) >= flow["max_attempts"]:
        raise ValueError("The three-attempt limit is reached. Existing state is preserved for human review.")
    practice = flow["active_task"]
    if example is not None and (not isinstance(example, str) or example not in {"incorrect_reference", "correct_reference"}):
        raise ValueError("Unsupported reference example.")
    if isinstance(example, str) and example in {"incorrect_reference", "correct_reference"}:
        answer = expected_records(practice)
        if example == "incorrect_reference":
            answer = [{**row, "external_id": int(row["external_id"])} for row in answer]
        origin = "ai_written_reference"
    if not isinstance(origin, str) or origin not in ORIGINS:
        raise ValueError("Choose a supported assistance declaration.")
    json.dumps(answer, allow_nan=False)
    identity = fingerprint({"task": practice, "answer": answer})
    if any(row["submission_sha256"] == identity for row in flow["attempts"]):
        return flow  # Replaying identical output cannot consume an attempt or erase assistance.
    result = evaluate(practice, answer)
    attempt = {"attempt_id": uuid.uuid4().hex, "practice_id": practice["task_id"], "task": practice, "practice_sha256": fingerprint(practice),
               "submission_sha256": identity, "submission_origin": origin, "origin_verified": example is not None,
               "submitted_at": now(), "answer": answer, "results": result,
               "feedback": "All fixed-input output checks passed; independent code ability remains unverified." if result["all_passed"] else "Some checks failed. Preserve identifier strings with their leading zeros and match numeric ratings."}
    flow["attempts"].append(attempt)
    write_json(flow_file(flow_id), flow)
    try:
        flow["memory"] = memory(flow, attempt)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        flow["memory"] = {"status": "unavailable", "memories": []}
    flow["without_memory_recommendation"] = recommendation(flow, {"status": "recalled", "memories": []})
    flow["recommendation"] = recommendation(flow, flow["memory"])
    if result["all_passed"] and flow["recommendation"]["next_action"] == "request_independent_evidence" and practice["sequence"] == 1 and len(flow["attempts"]) < flow["max_attempts"]:
        flow["active_task"] = task(flow_id, 2)
        flow["followup_reason"] = "Passing assisted output triggered a different input for an independent follow-up; the attempt budget was not reset."
    flow["outreach"] = make_draft(flow)
    attempt["recommendation_after"] = flow["recommendation"]
    attempt["followup_task_id"] = flow["active_task"]["task_id"]
    write_json(flow_file(flow_id), flow)
    return flow
