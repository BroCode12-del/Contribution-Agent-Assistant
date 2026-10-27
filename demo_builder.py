from pathlib import Path
import ast
import json


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


project_folder = Path(__file__).with_name("sample_project")
evidence = []
skipped_files = []

for source_file in sorted(project_folder.rglob("*.py")):
    print(f"Scanning: {source_file.name}")

    try:
        file_evidence = find_csv_calls(source_file)
    except SyntaxError as error:
        print(
            f"Skipped {source_file.name}: "
            f"syntax error on line {error.lineno}"
        )
        skipped_files.append({
            "file": source_file.relative_to(project_folder).as_posix(),
            "reason": "syntax_error",
            "line": error.lineno
        })
        continue

    for record in file_evidence:
        record["file"] = source_file.relative_to(project_folder).as_posix()

    evidence.extend(file_evidence)

for number, record in enumerate(evidence, start=1):
    record["id"] = f"E{number}"

report = {
    "evidence": evidence,
    "skipped_files": skipped_files,
    "all_python_files_parsed": len(skipped_files) == 0
}

output_file = Path(__file__).with_name("evidence.json")
output_file.write_text(
    json.dumps(report, indent=2),
    encoding="utf-8"
)

print(f"Saved {len(evidence)} records to {output_file.name}")



