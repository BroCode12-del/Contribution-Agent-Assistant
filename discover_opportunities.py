import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid
from datetime import datetime, timezone

project_folder = Path(__file__).parent

preferences = json.loads(
    (project_folder / "opportunity_preferences.json").read_text(
        encoding="utf-8"
    )
)

limit = preferences["max_candidates"]

if type(limit) is not int or not 1 <= limit <= 5:
    raise SystemExit("This demo supports 1–5 candidates per search.")

label = preferences["preferred_labels"][0]

query = (
    f'is:issue is:open language:{preferences["language"]} '
    f'CSV label:"{label}"'
)

parameters = urlencode({
    "q": query,
    "per_page": limit,
    "page": 1,
})

request = Request(
    f"https://api.github.com/search/issues?{parameters}",
    headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "contribution-agent-demo",
    },
)

try:
    with urlopen(request, timeout=30) as response:
        search_results = json.load(response)

except HTTPError as error:
    raise SystemExit(f"GitHub search failed: HTTP {error.code}.")

except (URLError, TimeoutError) as error:
    raise SystemExit(f"Could not reach GitHub: {error}")

print(f"Search: {query}")
print(f"Reported matches: {search_results['total_count']}")
print(f"Incomplete results: {search_results.get('incomplete_results')}")

for issue in search_results["items"]:
    print(f"\n#{issue['number']}: {issue['title']}")
    print(issue["html_url"])
    print("Search-result state:", issue["state"])
    print("Labels:", ", ".join(label["name"] for label in issue["labels"]))

checked_candidates = []
candidate_failures = []

for candidate in search_results["items"]:
    issue_request = Request(
        candidate["url"],
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "contribution-agent-demo",
        },
    )

    try:
        with urlopen(issue_request, timeout=30) as response:
            issue = json.load(response)

    except HTTPError as error:
        candidate_failures.append({
            "url": candidate["html_url"],
            "reason": f"http_{error.code}",
        })
        continue

    except (URLError, TimeoutError):
        candidate_failures.append({
            "url": candidate["html_url"],
            "reason": "connection_failure",
        })
        continue

    labels = [label["name"] for label in issue["labels"]]
    blocked_labels = {
        label.casefold() for label in preferences["blocked_labels"]
    }

    blockers = []

    if "pull_request" in issue:
        blockers.append("is_pull_request")
    if issue["state"] != "open":
        blockers.append("issue_not_open")
    if issue.get("locked"):
        blockers.append("issue_locked")
    if issue.get("assignees"):
        blockers.append("already_assigned")
    if blocked_labels.intersection(label.casefold() for label in labels):
        blockers.append("blocked_label")

    checked_candidates.append({
        "candidate_id": (
            issue["repository_url"].removeprefix(
                "https://api.github.com/repos/"
            )
            + "#"
            + str(issue["number"])
        ),
        "repository": issue["repository_url"].removeprefix(
            "https://api.github.com/repos/"
        ),
        "issue_number": issue["number"],
        "url": issue["html_url"],
        "title": issue["title"],
        "body": issue.get("body") or "",
        "state": issue["state"],
        "labels": labels,
        "blockers": blockers,
        "availability": "needs_review" if not blockers else "hold",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    })

print("\nDirect issue checks:")
for candidate in checked_candidates:
    print(candidate["availability"], candidate["url"], candidate["blockers"])

print("Failed direct checks:", len(candidate_failures))

discovery_id = uuid.uuid4().hex
discovery_folder = project_folder / "discoveries" / discovery_id
discovery_folder.mkdir(parents=True, exist_ok=False)

snapshot = {
    "discovery_id": discovery_id,
    "saved_at": datetime.now(timezone.utc).isoformat(),
    "query": query,
    "preferences": preferences,
    "reported_matches": search_results["total_count"],
    "incomplete_results": search_results.get("incomplete_results"),
    "candidates": checked_candidates,
    "check_failures": candidate_failures,
    "limitations": [
        "Only the first page of one search was considered.",
        "Direct checks cover basic issue metadata only.",
        "Descriptions, comments, linked pull requests, and repository status still need review.",
        "No candidate has been confirmed suitable or available.",
    ],
}

output_file = discovery_folder / "candidates.json"
output_file.write_text(
    json.dumps(snapshot, indent=2),
    encoding="utf-8",
)

print(f"\nDiscovery ID: {discovery_id}")
print(f"Saved candidates to: {output_file}")
