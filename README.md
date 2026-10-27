# Evidence-Grounded Contribution Agent

Hackathon prototype for reviewing Python repository evidence,
assessing open-source opportunities, generating practice, and using
observed results to guide later decisions.

## Start here

- [SETUP.md](SETUP.md): local Python, Nightshift, Zetaris and H-MEM setup.
- [TESTING.md](TESTING.md): offline checks versus optional live service checks.
- [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md): verified work and remaining gates.
- [metadata.json](metadata.json): provisional sponsor metadata, not an organiser-validated schema.

The bounded hackathon path now connects a validated issue to practice, measured
feedback, an H-MEM-informed follow-up, and a private draft. Individual provider
failures remain visible. Review the submission checklist for external service
limitations and the remaining human recording/publication steps.

## Download and run locally

Download the GitHub ZIP and extract it, or clone this repository. Open the
project folder in a terminal; Cursor is optional. The full local prototype
needs Python 3.14, Node.js/npm, Nightshift, and the organiser-provided Zetaris
Docker installation. Windows is the tested platform; a complete fresh-machine
installation has not been verified.

From the project folder in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
npm.cmd ci --prefix meterless-hmem/reference
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` locally with your own Nightshift Runtime token, Zetaris API key,
and organisation ID. NVIDIA's provider key belongs in Nightshift Providers.
The `openai` Python package is a compatible client for Nightshift; these app
requests do not go directly to OpenAI. Never commit `.env` or put credentials
in browser code.

Follow [SETUP.md](SETUP.md) to start and configure Nightshift and Zetaris,
verify their connections, and initialise H-MEM. These services and their
credentials are not bundled here. Start the interface with:

```powershell
.\.venv\Scripts\python.exe api_server.py
```

Open [Contribution Agent](http://127.0.0.1:8000/) and leave the terminal
running. Stop with Ctrl+C before restarting. Python changes require a
restart. Use the server address, not `index.html` as a local file.
Saved results can be viewed without live sponsor services. New AI analysis
needs Nightshift; the evidence join needs Zetaris.

## How to use the interface

1. **Repository:** paste a public GitHub URL and click **Fetch & collect
   evidence**, or select a saved review. Each fetch creates a separate review
   pinned to a commit. Downloaded code is never executed. Choose Python code
   using pandas `read_csv` for this prototype: that is the collector's current
   supported pattern, and other code may produce no evidence.
2. **Evidence:** inspect source locations, detected calls, coverage and
   limitations. Click **Request Nightshift analysis** for cited observations.
   Citation-ID checks do not automatically verify the meaning of each claim.
3. **Opportunities:** click **Search GitHub & check status**, then **Request /
   retry this assessment** on a candidate needing assessment. Read its
   requirements, gaps and blockers. Status is a dated snapshot; review order
   is not a skill score or permission to take an issue. Discovery currently
   focuses on CSV-related open-source contributions.
4. **Practice:** choose **Start connected practice** on a validated, unblocked
   CSV candidate. Submit the requested JSON records and declare assistance
   used. Checks measure output on fixed inputs, not independent coding ability.
   The clearly labeled AI-reference demonstration buttons consume attempts.
5. **Next step:** inspect feedback and the revised recommendation. Meterless
   H-MEM recalls assistance history. An assisted pass can trigger a different
   input for follow-up practice. Each flow has a three-attempt cap; reopening
   it does not reset the budget.
6. **Draft:** review the private outreach text and disclosures for the same
   selected issue. Sending is disabled. The app does not contact maintainers
   or submit anything to GitHub.

In Practice, **Zetaris evidence + opportunity join** shows the selected issue
paired with its repository evidence. This flow queries inline values through
Zetaris; it does not create persistent tables. **Earlier O1 example** is a
separate, collapsed historical demonstration.

Downloaded third-party source and private memory/learning state are excluded
from Git. To reuse the supplied saved review for fresh actions, restore its
verified source files:

```powershell
.\.venv\Scripts\python.exe restore_review_sources.py --review-id 01cdd3a0db1c4e21b8a850aa5593287d
```

Fetching a new repository already downloads its selected files. Issue status
snapshots older than 24 hours require fresh checks before a new flow starts.
New practice state is stored locally rather than supplied in the GitHub ZIP.

If the page cannot load, confirm the server is running and use the address
above. Provider timeouts remain visible; a failed assessment is not a match.
See [SETUP.md](SETUP.md) for detailed setup and [TESTING.md](TESTING.md) for
verification commands.

## Acknowledgements and AI assistance

ChatGPT helped me understand how to use and implement **Nightshift,
Zetaris, and Meterless** in this project. I used it for step-by-step
explanations, integration guidance, debugging, and assistance with code
and documentation. Saved AI-written practice references are labeled as
such; their passing checks do not establish my independent ability.

## Sponsor integrations

- Nightshift is the primary AI provider. NVIDIA Nemotron is reached
  through the configured Runtime endpoint for evidence analysis,
  opportunity assessment, practice generation, and feedback.
- Zetaris registers evidence and opportunity JSON files and queries
  them together. Local Docker setup is required.
- Meterless H-MEM stores practice assistance history and retrieves it
  across processes. Python uses recalled memory to change a learning
  recommendation, citing the memory ID.

## H-MEM feature demonstration

After installing the H-MEM reference dependencies, run from the
project folder:

```powershell
node meterless-hmem/reference/node_modules/tsx/dist/cli.mjs hmem_bridge.mts remember
python memory_recommendation.py
```

Expected result:

```text
PASS: recalled assistance history changes the recommendation.
```

Without recalled assistance history, the rule requests provenance
review. With the stored AI-written-reference history, it requests
independent evidence. This comparison does not reset the practice
attempt limit or remove an opportunity hold.

## Current limitations

- Evidence collection covers selected Python code only.
- Static evidence does not prove execution, correctness, authorship,
  or mastery.
- Citation validation checks reference existence, not claim accuracy.
- Current practice solutions were AI-written references. Passing
  checks do not establish independent learner ability.
- Opportunity availability is a saved snapshot.
- H-MEM uses the official deterministic reference implementation,
  including mock embeddings and local JSON persistence.
- The original memory demonstration uses P1; connected flows also recall
  their own assistance history.
- Public GitHub input now supports bounded downloads of selected Python
  files. This is not an exhaustive whole-repository assessment.
- Bounded opportunity discovery and relative review ordering are implemented
  (see Step 10 below). The local interface is implemented for the scoped
  demo. Integration of new review outputs into downstream Zetaris
  persistent Zetaris tables is not automatic. The selected issue now connects
  to its own practice, feedback, follow-up and private draft; its fresh evidence
  and opportunity are queried together through Zetaris using inline values.
  The complete external-service installation still needs a fresh-machine check.
- Outreach has a private, assistant-edited example saved in
  `outreach_draft.json`; it is unsent and unapproved for sending. The
  generator validates structure, but automatic saving and human review of
  future drafts still need wiring.

## Public GitHub repository review (Step 9)

Run these commands from the project folder using your Python environment
with `python-dotenv` and the OpenAI client installed. Nightshift Runtime
settings belong in `.env`; do not print or commit their values.

```powershell
python fetch_repository.py
python collect_repository.py
python analyse_repository.py
python check_review.py
```

1. Enter a public URL such as
   `https://github.com/BroCode12-del/gaming-fps-prediction` when fetching.
2. Copy the generated review ID. Enter that same ID for each subsequent
   command. Each fetch creates a new review rather than resuming one.
3. Fetching pins the default branch to a commit, lists the tree, and saves
   selected source files under `reviews/<review_id>/source/`. It never
   imports or executes downloaded code.
4. `manifest.json` records identity, selection, exclusions, downloaded
   paths, hashes, and individual download failures.
5. The collector verifies downloaded-file fingerprints, parses only
   manifest-listed files, and writes `evidence.json` in that review folder.
   Syntax and UTF-8 decoding failures are recorded as skipped files.
6. Analysis calls Nightshift, validates the response structure and citation
   IDs, attaches limitations and review identity, and saves the review's
   `analysis.json`. A provider failure is not a successful analysis.
7. `check_review.py` checks matching review IDs, repository, commit, and
   citation existence. It does not verify the meaning of model claims.

Sample-project files and root-level demo evidence and analysis are separate
from these review outputs. Use `(review_id, evidence_id)` together when
referring to evidence across reviews; `E1` alone is not globally unique.

### Selection and coverage

- At most 20 files, 100,000 bytes per file, and 1,000,000 total source
  bytes, with limits checked against actual downloads as well as metadata.
  A bounded one-byte probe detects oversized responses and is never saved.
- Only `.py` blobs with Git mode `100644` are selected. Executable-marked
  Python files, symlinks, and other modes are excluded in this prototype.
- Non-Python files are outside collection scope. A truncated GitHub tree
  listing is rejected. A review with no downloaded files cannot be scanned.
- Windows-incompatible paths, path traversal, and case-colliding selected
  paths are rejected. Size and Git blob hash mismatches are recorded as
  download failures.
- An inaccessible or changed downloaded file stops integrity verification.
  Do not edit the downloaded source and attribute it to the original commit.
- `all_python_files_parsed` describes downloaded files only; inspect
  exclusions, download failures, and skipped files before interpreting it.
- JSON and metadata validation is limited; malformed API responses may
  still surface as errors. Credentials, automatic rate-limit retries, and
  analysis of non-UTF-8 Python files are not implemented for this path.

### Verification

Run the Step 9 regression checks without internet or AI calls:

```powershell
python -m unittest test_repository_download test_repository_review -v
```

The tests use synthetic responses and temporary folders. They check URL
rejection, access/rate-limit/network errors, truncated listings, download
limits and hashes, Windows paths, parsing failures, unlisted-file exclusion,
and rejection of mixed review identities or unknown citations.

The observed live example at commit
`6f8963fc3328d8dc460c77f3460add4703aea79c` downloaded 7 files (23,149 bytes),
produced 3 static `read_csv` observations with no skipped files, and saved
a cited Nightshift analysis. The existing local review ID is
`01cdd3a0db1c4e21b8a850aa5593287d`; a fresh run produces a different ID.

## Opportunity discovery and review ordering (Step 10)

`run_opportunities.py` is the complete Step 10 entry point. The earlier
`discover_opportunities.py` and interactive `assess_candidates.py` remain
available as the small learning steps used to build it.

```powershell
python run_opportunities.py --review-id 01cdd3a0db1c4e21b8a850aa5593287d
```

This uses `opportunity_preferences.json`, searches public issues on the first page for up to
two preferred labels using the CSV topic probe, deduplicates repository and
issue identities, and considers at most five candidates. Other preference
topics are retained as context, not silently treated as satisfied filters.
This is a small search sample, not a comprehensive opportunity market.

For each candidate it fetches the issue, repository status, up to 20 issue
comments, and up to 30 timeline events. Assignments, closed/locked issues,
blocked labels, archived/disabled repositories, possible text restrictions,
and open referenced PRs are retained as conservative review holds. A PR
reference does not prove it closes the issue. Failed checks produce unknown
status, not permission to proceed. Pagination and text truncation are
explicit; even a completed bounded check does not guarantee availability.

Nightshift supplies requirement assessments using streaming. Under
`source_spans_v2`, it selects numbered source passages; Python copies the
exact saved issue text and Unicode character offsets. Generated quote text,
unknown passage IDs, and altered offsets are rejected. The conservative
catalog withholds obvious already-existing/current-behavior sentences; it
is not a semantic requirement extractor. Fit observations must cite IDs in
the selected review. Interpretations still need human review.

Known blockers are held before AI, with zero model attempts. Unknown status
is left unassessed. A provider failure remains a failure; holds do not count
as successful AI assessments.

Outputs are checkpointed under:

```text
discoveries/<discovery_id>/runs/<review_id>/<run_id>/
    status_checks.json
    assessments/<candidate-identity-hash>.json
    ranking.json
```

The ranking is an **order for human investigation**, not an ability score,
job-fit probability, or approval to implement. Known holds rank after
unblocked candidates, unknown status is separate, validated assessment
presence is considered, and simple CSV-reading title overlap is preferred
over writing when the selected evidence contains `pandas.read_csv` calls.
All entries remain review-required and have no confirmed suitability value.
Failed AI assessments remain failed; the runner does not fabricate them.

### Resume, retries, and offline inspection

The runner prints discovery and run IDs. Resume the same run without
repeating accepted model assessments:

```powershell
python run_opportunities.py --review-id REVIEW_ID --discovery-id DISCOVERY_ID --run-id RUN_ID
```

Substitute the printed IDs (without the angle-bracket folder notation).
Failure records are also reused unless `--retry-failed` is explicitly added.
There are at most two AI attempts per candidate in the same run. The attempt
is checkpointed before inference. An interrupted request stays counted and
requires an explicit retry flag; changed inputs cannot reset the budget.
Older-contract runs are inspectable with `--no-ai` but cannot launch new
inference through the updated contract. Their previous records and counts
are preserved; a genuine protocol/status refresh uses a new run.
Resuming rejects changed evidence or a status snapshot older than 24 hours;
omit `--run-id` to perform fresh checks. A new run creates new attempt
budgets; the cap is per run, not a global policy or spending limit.

To refresh statuses for an existing candidate discovery, provide review and
discovery IDs but omit the run ID. To perform discovery/status checks without
AI, add `--no-ai`. To inspect an existing run without internet or model calls,
provide all three IDs and `--no-ai`; its saved status must still be recent.
The output explicitly marks unassessed candidates and partial assessments.

GitHub public requests work without a token. An optional `GITHUB_TOKEN` in
the ignored `.env` can provide authenticated read access, but is not required
or created by this project. A run uses a 45-request GitHub budget, 30-second
network timeouts, and a bounded API response size. Nightshift uses the
existing Runtime token and model; no direct NVIDIA credential is read by the
app. Stream/provider errors are recorded without logging credential values.

### Step 10 verification

```powershell
python -m unittest test_opportunity_pipeline test_opportunity_runner -v
```

These offline tests cover deduplication, limits, failed status checks,
blockers, exact quotes, invented citations, interrupted streams, ranking,
atomic output, safe diagnostics, stale snapshots, resume, and retry caps.
They use fixtures, not invented live opportunities or evidence of user skill.

Step 11 now has a local interface; see below. Step 12 (full submission checks)
is still pending.

### Recorded live run (2026-10-27)

- Review: `01cdd3a0db1c4e21b8a850aa5593287d`
- Discovery: `17a5110ffc9f4d42924e4e7d4291f11b`
- Run: `dea3c275db704e71874eacb3f500ae4c`
- Five direct issue/repository/comment/timeline checks completed. Four
  candidates remained review-required; the assigned lead-export issue was
  held. The run used unauthenticated public GitHub requests.
- All five live Nightshift assessment attempts returned `provider_deadline`.
  Consequently `ranking.json` is marked `partial_assessments`; its review
  order is only deterministic topic triage, with no accepted new AI fit or
  requirement claims. Earlier successful single-candidate snapshots are
  preserved separately.
- Offline resume reused the error records without retrying the provider.
  At that point live multi-candidate AI validation was pending provider
  recovery; the later verification below demonstrates partial recovery.

### Later live verification (2026-10-27)

Run `cf544e87d6cb48d1846514962b6f1ab1` refreshed all five issue statuses
and saved three validated Nightshift assessments, with NVIDIA Nemotron 3.5
Lightning receipt/model provenance. The top review-priority candidate is
the Trakt CSV import issue. None of the three assessments established a
supported implementation fit from the limited read_csv evidence; each
records concrete gaps instead. Two candidates remain failed/rejected,
including the assigned lead-export issue, which remains held. The ranking
correctly remains `partial_assessments`, not an all-success report.

The CSV-import retry completed uncached with an 8192-token budget. The
runner requests no separate tier-split planning phase, preserves its two
attempt cap, records generation provenance, and retains rejected content
only as diagnostic data. `test_meterless.py` now verifies a fresh nonce and
an explicitly uncached response instead of accepting a cached greeting.
Brief Windows/OneDrive replacement locks are retried without discarding
the preceding saved JSON.

Evidence: `step10_verification.json` and `NIGHTSHIFT_DIAGNOSTICS.md`.
Provider reliability remains intermittent. This run demonstrates the live
discovery/assessment/review-order feature, not a permanent upstream fix.
73 combined offline tests passed, including fresh-vs-cached health probes,
provider provenance, rejected outputs, and file-sharing failure handling.

### Current source-span run (2026-10-27)

Run `fb4c2548c4cd4a25b615c058919ae3b0` refreshed the same five issue
statuses under `source_spans_v2`. Three assessments passed exact passage,
quote, offset, citation-ID, schema and completion checks. The assigned lead
export issue was held without an AI call. ClipQR hit `provider_deadline`
on both permitted attempts. The ranking remains `partial_assessments`;
full live reliability is still pending this external failure.

A further resume reused all successes and the hold, kept the exhausted
failure, and sent no new model request. All 82 offline tests passed in the
isolated Python environment. See `step10_verification.json` and the unsent
`NIGHTSHIFT_SUPPORT_DRAFT.md`. These changes did not connect new discoveries
to practice/outreach or complete the final recording/submission gates.

## Local interface (Step 11)

From the project directory, run `python api_server.py`, then open
http://127.0.0.1:8000/ . Keep one server running. Stop it with Ctrl+C before
starting another copy. HTML, styles, and JavaScript changes appear on refresh;
Python changes require restarting the server. Do not open index.html as a
file URL. No additional UI packages or hosted services are required.

The interface supports:

- Fetching a public GitHub repository and collecting bounded, pinned static
  evidence through the existing download/collector scripts.
- Selecting saved reviews and inspecting observations, source locations,
  code, coverage, and limitations.
- Requesting Nightshift analysis, searching/checking GitHub issues without
  AI, and requesting or retrying one candidate assessment at a time.
- Viewing the original O1 practice, measured reference results, feedback,
  capped decision, and honest private outreach draft as an explicitly
  separate saved demonstration.
- Running the real H-MEM recall/recommendation demonstration, and a Zetaris
  SELECT 1 connection check. The latter is a health check, not a replacement
  for the original evidence/opportunity join.

Background actions report progress and errors. Only one action runs at a
time. Refreshing the same browser tab resumes job tracking while the server
is running; restarting the server clears the in-memory queue. Saved JSON
artifacts remain on disk. Nightshift provider deadlines are unresolved and
failures remain visibly unassessed. No automatic provider retries or
fallback-generated assessments are introduced by this interface.

Validated, unblocked CSV-related candidates now offer **Start connected
practice**. Each flow binds review/commit/issue IDs, a fixed practice template,
measured JSON-output checks, H-MEM assistance history, capped follow-ups and
a private draft. The real Zetaris engine joins that flow's evidence and issue
as query-local values; this does not create new persistent tables. The
original O1 example remains separately collapsed. Submitted Python is not
executed by the new checker: it measures returned data on fixed inputs,
not coding ability or independent authorship. Outreach cannot be sent.

The server binds to loopback only. It serves a fixed asset/data allowlist,
checks Host/Origin and a per-process action token, uses no shell for script
execution, and renders untrusted text through textContent. Provider tokens
remain server-side. This is a single-user local prototype, not a production
authentication scheme or a public deployment. A hosted Lovable frontend
cannot use the laptop's loopback services without a separately designed
backend deployment/connection.

Interface checks: `python -m unittest test_api_server -v`.

Browser verification on 2026-10-27: the original analysis, five saved
opportunity statuses/errors, practice checks, feedback, capped decision,
and private draft rendered successfully. Fetch & collect created review
`72d6d1e1bbf14245a7b2b2cc10168950` at the same pinned test commit, with
three evidence records and no fabricated AI analysis. H-MEM recall showed
`review_submission_provenance` changing to `request_independent_evidence`.
The Zetaris button received the expected SELECT 1 result. These checks do
not establish that the currently failing Nightshift assessments work.

The combined repository, outreach, opportunity, interface, and health-probe
suite now passes 100 tests. Step 12's full submission review and demo recording
are pending.

## Secrets

Keep credentials in the Git-ignored .env file. Never include tokens
in documentation, metadata, screenshots, or browser code.

## Connected practice and decision flow

Use `RECORD_NOW.md` for the short working demonstration. The original review
`01cdd3a0db1c4e21b8a850aa5593287d` has a blank, zero-attempt practice flow
for `makingdreamscometrue/pontil#8` on the development machine. On a new
checkout, create it with the Start connected practice button after restoring
the saved source fingerprints and checking snapshot freshness.

`learning_flow.py` validates bindings, grades structured CSV output, preserves
assistance provenance, deduplicates repeats, and caps each flow at three
attempts. Assisted success creates a different-input follow-up. Actual H-MEM
recall changes the next recommendation; a template drafts honest private
outreach from those same bound records. The fixed exercise is a toy CSV
subskill, not the real Trakt input format or a fix for the issue.

`verify_connected_demo.py` runs this entire path in isolated state using
real Zetaris and H-MEM. `connected_demo_verification.json` records the
passing run: lost-zero feedback, assisted pass, new follow-up, memory-driven
revision, matching private draft, and rejection of a fourth attempt. It leaves
real practice state untouched and does not call a model again.

## Exact-input assessment reuse

Fresh status checks can reuse a previous validated assessment only when its
review, candidate, complete assessment input hash and source-span contract
match. Reuse is labeled separately from a new Nightshift call. Exhausted
exact-input failures keep their cap. A fresh check on 2026-10-27 reused the
three successful assessments and the exhausted timeout, with no new inference
requests; the assigned issue remained held before AI.

The full current suite has 100 passing offline tests. The connected UI was
also exercised in isolated state through wrong output, corrected assisted
output, H-MEM recall, a new follow-up and the same-issue private draft.
See THIRD_PARTY_NOTICES.md for the reference engine and source provenance.
