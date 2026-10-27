import json
import hashlib
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype

from practice_submission import load_players

project_folder = Path(__file__).parent

practice = json.loads(
    (project_folder / "practice.json").read_text(encoding="utf-8")
)

submission_hash = hashlib.sha256(
    (project_folder / "practice_submission.py").read_bytes()
).hexdigest()
practice_hash = hashlib.sha256(
    (project_folder / "practice.json").read_bytes()
).hexdigest()
metadata_file = project_folder / "submission_metadata.json"
metadata = json.loads(metadata_file.read_text(encoding="utf-8")) if metadata_file.exists() else {}
origin = (
    metadata.get("submission_origin", "unknown")
    if metadata.get("submission_sha256") == submission_hash
    else "unknown"
)

results = {
    "practice_id": practice["practice_id"],
    "submission_sha256": submission_hash,
    "practice_sha256": practice_hash,
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
    frame = load_players(practice["input_csv"])

    is_dataframe = isinstance(frame, pd.DataFrame)
    record_check("Returns a pandas DataFrame", is_dataframe)

    if is_dataframe:
        record_check("Has two rows", len(frame) == 2)

        has_ids = "player_id" in frame.columns
        record_check(
            "Preserves identifier strings",
            has_ids and frame["player_id"].tolist() == ["001", "002"],
        )

        has_fps = "fps" in frame.columns
        record_check(
            "Keeps expected numeric FPS values",
            has_fps
            and is_numeric_dtype(frame["fps"])
            and frame["fps"].tolist() == [120, 85],
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

output_file = project_folder / "practice_results.json"
output_file.write_text(
    json.dumps(results, indent=2),
    encoding="utf-8",
)

print(json.dumps(results, indent=2))
print(f"Saved results to {output_file.name}")