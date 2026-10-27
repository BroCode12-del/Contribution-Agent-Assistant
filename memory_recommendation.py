import json
import subprocess
from pathlib import Path

project_folder = Path(__file__).parent

runner = (
    project_folder
    / "meterless-hmem"
    / "reference"
    / "node_modules"
    / "tsx"
    / "dist"
    / "cli.mjs"
)

completed = subprocess.run(
    ["node", str(runner), str(project_folder / "hmem_bridge.mts"), "recall"],
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=True,
    timeout=30,
)

recalled = json.loads(completed.stdout)


def recommend(memories):
    supporting_ids = []

    for item in memories:
        memory = item["memory"]

        if (
            "Python practice P1:" in memory["content"]
            and "submission_origin=ai_written_reference;" in memory["content"]
            and memory["source"].startswith("practice_feedback.json#")
        ):
            supporting_ids.append(memory["id"])

    if supporting_ids:
        action = "request_independent_evidence"
        reason = "Recalled history identifies an AI-written reference solution."
    else:
        action = "review_submission_provenance"
        reason = "No relevant AI-assistance history was retrieved."

    return {
        "next_action": action,
        "reason": reason,
        "memory_ids": supporting_ids,
    }


comparison = {
    "without_memory": recommend([]),
    "with_memory": recommend(recalled["memories"]),
    "retrieval_trace": recalled["trace"],
}

print(json.dumps(comparison, indent=2))

assert comparison["without_memory"]["next_action"] == (
    "review_submission_provenance"
)

assert comparison["with_memory"]["next_action"] == (
    "request_independent_evidence"
)

assert comparison["with_memory"]["memory_ids"]

print("PASS: recalled assistance history changes the recommendation.")