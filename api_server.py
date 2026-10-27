"""Loopback-only UI. Browser inputs can invoke only fixed project scripts."""
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import learning_flow

PROJECT = Path(__file__).parent
REVIEW_ID = "01cdd3a0db1c4e21b8a850aa5593287d"
JOBS, LOCK = {}, threading.Lock()
SESSION_TOKEN = secrets.token_urlsafe(32)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Invalid review or run ID.")
    return value


def review_data(review_id):
    folder = PROJECT / "reviews" / valid_id(review_id)
    evidence = read_json(folder / "evidence.json")
    manifest = read_json(folder / "manifest.json")
    analysis = read_json(folder / "analysis.json") if (folder / "analysis.json").exists() else None
    if evidence.get("review_id") != review_id or manifest.get("review_id") != review_id:
        raise ValueError("Review identities differ.")
    if any(evidence.get(key) != manifest.get(key) for key in ("repository", "commit_sha")):
        raise ValueError("Manifest and evidence identities differ.")
    if analysis and any(analysis.get(key) != evidence.get(key) for key in ("review_id", "repository", "commit_sha")):
        raise ValueError("Analysis and evidence identities differ.")
    runs = sorted((PROJECT / "discoveries").glob(f"*/runs/{review_id}/*/ranking.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    ranking = read_json(runs[0]) if runs else None
    if ranking and any(ranking.get(key) != evidence.get(key) for key in ("review_id", "repository", "commit_sha")):
        raise ValueError("Opportunity run and evidence identities differ.")
    return {"source": "saved_analysis", "review_id": review_id, "repository": evidence["repository"],
            "commit_sha": evidence["commit_sha"], "analysis": analysis, "evidence": evidence["evidence"],
            "coverage": {key: evidence.get(key) for key in ("all_python_files_parsed", "skipped_files", "excluded_files", "download_failures", "coverage_note")},
            "ranking": ranking}


def review_list():
    rows = []
    for path in (PROJECT / "reviews").glob("*/manifest.json"):
        try:
            value = read_json(path)
            valid_id(path.parent.name)
            if (path.parent / "evidence.json").exists():
                rows.append({"review_id": path.parent.name, "repository": value["repository"], "commit_sha": value["commit_sha"]})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(rows, key=lambda row: (row["repository"], row["review_id"]))


def demo_data():
    names = {"opportunity": "opportunity.json", "assessment": "match_assessment.json", "practice": "practice.json",
             "results": "practice_results.json", "followup": "followup_practice.json", "followup_results": "followup_results.json",
             "feedback": "practice_feedback.json", "state": "agent_state.json", "outreach": "outreach_draft.json"}
    return {"scope": "Original O1 demo only; separate from the selected repository and new discoveries.",
            **{key: read_json(PROJECT / name) if (PROJECT / name).exists() else None for key, name in names.items()}}


def run_script(script, args=(), input_text="", timeout=240):
    with tempfile.TemporaryFile(mode="w+b") as log:
        result = subprocess.run([sys.executable, "-X", "utf8", str(PROJECT / script), *args],
                                input=input_text.encode("utf-8"), stdout=log, stderr=log, cwd=PROJECT,
                                timeout=timeout, env={**os.environ, "PYTHONUTF8": "1"})
        log.seek(0)
        output = log.read(1_000_000).decode("utf-8", errors="replace")
    if result.returncode:
        if "provider_deadline" in output or "empty_response" in output:
            raise ValueError("Nightshift did not return an assessment. Saved results are preserved; retry later.")
        raise ValueError(f"{script} did not complete. Check local setup, network access, and input; no success is claimed.")
    return output


def action_worker(job_id, payload):
    def update(**values):
        with LOCK:
            JOBS[job_id].update(values)
    try:
        action, result = payload["action"], {}
        if action == "fetch":
            output = run_script("fetch_repository.py", input_text=payload["url"] + "\n", timeout=300)
            match = re.search(r"Review ID: ([a-f0-9]{32})", output)
            if not match:
                raise ValueError("Download did not produce a review ID.")
            review_id = match.group(1)
            update(message="Collecting static evidence; downloaded code is not executed.", review_id=review_id)
            run_script("collect_repository.py", input_text=review_id + "\n", timeout=40)
            result = {"review_id": review_id, "message": "Repository fetched and evidence collected. Run AI analysis when ready."}
        elif action == "analyse":
            run_script("analyse_repository.py", input_text=payload["review_id"] + "\n", timeout=200)
            result = {"review_id": payload["review_id"], "message": "Analysis saved. Structure and IDs checked; claims still need review."}
        elif action == "discover":
            run_script("run_opportunities.py", ["--review-id", payload["review_id"], "--no-ai"], timeout=600)
            result = {"review_id": payload["review_id"], "message": "Issue search and status checks saved. AI assessments have not been requested."}
        elif action == "assess":
            args = ["--review-id", payload["review_id"], "--discovery-id", payload["discovery_id"], "--run-id", payload["run_id"], "--candidate-id", payload["candidate_id"], "--retry-failed"]
            run_script("run_opportunities.py", args, timeout=240)
            ranking = review_data(payload["review_id"])["ranking"]
            row = next(row for row in ranking["candidates"] if row["candidate_id"] == payload["candidate_id"])
            result = {"review_id": payload["review_id"], "assessment_status": row["assessment_status"], "message": "Candidate status: " + row["assessment_status"] + ". Failures remain visible; retries are capped."}
        elif action == "memory":
            output = run_script("memory_recommendation.py", timeout=50)
            comparison, _ = json.JSONDecoder().raw_decode(output.lstrip())
            result = {"comparison": comparison, "message": "H-MEM recalled assistance history. O1's practice limit is unchanged."}
        elif action == "zetaris":
            value = json.loads(run_script("test_zetaris.py", timeout=75))
            if not isinstance(value, dict) or not any(str(row.get("one")) == "1" for row in value.get("records", [])):
                raise ValueError("Zetaris did not return the expected SELECT 1 result.")
            result = {"message": "Zetaris returned SELECT 1. The original join is in match_opportunity.py; new discoveries are not registered automatically."}
        elif action == "start_learning":
            flow = learning_flow.create_flow(payload["review_id"], payload["discovery_id"], payload["run_id"], payload["candidate_id"])
            result = {"review_id": flow["review_id"], "flow_id": flow["flow_id"], "message": "Connected practice is ready. This opportunity, evidence, feedback and draft share the same flow ID. Zetaris: " + flow["zetaris"]["status"]}
        elif action in {"submit_learning", "reference_learning"}:
            flow = learning_flow.submit(payload["flow_id"], payload.get("answer"), payload.get("origin", "unverified"), payload.get("example") if action == "reference_learning" else None)
            result = {"review_id": flow["review_id"], "flow_id": flow["flow_id"], "message": "Practice checked. Next action: " + flow["recommendation"]["next_action"] + ". No independent ability or issue readiness is inferred."}
        elif action == "sync_learning":
            flow = learning_flow.sync_flow(payload["flow_id"])
            result = {"review_id": flow["review_id"], "flow_id": flow["flow_id"], "message": "Selected flow's Zetaris join: " + flow["zetaris"]["status"]}
        update(status="failed" if result.get("assessment_status") == "failed" else "complete", result=result, message=result.get("message", "Complete."))
    except subprocess.TimeoutExpired:
        update(status="failed", message="The action reached its time limit. Existing saved results remain available.")
    except (ValueError, OSError, KeyError, StopIteration) as error:
        update(status="failed", message=str(error) if isinstance(error, ValueError) else "The action could not complete. Check local setup; no success is claimed.")


def start_action(payload):
    action = payload.get("action")
    if not isinstance(action, str) or action not in {"fetch", "analyse", "discover", "assess", "memory", "zetaris", "start_learning", "submit_learning", "reference_learning", "sync_learning"}:
        raise ValueError("Unknown action.")
    if action == "fetch":
        if not isinstance(payload.get("url"), str) or not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?", payload["url"]):
            raise ValueError("Enter a public repository URL: https://github.com/owner/repository")
    if action in {"submit_learning", "reference_learning", "sync_learning"}:
        learning_flow.get_flow(valid_id(payload.get("flow_id")))
        if action == "reference_learning" and (not isinstance(payload.get("example"), str) or payload["example"] not in {"incorrect_reference", "correct_reference"}):
            raise ValueError("Choose a supported reference example.")
    if action in {"analyse", "discover", "assess", "start_learning"}:
        data = review_data(valid_id(payload.get("review_id")))
        if not data["evidence"]:
            raise ValueError("No supported CSV-reading evidence was collected. This limited demo cannot assess a match from it.")
        if action in {"assess", "start_learning"}:
            ranking = data["ranking"]
            if not ranking or any(payload.get(key) != ranking[key] for key in ("discovery_id", "run_id")):
                raise ValueError("Use the latest saved opportunity run.")
            if payload.get("candidate_id") not in {row["candidate_id"] for row in ranking["candidates"]}:
                raise ValueError("Candidate does not belong to this review's latest run.")
    with LOCK:
        if any(job["status"] == "running" for job in JOBS.values()):
            raise ValueError("An action is already running. Wait for it to finish.")
        if len(JOBS) >= 30:
            JOBS.pop(next(iter(JOBS)))
        job_id = secrets.token_hex(16)
        JOBS[job_id] = {"job_id": job_id, "action": action, "status": "running", "message": "Working…"}
    threading.Thread(target=action_worker, args=(job_id, dict(payload)), daemon=True).start()
    return {"job_id": job_id}


class Handler(BaseHTTPRequestHandler):
    def allowed_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def send_body(self, code, body, content_type="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, value, code=200):
        self.send_body(code, json.dumps(value).encode("utf-8"))

    def do_GET(self):
        if not self.allowed_host():
            return self.json_response({"error": "Use localhost or 127.0.0.1."}, 403)
        url = urlsplit(self.path)
        try:
            assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
            if url.path in assets:
                name, kind = assets[url.path]
                return self.send_body(200, (PROJECT / name).read_bytes(), kind)
            if url.path == "/api/session":
                return self.json_response({"token": SESSION_TOKEN})
            if url.path == "/api/reviews":
                return self.json_response({"reviews": review_list(), "default_review_id": REVIEW_ID})
            if url.path == "/api/review":
                return self.json_response(review_data(parse_qs(url.query).get("review_id", [REVIEW_ID])[0]))
            if url.path == "/api/demo":
                return self.json_response(demo_data())
            if url.path == "/api/learning":
                params = parse_qs(url.query)
                review_id = valid_id(params.get("review_id", [REVIEW_ID])[0])
                flows = learning_flow.list_flows(review_id)
                flow_id = params.get("flow_id", [flows[0]["flow_id"] if flows else None])[0]
                flow = learning_flow.get_flow(valid_id(flow_id)) if flow_id else None
                if flow and flow["review_id"] != review_id:
                    raise ValueError("Flow belongs to a different review.")
                return self.json_response({"flows": flows, "flow": flow})
            if url.path.startswith("/api/jobs/"):
                with LOCK:
                    job = dict(JOBS.get(valid_id(url.path.rsplit("/", 1)[-1]), {}))
                return self.json_response(job or {"error": "Job not found. Restart clears job tracking."}, 200 if job else 404)
            self.json_response({"error": "Not found."}, 404)
        except (ValueError, KeyError):
            self.json_response({"error": "Invalid or inconsistent saved data."}, 400)
        except OSError:
            self.json_response({"error": "Saved data unavailable. Fetch a repository or choose another review."}, 404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096 or self.headers.get_content_type() != "application/json":
                raise ValueError("Expected a small JSON request.")
            raw_body = self.rfile.read(length)
        except ValueError:
            return self.json_response({"error": "Expected a small JSON request."}, 400)
        if not self.allowed_host():
            return self.json_response({"error": "Invalid host."}, 403)
        origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if self.headers.get("Origin") not in origins or not secrets.compare_digest(self.headers.get("X-Session-Token", ""), SESSION_TOKEN):
            return self.json_response({"error": "Reload the local app before starting an action."}, 403)
        if self.path != "/api/actions":
            return self.json_response({"error": "Not found."}, 404)
        try:
            payload = json.loads(raw_body)
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
            self.json_response(start_action(payload), 202)
        except (ValueError, KeyError, OSError) as error:
            self.json_response({"error": str(error) if isinstance(error, ValueError) else "Saved data unavailable."}, 400)


class LocalServer(ThreadingHTTPServer):
    # Windows otherwise permits two HTTP servers to share a reused port.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


if __name__ == "__main__":
    print("Contribution Agent: http://127.0.0.1:8000/")
    LocalServer(("127.0.0.1", 8000), Handler).serve_forever()
