import hashlib
import json
from pathlib import Path

project_folder = Path(__file__).parent

feedback = json.loads(
    (project_folder / "practice_feedback.json").read_text(encoding="utf-8")
)
state_file = project_folder / "agent_state.json"

if state_file.exists():
    state = json.loads(state_file.read_text(encoding="utf-8"))
else:
    state = {
        "practice_id": feedback["practice_id"],
        "max_attempts": 3,
        "seen_submissions": [],
    }

if state["practice_id"] != feedback["practice_id"]:
    raise SystemExit("State belongs to a different practice exercise.")

results = feedback["observed_results"]

followup_file = project_folder / "followup_results.json"
pending = state.get("pending_practice")

if pending and followup_file.exists():
    followup = json.loads(followup_file.read_text(encoding="utf-8"))

    if (
        followup["practice_id"] != pending["practice_id"]
        or followup["parent_practice_id"] != feedback["practice_id"]
        or followup["opportunity_id"] != feedback["opportunity_id"]
    ):
        raise SystemExit("Follow-up result belongs to a different task.")

    task_file = project_folder / pending["file"]
    submission_file = project_folder / "independent_submission.py"

    task_hash = hashlib.sha256(task_file.read_bytes()).hexdigest()
    submission_hash = hashlib.sha256(submission_file.read_bytes()).hexdigest()

    if (
        task_hash != pending["sha256"]
        or followup["practice_sha256"] != task_hash
        or followup["submission_sha256"] != submission_hash
    ):
        raise SystemExit("Follow-up inputs changed. Run its checker again.")

    results = followup

submission_key = (
    results["practice_sha256"] + ":" + results["submission_sha256"]
)

if submission_key not in state["seen_submissions"]:
    state["seen_submissions"].append(submission_key)

attempts_used = len(state["seen_submissions"])

if attempts_used >= state["max_attempts"]:
    next_action = "stop_for_user_review"
    reason = "The practice attempt limit has been reached."
elif results.get("submission_origin") == "ai_written_reference":
    next_action = "request_independent_attempt"
    reason = (
        "The reference solution was AI-written. "
        "Its results do not establish independent learner ability."
    )
elif results.get("all_passed") is not True:
    next_action = "review_failed_checks"
    reason = "The submission has not passed every required check."
else:
    next_action = "review_submission_provenance"
    reason = (
        "The checks passed, but assistance and authorship "
        "must be reviewed before revising ability claims."
    )

decision = {
    "practice_id": feedback["practice_id"],
    "opportunity_id": feedback["opportunity_id"],
    "next_action": next_action,
    "reason": reason,
    "opportunity_decision": feedback["opportunity_decision"],
}
decision["attempts_used"] = attempts_used
decision["max_attempts"] = state["max_attempts"]

if next_action == "request_independent_attempt":
    task_file = project_folder / "followup_practice.json"
    pending = state.get("pending_practice")

    if pending is None:
        task = {
            "practice_id": feedback["practice_id"] + "-independent-1",
            "parent_practice_id": feedback["practice_id"],
            "opportunity_id": feedback["opportunity_id"],
            "trigger_submission": submission_key,
            "generation_method": "fixed_template_selected_by_agent_rule",
            "title": "Independent CSV identifier practice",
            "instructions": (
                "Create independent_submission.py with a function named "
                "load_players(csv_text). Accept CSV text and return a pandas "
                "DataFrame. Preserve player_id values as strings with leading "
                "zeros and keep fps numeric. Attempt it yourself; record any "
                "assistance honestly. This task does not establish independent "
                "ability until a submission and its assistance are reviewed."
            ),
            "input_csv": "player_id,fps\n007,98\n042,144\n",
            "expected": {
                "row_count": 2,
                "player_id": ["007", "042"],
                "fps": [98, 144],
                "fps_numeric": True,
            },
            "submission_file": "independent_submission.py",
            "scope_note": (
                "A related CSV exercise, not a fix for the GitHub issue. "
                "The existing opportunity decision remains unchanged."
            ),
        }
        # Recover a task created before an interrupted state save; never overwrite it.
        if task_file.exists():
            existing = json.loads(task_file.read_text(encoding="utf-8"))
            if existing != task:
                raise SystemExit("Existing follow-up differs; review it before continuing.")
        else:
            with task_file.open("x", encoding="utf-8") as output:
                output.write(json.dumps(task, indent=2))

        pending = {
            "practice_id": task["practice_id"],
            "file": task_file.name,
            "sha256": hashlib.sha256(task_file.read_bytes()).hexdigest(),
        }
        state["pending_practice"] = pending
    else:
        if pending.get("file") != task_file.name or not task_file.exists():
            raise SystemExit("Pending practice is missing or invalid; review state.")
        if hashlib.sha256(task_file.read_bytes()).hexdigest() != pending.get("sha256"):
            raise SystemExit("Pending practice changed; review it before continuing.")

    decision["action_status"] = "waiting_for_submission"
    decision["followup_practice_id"] = pending["practice_id"]
    decision["followup_file"] = pending["file"]

if next_action == "review_failed_checks":
    error = results.get("error")
    failed_checks = [
        check["name"]
        for check in results["checks"]
        if check["passed"] is False
    ]

    if error and error["type"] == "NotImplementedError":
        message = (
            "The function is still a placeholder. "
            "No output checks ran. Implement load_players(csv_text), "
            "then run check_followup.py again."
        )
    elif error:
        message = (
            f"Execution failed with {error['type']}: {error['message']}. "
            "Review the error and rerun the checker after revising."
        )
    else:
        message = "Review these failed checks: " + ", ".join(failed_checks)

    revision_feedback = {
        "practice_id": results["practice_id"],
        "submission_sha256": results["submission_sha256"],
        "message": message,
        "failed_checks": failed_checks,
        "error": error,
        "opportunity_decision": decision["opportunity_decision"],
    }

    feedback_file = project_folder / "revision_feedback.json"
    feedback_file.write_text(
        json.dumps(revision_feedback, indent=2),
        encoding="utf-8",
    )

    decision["action_status"] = "waiting_for_revision"
    decision["feedback_file"] = feedback_file.name
    decision["feedback_message"] = message

state["latest_decision"] = decision

state_file.write_text(
    json.dumps(state, indent=2),
    encoding="utf-8",
)
print(json.dumps(decision, indent=2))
