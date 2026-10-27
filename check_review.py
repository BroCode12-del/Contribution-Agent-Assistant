import json
from pathlib import Path

review_id = input("Review ID: ").strip()

if len(review_id) != 32 or any(
    character not in "0123456789abcdef" for character in review_id
):
    raise SystemExit("Invalid review ID.")

folder = Path(__file__).parent / "reviews" / review_id


def read_json(filename):
    return json.loads((folder / filename).read_text(encoding="utf-8"))


manifest = read_json("manifest.json")
evidence = read_json("evidence.json")
analysis = read_json("analysis.json")

for record in (manifest, evidence, analysis):
    if record["review_id"] != review_id:
        raise SystemExit("Review IDs do not match.")

    if (
        record["repository"] != manifest["repository"]
        or record["commit_sha"] != manifest["commit_sha"]
    ):
        raise SystemExit("Repository or commit does not match.")

valid_ids = {record["id"] for record in evidence["evidence"]}

for observation in analysis["observations"]:
    if set(observation["evidence_ids"]) - valid_ids:
        raise SystemExit("Analysis cites unknown evidence.")

print("PASS: review identity, repository, commit, and citation IDs match.")
