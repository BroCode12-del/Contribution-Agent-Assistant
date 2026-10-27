"""Run or resume Step 10 without replacing earlier discovery snapshots."""

import argparse
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from opportunity_pipeline import (
    ASSESSMENT_CONTRACT, ASSESSMENT_INSTRUCTIONS, GitHub, assess_one, assessment_input, check_id,
    discover, fingerprint, now, preferences_checked, refresh_candidate,
    review_order, validate_assessment, write_json,
)
from repository_download import safe_destination


PROJECT = Path(__file__).parent


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_review(review_id):
    folder = PROJECT / "reviews" / check_id(review_id)
    manifest, evidence = read_json(folder / "manifest.json"), read_json(folder / "evidence.json")
    if any(item.get("review_id") != review_id for item in (manifest, evidence)):
        raise ValueError("Review identities differ.")
    for key in ("repository", "commit_sha"):
        if evidence.get(key) != manifest.get(key):
            raise ValueError("Repository or commit identity differs.")
    records = evidence.get("evidence")
    if not isinstance(records, list) or not records:
        raise ValueError("This ranking demo needs collected evidence; empty evidence is not a skill claim.")
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate evidence IDs.")
    downloads = {item["file"]: item for item in manifest["downloaded_files"]}
    for item in downloads.values():
        source = safe_destination(folder / "source", item["file"])
        if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Downloaded source changed; recollect evidence in a new review.")
    for record in records:
        if record.get("file") not in downloads or record.get("verification") != "static_code_only":
            raise ValueError("Evidence is not linked to a verified downloaded source.")
    return evidence


def provider_error(error):
    # Never log keys, URLs with credentials, or the entire request/response body.
    result = {"type": type(error).__name__}
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        detail = body.get("meterless_detail")
        nested = body.get("error")
        if isinstance(nested, dict):
            detail = detail or nested.get("meterless_detail") or nested.get("code")
        allowed_details = {
            "provider_deadline", "provider_error", "api_error", "rate_limit_exceeded",
            "insufficient_quota", "authentication_error", "connection_failure",
            "invalid_api_key", "nvidia_key_missing",
        }
        if isinstance(detail, str) and detail in allowed_details:
            result["detail"] = detail
        # Streaming errors can contain the provider message directly rather
        # than the non-streaming error envelope. Normalize; never echo it.
        for item in (body, nested):
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            if isinstance(message, str) and re.fullmatch(r"[a-zA-Z0-9_./:-]+_empty_response", message):
                result["detail"] = "empty_response"
    if isinstance(error, ValueError):
        result["detail"] = "Response validation failed; no accepted assessment was produced."
        code = getattr(error, "validation_code", None)
        if code in {"invalid_json", "generation_incomplete", "candidate_id_mismatch", "invalid_requirements",
                    "invalid_requirement_statement", "requirement_quote_not_found", "existing_behavior_quote_requires_review",
                    "invalid_gaps", "invalid_review_notes", "invalid_fit", "invalid_fit_statement", "invalid_citations",
                    "invalid_source_span_id", "unknown_source_span_id", "generated_quote_not_allowed", "source_span_mismatch"}:
            result["validation_code"] = code
    return result


def prior_result(review_id, candidate, evidence, key, current_folder):
    """Reuse exact-input successes; retain exhausted failures without new calls."""
    filename = hashlib.sha256(candidate["candidate_id"].encode()).hexdigest() + ".json"
    paths = sorted((PROJECT / "discoveries").glob(f"*/runs/{review_id}/*/assessments/{filename}"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths[:40]:
        if path.parent.parent == current_folder:
            continue
        try:
            value = read_json(path)
            if value.get("input_sha256") != key or value.get("assessment_contract") != ASSESSMENT_CONTRACT or value.get("candidate_id") != candidate["candidate_id"] or value.get("review_id") != review_id:
                continue
            if value.get("status") == "assessed":
                validate_assessment(json.dumps(value["assessment"]), "stop", candidate, evidence)
            elif value.get("status") != "failed" or value.get("attempt_count", 0) < 2:
                continue
            return {**value, "attempt_count": 0 if value["status"] == "assessed" else 2,
                    "application_cache": {"reused": True, "source_run_id": path.parent.parent.name,
                                          "source_attempt_count": value.get("attempt_count", 0),
                                          "note": "Exact assessment input and contract match; no new model request."}}
        except (ValueError, KeyError, OSError):
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-id")
    parser.add_argument("--discovery-id", help="Reuse a candidate list but perform fresh status checks.")
    parser.add_argument("--run-id", help="Resume a saved run (also supply discovery ID).")
    parser.add_argument("--no-ai", action="store_true", help="Inspect discovery and status checks only.")
    parser.add_argument("--retry-failed", action="store_true", help="One additional attempt per failed candidate; maximum two total.")
    parser.add_argument("--candidate-id", help="Assess only this candidate; preserve other saved results.")
    args = parser.parse_args()
    review_id = check_id(args.review_id or input("Review ID: ").strip())
    evidence = load_review(review_id)
    preferences = preferences_checked(read_json(PROJECT / "opportunity_preferences.json"))
    load_dotenv(PROJECT / ".env")
    github = GitHub(token=os.environ.get("GITHUB_TOKEN"))

    if args.run_id:
        if not args.discovery_id:
            raise ValueError("Resuming requires --discovery-id.")
        discovery_id = check_id(args.discovery_id)
        run_id = check_id(args.run_id)
        run_folder = PROJECT / "discoveries" / discovery_id / "runs" / review_id / run_id
        status = read_json(run_folder / "status_checks.json")
        if status.get("assessment_contract") != ASSESSMENT_CONTRACT and not args.no_ai:
            raise ValueError("This run uses an earlier assessment contract. Its attempts are preserved. Refresh issue statuses in a new run to use source-span selection; use --no-ai to inspect this run.")
        if status["review_id"] != review_id or status["discovery_id"] != discovery_id or status["evidence_sha256"] != fingerprint(evidence):
            raise ValueError("Run identity or evidence changed; start a fresh run.")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(status["checked_at"])).total_seconds()
        if not 0 <= age <= 86400:
            raise ValueError("Status snapshot is older than 24 hours; start a fresh run to recheck.")
        candidates = status["candidates"]
    else:
        if args.discovery_id:
            discovery_id = check_id(args.discovery_id)
            snapshot = read_json(PROJECT / "discoveries" / discovery_id / "candidates.json")
            if snapshot["discovery_id"] != discovery_id:
                raise ValueError("Discovery identity mismatch.")
            identities = snapshot["candidates"][:preferences["max_candidates"]]
        else:
            discovery_id = uuid.uuid4().hex
            identities, searches, failures = discover(github, preferences)
            snapshot = {"discovery_id": discovery_id, "saved_at": now(), "preferences": preferences,
                        "searches": searches, "search_failures": failures, "candidates": identities,
                        "limitations": ["Two preferred-label CSV queries, first pages only, maximum five unique candidates."]}
            write_json(PROJECT / "discoveries" / discovery_id / "candidates.json", snapshot)
        run_id = uuid.uuid4().hex
        run_folder = PROJECT / "discoveries" / discovery_id / "runs" / review_id / run_id
        candidates = []
        for identity in identities:
            print("Checking status:", identity["candidate_id"], flush=True)
            candidates.append(refresh_candidate(github, identity, preferences))
        status = {"run_id": run_id, "review_id": review_id, "discovery_id": discovery_id,
                  "assessment_contract": ASSESSMENT_CONTRACT,
                  "checked_at": now(), "evidence_sha256": fingerprint(evidence), "candidates": candidates,
                  "github_requests": github.requests}
        write_json(run_folder / "status_checks.json", status)

    print("Discovery ID:", discovery_id, flush=True)
    if args.candidate_id and args.candidate_id not in {row["candidate_id"] for row in candidates}:
        raise ValueError("Selected candidate is not in this run.")
    print("Run ID:", run_id, flush=True)
    print("Run folder:", run_folder, flush=True)
    client = None

    assessments = {}
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        output = run_folder / "assessments" / (hashlib.sha256(candidate_id.encode()).hexdigest() + ".json")
        key = fingerprint({"input": assessment_input(candidate, evidence), "instructions": ASSESSMENT_INSTRUCTIONS})
        previous = read_json(output) if output.exists() else None
        if previous is None:
            previous = prior_result(review_id, candidate, evidence, key, run_folder)
            if previous:
                previous.update(review_id=review_id, discovery_id=discovery_id)
                write_json(output, previous)
        if args.no_ai and previous:
            assessments[candidate_id] = previous
            continue
        if args.candidate_id and candidate_id != args.candidate_id:
            if previous and previous.get("input_sha256") == key:
                assessments[candidate_id] = previous
            else:
                assessments[candidate_id] = {"status": "not_requested"}
            continue
        attempts = previous.get("attempt_count", 0) if previous else 0
        if previous and previous.get("input_sha256") != key:
            raise ValueError("Assessment inputs changed. Previous attempts are preserved; refresh statuses in a new run rather than resetting this candidate's budget.")
        if previous and previous.get("status") == "in_progress":
            previous = {**previous, "status": "failed", "error": {"type": "InterruptedRequest", "detail": "The request was interrupted; its attempt remains counted."}}
            write_json(output, previous)
        if previous and previous.get("input_sha256") == key:
            if previous["status"] == "assessed":
                try:
                    validate_assessment(json.dumps(previous["assessment"]), "stop", candidate, evidence)
                    assessments[candidate_id] = previous
                    print("Reusing checked assessment:", candidate_id, flush=True)
                    continue
                except ValueError:
                    previous = None
            elif previous["status"] == "failed" and (not args.retry_failed or attempts >= 2):
                assessments[candidate_id] = previous
                print("Keeping recorded failure (no automatic retry):", candidate_id, flush=True)
                continue
            elif previous["status"] == "held":
                assessments[candidate_id] = previous
                print("Keeping recorded hold (no AI request):", candidate_id, flush=True)
                continue
        result = {"candidate_id": candidate_id, "input_sha256": key, "attempt_count": attempts,
                  "assessment_contract": ASSESSMENT_CONTRACT,
                  "review_id": review_id, "discovery_id": discovery_id, "created_at": now(),
                  "human_review_required": True}
        if candidate.get("blockers") or candidate.get("availability") == "hold":
            result.update(status="held", availability_decision="hold", hold_reasons=candidate.get("blockers", []))
        elif candidate.get("availability") == "unknown":
            result.update(status="not_assessed", error={"type": "StatusUnverified"})
        elif not candidate.get("body"):
            result.update(status="not_assessed", error={"type": "MissingIssueBody"})
        elif args.no_ai:
            result.update(status="not_requested")
        elif attempts >= 2:
            result.update(status="failed", error={"type": "RetryLimit", "detail": "The two-attempt limit has been reached; no new request was sent."})
        else:
            print("Assessing:", candidate_id, flush=True)
            result["attempt_count"] += 1
            result["status"] = "in_progress"
            write_json(output, result)
            try:
                if client is None:
                    from openai import OpenAI
                    client = OpenAI(
                        base_url=os.environ["METERLESS_BASE_URL"], api_key=os.environ["METERLESS_RUNTIME_TOKEN"],
                        default_headers={
                            "meterless-app": "student-contribution-demo", "meterless-scope": "user",
                            # One bounded assessment needs no separate planning phase.
                            "meterless-tier-split": "off",
                        },
                        timeout=90, max_retries=0,
                    )
                result["generation"] = {"requested_model": os.environ["METERLESS_MODEL"], "tier_split": False, "max_tokens": 8192}
                result.update(status="assessed", assessment=assess_one(client, os.environ["METERLESS_MODEL"], candidate, evidence, provenance=result["generation"]))
                print("Validated:", candidate_id, flush=True)
            except Exception as error:
                result.update(status="failed", error=provider_error(error))
                if hasattr(error, "response_text"):
                    # Diagnostic data only; never rendered as an accepted assessment.
                    result["unvalidated_response"] = error.response_text[:100_000]
                print("Assessment failed:", candidate_id, result["error"], flush=True)
        write_json(output, result)
        assessments[candidate_id] = result
        # Checkpoint the review order after every candidate, including failures.
        save_ranking(run_folder, evidence, status, candidates, assessments)
    ranking = save_ranking(run_folder, evidence, status, candidates, assessments)
    for row in ranking["candidates"]:
        print(f"{row['review_priority']}. {row['candidate_id']} | {row['group']} | {row['topic_relation']} | {row['assessment_status']}")
    print("Saved:", run_folder / "ranking.json")
    print("This is an ordering for human investigation, not a claim of suitability or permission to start.")


def save_ranking(folder, evidence, status, candidates, assessments):
    value = {
        "review_id": evidence["review_id"], "repository": evidence["repository"], "commit_sha": evidence["commit_sha"],
        "discovery_id": status["discovery_id"], "run_id": status["run_id"], "status_checked_at": status["checked_at"],
        "ranking_method": "known blockers/status first; validated assessment presence second; CSV-reading title overlap third; candidate ID breaks ties",
        "candidates": review_order(candidates, assessments, evidence),
        "assessment_failures": sum(row.get("status") == "failed" for row in assessments.values()),
        "status": "no_candidates" if not candidates else "partial_assessments" if any(row.get("status") not in {"assessed", "held"} for row in assessments.values()) or len(assessments) < len(candidates) else "review_complete_with_holds" if any(row.get("status") == "held" for row in assessments.values()) else "assessed_needs_human_review",
        "assessment_contract": status.get("assessment_contract", "legacy"),
        "held_without_ai": sum(row.get("status") == "held" for row in assessments.values()),
        "limitations": [
            "Ranking is relative review priority among a small search sample, not a skill score or best-job prediction.",
            "Exact quotes and citation IDs are checked; their interpretation is not automatically proven.",
            "CSV reading does not demonstrate writing, JavaScript, GUI development, tests, or debugging ability.",
            "Status is a dated snapshot, not guaranteed availability. Check context_complete, pagination, and failures.",
            "Timeline references are not proof of a closing PR; open references conservatively trigger review holds.",
            "Code evidence is static and does not establish authorship or mastery. AI-written practice is not independent evidence.",
            "This runner does not alter prior O1 decisions, practice limits, outreach, or Zetaris records.",
        ],
    }
    write_json(folder / "ranking.json", value)
    return value


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(f"Step 10 could not complete: {type(error).__name__}: {error}")
