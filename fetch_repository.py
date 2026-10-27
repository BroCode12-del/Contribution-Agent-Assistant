import json
from repository_download import download_selected
from pathlib import Path
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from urllib.parse import quote

repository_url = input("Public GitHub repository URL: ").strip()
parsed = urlparse(repository_url)

parts = parsed.path.strip("/").split("/")

if (
    parsed.scheme != "https"
    or parsed.netloc != "github.com"
    or parsed.query
    or parsed.fragment
    or len(parts) != 2
    or not all(parts)
):
    raise SystemExit(
        "Enter a repository URL like https://github.com/owner/repository"
    )

owner, repository = parts

if repository.endswith(".git"):
    repository = repository[:-4]

if not repository or any(
    character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._"
    for character in owner + repository
):
    raise SystemExit("Repository name contains unsupported characters.")

print(f"Owner: {owner}")
print(f"Repository: {repository}")

api_url = f"https://api.github.com/repos/{owner}/{repository}"

request = Request(
    api_url,
    headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "contribution-agent-demo",
    },
)

try:
    with urlopen(request, timeout=30) as response:
        repository_info = json.load(response)

except HTTPError as error:
    if error.code == 404:
        raise SystemExit("Repository not found or not publicly accessible.")
    if error.code in (403, 429):
        raise SystemExit("GitHub refused the request; check access or rate limits.")
    raise SystemExit(f"GitHub returned HTTP {error.code}.")

except (URLError, TimeoutError) as error:
    raise SystemExit(f"Could not reach GitHub: {error}")

if repository_info.get("private") is not False:
    raise SystemExit("Only public repositories are supported.")

print(f"Verified public repository: {repository_info['full_name']}")
print(f"Default branch: {repository_info['default_branch']}")

default_branch = repository_info["default_branch"]
encoded_branch = quote(default_branch, safe="")

commit_url = (
    f"https://api.github.com/repos/{owner}/{repository}"
    f"/commits/{encoded_branch}"
)

commit_request = Request(
    commit_url,
    headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "contribution-agent-demo",
    },
)

try:
    with urlopen(commit_request, timeout=30) as response:
        commit_info = json.load(response)

except HTTPError as error:
    raise SystemExit(f"Could not resolve the branch: HTTP {error.code}.")

except (URLError, TimeoutError) as error:
    raise SystemExit(f"Could not reach GitHub: {error}")

commit_sha = commit_info["sha"]

print(f"Commit selected for review: {commit_sha}")

tree_sha = commit_info["commit"]["tree"]["sha"]

tree_url = (
    f"https://api.github.com/repos/{owner}/{repository}"
    f"/git/trees/{tree_sha}?recursive=1"
)

tree_request = Request(
    tree_url,
    headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "contribution-agent-demo",
    },
)

try:
    with urlopen(tree_request, timeout=30) as response:
        tree_info = json.load(response)

except HTTPError as error:
    raise SystemExit(f"Could not list repository files: HTTP {error.code}.")

except (URLError, TimeoutError) as error:
    raise SystemExit(f"Could not reach GitHub: {error}")

if tree_info.get("truncated") is not False:
    raise SystemExit(
        "GitHub did not confirm a complete file listing. "
        "This demo cannot safely report full coverage."
    )

python_files = sorted(
    [
        entry
        for entry in tree_info["tree"]
        if entry["type"] == "blob"
        and entry["path"].endswith(".py")
        and entry.get("mode") == "100644"
    ],
    key=lambda entry: entry["path"],
)

print(f"\nFound {len(python_files)} regular, non-executable Python files:")

for entry in python_files:
    print(f"- {entry['path']} ({entry.get('size', 'unknown')} bytes)")

MAX_FILES = 20
MAX_FILE_BYTES = 100_000
MAX_TOTAL_BYTES = 1_000_000

selected_files = []
excluded_files = []
selected_bytes = 0

for entry in sorted(tree_info["tree"], key=lambda item: item["path"]):
    if not entry["path"].endswith(".py"):
        continue

    reason = None
    size = entry.get("size")

    if entry["type"] != "blob" or entry.get("mode") != "100644":
        reason = "unsupported_file_type_or_mode"
    elif type(size) is not int or size < 0:
        reason = "unknown_or_invalid_size"
    elif size > MAX_FILE_BYTES:
        reason = "file_size_limit"
    elif len(selected_files) >= MAX_FILES:
        reason = "file_count_limit"
    elif selected_bytes + size > MAX_TOTAL_BYTES:
        reason = "total_size_limit"

    if reason:
        excluded_files.append({
            "file": entry["path"],
            "reason": reason,
        })
    else:
        selected_files.append(entry)
        selected_bytes += size

print(
    f"\nSelected {len(selected_files)} files "
    f"totalling {selected_bytes} bytes."
)
print(f"Excluded Python entries: {len(excluded_files)}")

review_id = uuid.uuid4().hex
project_folder = Path(__file__).parent

review_folder = project_folder / "reviews" / review_id
source_folder = review_folder / "source"
source_folder.mkdir(parents=True, exist_ok=False)

manifest = {
    "review_id": review_id,
    "repository": repository_info["full_name"],
    "commit_sha": commit_sha,
    "tree_sha": tree_sha,
    "status": "selected_not_downloaded",
    "limits": {
        "max_files": MAX_FILES,
        "max_file_bytes": MAX_FILE_BYTES,
        "max_total_bytes": MAX_TOTAL_BYTES,
    },
    "selected_files": selected_files,
    "excluded_files": excluded_files,
    "downloaded_files": [],
    "download_failures": [],
}

manifest_file = review_folder / "manifest.json"
manifest_file.write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8",
)

print(f"Review ID: {review_id}")
print(f"Review folder: {review_folder}")

download_selected(manifest, source_folder, manifest_file)
print(f"Downloaded files: {len(manifest['downloaded_files'])}")
print(f"Download failures: {len(manifest['download_failures'])}")
print(f"Saved source bytes: {manifest['saved_bytes']}")
print("Downloaded source was not imported or executed.")
