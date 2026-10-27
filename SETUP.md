# Local setup

This is a Windows-first, single-user hackathon prototype. The demonstrated
machine uses Python 3.14, Node.js 24, Nightshift 1.2.1, and the organiser's
Zetaris Docker distribution. Those are tested versions, not a claim that all
other versions are incompatible. A clean-machine installation has not yet
been verified. No frontend build service or Cursor credits are required.

## 1. Install Python dependencies

Run these commands from the project directory in PowerShell. Using the
virtual environment's executable directly avoids PowerShell activation-policy
problems.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
```

If `py` is unavailable, use your installed Python executable in its place.
`requirements.txt` lists the direct dependencies. `requirements-lock.txt`
captures their tested resolved versions on Windows/Python 3.14. An isolated
virtual environment installed those versions successfully, passed all 100
offline tests, and passed pip's dependency-consistency check. This is not a
clean-machine test of Docker, Nightshift or the complete application setup.
The `openai` package is a compatibility client; app model calls go through
Nightshift rather than directly to OpenAI.

## 2. Configure secrets without overwriting an existing .env

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` locally. Supply the Nightshift **Runtime token**, Zetaris API key,
and Zetaris organisation ID. The optional GitHub token is unnecessary for
unauthenticated public reads but can help with rate limits. Do not paste
credentials into HTML, screenshots, README, or metadata.

In Nightshift, store the NVIDIA provider key in **Setup → Providers**. The
Python app authenticates to Nightshift using its Runtime token; it does not
read NVIDIA's key. Keep the Runtime endpoint on loopback. Start Nightshift
before using AI actions.

```powershell
.\.venv\Scripts\python.exe test_meterless.py
```

Success is JSON with `status: ready`, `from_cache: false`, and the routed model.
The test requests a unique nonce. A cached greeting, empty reply, timeout, or
unknown cache origin is not accepted as provider-health evidence. A passing
small probe does not prove that every larger assessment will succeed.

## 3. Install H-MEM reference dependencies

The project already contains `meterless-hmem/reference/src/index.ts`, the
official H-MEM reference implementation and its Apache-2.0 license. Preserve
that source and license. From the project root:

```powershell
npm.cmd ci --prefix meterless-hmem/reference
node meterless-hmem/reference/node_modules/tsx/dist/cli.mjs hmem_bridge.mts remember
.\.venv\Scripts\python.exe memory_recommendation.py
```

`npm.cmd` avoids the blocked `npm.ps1` launcher on this Windows setup. The
remember command deduplicates the recorded feedback by its source hash and
content. Recall should print `PASS: recalled assistance history changes the
recommendation.` It uses deterministic mock embeddings and local JSON
persistence, not a production embedding service. The local `.hmem` folder is
ignored; initialise it with the command above on a new checkout.

## 4. Start Zetaris separately

Use the organiser-provided Zetaris Docker bundle and its own installation
instructions; that distribution and its credentials are not included here.
Start Docker Desktop and start the platform from the bundle's compose
directory. The demonstrated UI is http://localhost:3000/ and the driver
container is `zetaris-driver-1`. Container names can differ on another install.

```powershell
docker ps --format "table {{.Names}}\t{{.Image}}"
.\.venv\Scripts\python.exe test_zetaris.py
```

The health check must return a record with `one: 1`. This is connectivity
evidence, not evidence that the contribution tables exist.

For the **original O1 sample**, make the JSON files accessible inside the
driver's shared path. Windows files are not automatically visible in Docker.
The commands below copy the original root-level sample, not a new review:

```powershell
docker exec zetaris-driver-1 mkdir -p /home/zetaris/customer-data/shared/contribution-demo
docker cp .\evidence.json zetaris-driver-1:/home/zetaris/customer-data/shared/contribution-demo/evidence.json
docker cp .\opportunity.json zetaris-driver-1:/home/zetaris/customer-data/shared/contribution-demo/opportunity.json
```

Copying replaces files at those paths. On the current demo installation the
database and tables already exist: inspect them instead of recreating them.
Run the following **inspection** statements individually on Zetaris's SQL page:

```sql
SHOW LIGHTNING DATABASES;
SHOW LIGHTNING TABLES CONTRIBUTION_DEMO;
```

On a fresh installation, create only the missing objects:

```sql
CREATE LIGHTNING DATABASE CONTRIBUTION_DEMO;
CREATE LIGHTNING FILESTORE TABLE evidence_report FROM CONTRIBUTION_DEMO
FORMAT JSON OPTIONS (
  path "/home/zetaris/customer-data/shared/contribution-demo/evidence.json",
  multiLine "true"
);
CREATE LIGHTNING FILESTORE TABLE opportunity_record FROM CONTRIBUTION_DEMO
FORMAT JSON OPTIONS (
  path "/home/zetaris/customer-data/shared/contribution-demo/opportunity.json",
  multiLine "true"
);
```

Then run the read-only query in `zetaris_join.sql`; it should return E1–E3
paired with O1 for the original snapshot. Never reinterpret that query as a
readiness score. `match_opportunity.py` performs the same join and then calls
Nightshift and may update the original assessment; do not rerun it merely as
a health check.

The local shared-path rule comes from the tested Docker distribution. General
syntax references: [Zetaris SQL manual](https://kbase.zetaris.com/knowledge/sql-manual)
and the [official Lightning SQL command guide](https://github.com/zetaris/getting-started/blob/main/docs/guides/zetaris-lightning-sql-commands.md).
A new installation of this complete registration procedure still needs a
clean-machine check.

## 5. Open the interface

```powershell
.\.venv\Scripts\python.exe api_server.py
```

Open http://127.0.0.1:8000/ and leave the terminal running. Use one server.
Stop with Ctrl+C before restarting after Python changes. Refresh for HTML,
CSS, or JavaScript changes. Do not open index.html using a file URL.

The UI can read saved results without Nightshift or Docker. Live GitHub/AI
actions require their corresponding services. The original saved O1 example is separately collapsed. For a validated,
unblocked CSV-related issue, Start connected practice creates a new bound
flow. Practice measures submitted JSON results; it does not execute uploaded
Python or establish independent ability. No outreach is sent.

If saved reviews are absent, use the repository URL form to fetch and collect
a fresh review. Its analysis and discovery start empty; the app must not
invent saved results. The broader download path is capped at 20 Python files,
100 KB per file and 1 MB selected total. Downloaded source is never imported
or executed by the collector. Only the deliberately local practice checker
executes a local submission.

## 6. Verify and rehearse

Follow `TESTING.md`. Keep `SUBMISSION_CHECKLIST.md`
visible when deciding readiness. Preparation of these files does not mark
Step 10, the new-opportunity learning integration, recording, or the final
submission complete.

## Restoring saved review sources on a clean checkout

Downloaded third-party source is excluded from Git and the source archive.
To use the supplied saved review for fresh actions, restore its seven files
at the pinned public commit; the helper verifies SHA-256 and Git blob hashes
and never imports or executes source:

```powershell
.\.venv\Scripts\python.exe restore_review_sources.py --review-id 01cdd3a0db1c4e21b8a850aa5593287d
```

It does not overwrite changed existing files. Fetching a new repository through
the interface already downloads its selected sources. Issue snapshots older
than 24 hours require fresh status checks before a new learning flow can start.
