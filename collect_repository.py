from pathlib import Path
import ast
import json
import hashlib


def find_csv_calls(source_file):
    code = source_file.read_text(encoding="utf-8")
    tree = ast.parse(code)
    pandas_aliases = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name == "pandas":
                    pandas_aliases.add(imported.asname or "pandas")

    lines = code.splitlines()
    evidence = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function = node.func

            if (
                isinstance(function, ast.Attribute)
                and function.attr == "read_csv"
                and isinstance(function.value, ast.Name)
                and function.value.id in pandas_aliases
            ):
                evidence.append({
                    "file": source_file.name,
                    "line": node.lineno,
                    "line_end": node.end_lineno,
                    "code": ast.get_source_segment(code, node),
                    "observation":  "Calls pandas.read_csv to load CSV data",
                    "verification": "static_code_only"
                })

    return evidence


review_id = input("Review ID: ").strip()

if len(review_id) != 32 or any(
    character not in "0123456789abcdef" for character in review_id
):
    raise SystemExit("Expected a 32-character review ID.")

review_folder = Path(__file__).parent / "reviews" / review_id
manifest_file = review_folder / "manifest.json"

if not manifest_file.is_file():
    raise SystemExit("Review manifest not found.")

manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

if manifest["review_id"] != review_id:
    raise SystemExit("Review ID does not match its manifest.")

project_folder = review_folder / "source"

if not project_folder.is_dir():
    raise SystemExit("Downloaded source folder not found.")

downloaded_files = manifest["downloaded_files"]

if not downloaded_files:
    raise SystemExit("No successfully downloaded files to review.")

for record in downloaded_files:
    source_file = project_folder / record["file"]

    if (
        source_file.is_symlink()
        or not source_file.resolve().is_relative_to(project_folder.resolve())
    ):
        raise SystemExit(f"Unsafe source path: {record['file']}")

    try:
        actual_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
    except OSError:
        raise SystemExit(f"Cannot read downloaded file: {record['file']}")

    if actual_hash != record["sha256"]:
        raise SystemExit(
            f"File changed since download: {record['file']}. "
            "Create a new review before analysing modified source."
        )

print(f"Verified {len(downloaded_files)} downloaded file fingerprints.")

evidence = []
skipped_files = []

for record in sorted(downloaded_files, key=lambda item: item["file"]):
    source_file = project_folder / record["file"]
    print(f"Scanning: {record['file']}")

    try:
        file_evidence = find_csv_calls(source_file)

    except SyntaxError as error:
        skipped_files.append({
            "file": record["file"],
            "reason": "syntax_error",
            "line": error.lineno,
        })
        continue

    except (UnicodeError, OSError) as error:
        skipped_files.append({
            "file": record["file"],
            "reason": (
                "encoding_error"
                if isinstance(error, UnicodeError)
                else "file_read_error"
            ),
            "error_type": type(error).__name__,
        })
        continue

    for evidence_record in file_evidence:
        evidence_record["file"] = record["file"]

    evidence.extend(file_evidence)


for number, record in enumerate(evidence, start=1):
    record["id"] = f"E{number}"

report = {
    "evidence": evidence,
    "skipped_files": skipped_files,
    "all_python_files_parsed": len(skipped_files) == 0
}

report["review_id"] = review_id
report["repository"] = manifest["repository"]
report["commit_sha"] = manifest["commit_sha"]
report["excluded_files"] = manifest["excluded_files"]
report["download_failures"] = manifest["download_failures"]
report["coverage_note"] = (
    "Parsing status covers downloaded Python files only, "
    "not every file in the repository."
)

output_file = review_folder / "evidence.json"
output_file.write_text(
    json.dumps(report, indent=2),
    encoding="utf-8"
)

print(f"Saved {len(evidence)} records to {output_file.name}")



