import hashlib
import json
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype

from independent_submission import load_players

project_folder = Path(__file__).parent
task_file = project_folder / "followup_practice.json"
submission_file = project_folder / "independent_submission.py"

task = json.loads(task_file.read_text(encoding="utf-8"))
expected = task["expected"]

submission_hash = hashlib.sha256(submission_file.read_bytes()).hexdigest()
metadata_file = project_folder / "followup_submission_metadata.json"
metadata = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.exists() else {}
origin = (
    metadata.get("submission_origin", "unverified")
    if metadata.get("submission_sha256") == submission_hash
    else "unverified"
)

results = {
    "practice_id": task["practice_id"],
    "parent_practice_id": task["parent_practice_id"],
    "opportunity_id": task["opportunity_id"],
    "practice_sha256": hashlib.sha256(task_file.read_bytes()).hexdigest(),
    "submission_sha256": hashlib.sha256(
        submission_file.read_bytes()
    ).hexdigest(),
    "submission_origin": origin,
    "independent_ability_established": False,
    "checks": [],
    "error": None,
}


def record_check(name, passed):
    results["checks"].append({
        "name": name,
        "passed": bool(passed),
    })


try:
    frame = load_players(task["input_csv"])

    is_dataframe = isinstance(frame, pd.DataFrame)
    record_check("Returns a pandas DataFrame", is_dataframe)

    if is_dataframe:
        record_check(
            "Has the expected row count",
            len(frame) == expected["row_count"],
        )
        record_check(
            "Preserves identifier strings",
            "player_id" in frame.columns
            and frame["player_id"].tolist() == expected["player_id"],
        )
        record_check(
            "Keeps expected numeric FPS values",
            "fps" in frame.columns
            and is_numeric_dtype(frame["fps"])
            and frame["fps"].tolist() == expected["fps"],
        )

except Exception as error:
    results["error"] = {
        "type": type(error).__name__,
        "message": str(error),
    }

results["all_passed"] = (
    results["error"] is None
    and len(results["checks"]) == 4
    and all(check["passed"] for check in results["checks"])
)

output_file = project_folder / "followup_results.json"
output_file.write_text(
    json.dumps(results, indent=2),
    encoding="utf-8",
)

print(json.dumps(results, indent=2))
print(f"Saved results to {output_file.name}")