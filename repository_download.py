"""Bounded source-file downloads. Never import or execute repository contents."""

import hashlib
import json
import ntpath
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def safe_destination(source_folder, repository_path):
    if not isinstance(repository_path, str) or "\\" in repository_path:
        raise ValueError("unsupported_path")
    parts = repository_path.split("/")
    if any(
        part in ("", ".", "..")
        or part.endswith((" ", "."))
        or ntpath.isreserved(part)
        or any(ord(char) < 32 or char in '<>:"|?*' for char in part)
        for part in parts
    ):
        raise ValueError("unsupported_windows_path")
    root = Path(source_folder).resolve()
    destination = root.joinpath(*parts).resolve()
    if not destination.is_relative_to(root) or destination == root:
        raise ValueError("path_outside_review")
    return destination


def bounded_read(response, byte_limit, on_chunk=None):
    # One extra byte detects an oversized response; rejected bytes are never saved.
    data = bytearray()
    while len(data) <= byte_limit:
        chunk = response.read(min(8192, byte_limit + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if on_chunk is not None:
            on_chunk(len(chunk))
    return bytes(data)


def download_selected(manifest, source_folder, manifest_file, opener=urlopen):
    limits = manifest["limits"]
    selected = manifest["selected_files"]
    if len(selected) > limits["max_files"]:
        raise ValueError("Selection exceeds file count limit.")
    if not re.fullmatch(r"[0-9a-f]{40}", manifest["commit_sha"]):
        raise ValueError("Expected a pinned Git commit SHA.")
    repository = manifest["repository"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository identity.")
    if manifest["downloaded_files"] or manifest["download_failures"]:
        raise ValueError("Use a fresh review for downloads; existing results will not be overwritten.")

    source_folder = Path(source_folder)
    manifest_file = Path(manifest_file)
    transferred_bytes = 0
    saved_bytes = 0
    seen_paths = set()

    def count_chunk(size):
        nonlocal transferred_bytes
        transferred_bytes += size

    def persist():
        manifest["transferred_bytes"] = transferred_bytes
        manifest["saved_bytes"] = saved_bytes
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    manifest["status"] = "downloading"
    persist()
    for entry in selected:
        relative_path = entry["path"]
        created = False
        destination = None
        try:
            destination = safe_destination(source_folder, relative_path)
            if entry.get("type") != "blob" or entry.get("mode") != "100644" or not relative_path.endswith(".py"):
                raise ValueError("unsupported_file_type_or_mode")
            path_key = relative_path.casefold()
            if path_key in seen_paths:
                raise ValueError("case_insensitive_path_collision")
            seen_paths.add(path_key)
            if destination.exists():
                raise ValueError("destination_already_exists")
            expected_size = entry.get("size")
            if type(expected_size) is not int or not 0 <= expected_size <= limits["max_file_bytes"]:
                raise ValueError("invalid_or_oversized_file_metadata")
            remaining = limits["max_total_bytes"] - transferred_bytes
            if remaining <= 0:
                raise ValueError("total_download_limit")

            url = (
                f"https://raw.githubusercontent.com/{repository}/"
                f"{manifest['commit_sha']}/{quote(relative_path, safe='/')}"
            )
            request = Request(url, headers={"User-Agent": "contribution-agent-demo"})
            with opener(request, timeout=30) as response:
                if response.status != 200:
                    raise ValueError(f"unexpected_http_status_{response.status}")
                data = bounded_read(response, min(limits["max_file_bytes"], remaining), count_chunk)
            if len(data) > limits["max_file_bytes"]:
                raise ValueError("actual_file_size_limit")
            if len(data) > remaining:
                raise ValueError("actual_total_size_limit")
            if len(data) != expected_size:
                raise ValueError("downloaded_size_mismatch")
            blob_sha = hashlib.sha1(
                f"blob {len(data)}\0".encode() + data
            ).hexdigest()
            if blob_sha != entry.get("sha"):
                raise ValueError("git_blob_hash_mismatch")

            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                created = True
                output.write(data)
            saved_bytes += len(data)
            manifest["downloaded_files"].append({
                "file": relative_path,
                "bytes": len(data),
                "blob_sha": blob_sha,
                "sha256": hashlib.sha256(data).hexdigest(),
                "source_url": url,
            })
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            if created and destination is not None:
                destination.unlink(missing_ok=True)
            reason = f"http_{error.code}" if isinstance(error, HTTPError) else str(error)
            if isinstance(error, HTTPError):
                error.close()
            manifest["download_failures"].append({"file": relative_path, "reason": reason})
        persist()

    manifest["status"] = (
        "download_finished_with_failures" if manifest["download_failures"]
        else "selected_files_downloaded"
    )
    # This does not claim complete repository or Python analysis coverage.
    persist()
    return manifest
