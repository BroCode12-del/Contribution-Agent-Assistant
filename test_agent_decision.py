import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

project_folder = Path(__file__).parent

original_feedback = json.loads(
    (project_folder / "practice_feedback.json").read_text(encoding="utf-8")
)

with tempfile.TemporaryDirectory() as temporary_folder:
    test_folder = Path(temporary_folder)

    shutil.copy2(
        project_folder / "agent_decision.py",
        test_folder / "agent_decision.py",
    )

    def run_case(feedback, expected_action, expected_count):
        (test_folder / "practice_feedback.json").write_text(
            json.dumps(feedback),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [sys.executable, str(test_folder / "agent_decision.py")],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        decision = json.loads(completed.stdout)

        assert decision["next_action"] == expected_action, decision
        assert decision["attempts_used"] == expected_count, decision
        assert decision["opportunity_decision"] == "hold", decision

        print(f"PASS: {expected_action}, attempts={expected_count}")
        return decision

    # First submission: the existing AI-written reference.
    first_decision = run_case(original_feedback, "request_independent_attempt", 1)
    assert first_decision["action_status"] == "waiting_for_submission"
    task_file = test_folder / "followup_practice.json"
    original_task_bytes = task_file.read_bytes()
    original_task_time = task_file.stat().st_mtime_ns
    task = json.loads(original_task_bytes)
    assert task["parent_practice_id"] == original_feedback["practice_id"]
    assert task["expected"]["player_id"] == ["007", "042"]
    assert task["generation_method"] == "fixed_template_selected_by_agent_rule"

    # Reprocessing it must not consume another attempt.
    repeated_decision = run_case(original_feedback, "request_independent_attempt", 1)
    assert repeated_decision == first_decision
    assert task_file.read_bytes() == original_task_bytes
    assert task_file.stat().st_mtime_ns == original_task_time
    print("PASS: follow-up created once and reused while waiting for submission")

    # Synthetic failed submission: testing the rule, not a real attempt.
    failed_feedback = copy.deepcopy(original_feedback)
    results = failed_feedback["observed_results"]
    results["submission_sha256"] = "synthetic-failed-submission-2"
    results["submission_origin"] = "unknown"
    results["all_passed"] = False

    for check in results["checks"]:
        check["passed"] = False

    run_case(failed_feedback, "review_failed_checks", 2)

    # A third distinct submission must trigger the limit.
    third_feedback = copy.deepcopy(failed_feedback)
    third_feedback["observed_results"]["submission_sha256"] = (
        "synthetic-failed-submission-3"
    )

    run_case(third_feedback, "stop_for_user_review", 3)
    assert task_file.read_bytes() == original_task_bytes
    assert task_file.stat().st_mtime_ns == original_task_time
    print("PASS: other decisions and attempt limit do not overwrite the follow-up")

print("All decision tests passed. Real project state was untouched.")
