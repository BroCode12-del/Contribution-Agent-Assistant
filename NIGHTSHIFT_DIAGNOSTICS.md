# Nightshift assessment deadline — 2026-10-27

## Current source-span run

Run `fb4c2548c4cd4a25b615c058919ae3b0` uses `source_spans_v2`: Nightshift
selects passage IDs and Python materializes exact original quotes/offsets.
Three assessments validated, one assigned issue was held before AI with zero
attempts, and ClipQR timed out on both allowed attempts. A subsequent resume
sent no new model requests. All 82 offline tests passed. Final live readiness
still has one upstream provider-deadline blocker. Earlier runs below are
history, not the current candidate counts. The unsent support draft contains
correlated Nightshift request IDs; no credentials are included.

## Later verification: live assessments demonstrated

The original greeting was insufficient as a health check: Nightshift's
canonical receipt showed an exact cache hit. `test_meterless.py` now asks
for a unique nonce, supplies a 4096-token completion budget (including
reasoning), requires a complete matching response, and rejects cached or
unknown-cache-origin responses. The strengthened check passed on
2026-10-27 with `from_cache: false` and the NVIDIA Nemotron 3.5 Lightning
route confirmed by the Runtime response.

A fresh status/assessment run `cf544e87d6cb48d1846514962b6f1ab1` checked
all five issues. Three AI assessments passed schema, exact-quote, and
citation validation. The CSV-import assessment succeeded on its final
retry with an 8192-token budget; its recorded generation took 47.06 seconds,
finished with stop, and was uncached. Provider responses are still
intermittent: this demonstrates working live requests, not a permanent
provider-side repair or a controlled proof that a single setting fixed it.

The runner now requests a single assessment without tier-split planning,
records model/receipt/cache provenance, retains rejected response text as
diagnostic data only, and normalizes streaming empty-response errors without
echoing arbitrary messages. It also retries brief Windows/OneDrive sharing
failures during atomic JSON replacement; permanent failures preserve the
previous JSON. These changes have offline tests.

Two assessments remain failed/rejected. A retrieved original ClipQR answer
incorrectly listed already-existing privacy behavior as new work; the
validator correctly rejected it. The held lead-export answer altered an
exact source quote and was also correctly rejected. The ClipQR retry
returned a provider error. Neither rejection was promoted to a valid
recommendation or bypassed by rewriting its source quotes. Each candidate
still has at most two attempts in this run.

See `step10_verification.json` for exact IDs and per-candidate provenance.
All 73 combined offline tests passed. Original observations below describe
the earlier failed probes; they are retained as history.

## Earlier observations

The basic `test_meterless.py` check returned `ready`. This establishes that the local Runtime can serve that small request; it does not establish that longer assessments work.

Two bounded diagnostic requests used the existing Runtime URL and Runtime token, requesting `nvidia/nemotron-3.5-lightning-30b-a3b` explicitly. Neither bypassed Nightshift or changed `.env`:

- Full Pontil candidate assessment: `provider_deadline` after 45.25 seconds; see `nightshift_diagnostic.json`.
- Reduced one-requirement assessment: `provider_deadline` after 45.21 seconds; see `nightshift_small_diagnostic.json`.

Installed Nightshift source `engine/js/engine/providers.js` sets `CLOUD_FETCH_DEADLINE_MS = 45_000`. Its OpenAI-compatible provider adapter wraps the upstream fetch in that deadline and clears it when fetch returns. Increasing the application's Python timeout therefore cannot remove this provider-side limit. These observations locate the reported failure at the Runtime/upstream request boundary; they do not establish why the upstream failed to return in time. Requesting the concrete model did not resolve it. A bound Nightshift app profile can override a requested model, so requested model identity alone is not proof of the actual provider selection.

No installed Nightshift code, provider credentials, saved opportunity assessments, or practice decisions were changed by these probes. No successful assessment was fabricated. Step 10's full live assessment verification remains pending.

The runner now supports `--candidate-id` with the existing resume and retry flags, so a later investigation can retry one candidate while keeping the others' saved results and retry counts. The two diagnostic probes are separate from the runner's per-run attempt counts and are recorded above.

Example targeted retry (performs one real AI request if the saved candidate has a retry remaining):

```powershell
python run_opportunities.py --review-id 01cdd3a0db1c4e21b8a850aa5593287d --discovery-id 17a5110ffc9f4d42924e4e7d4291f11b --run-id dea3c275db704e71874eacb3f500ae4c --candidate-id "makingdreamscometrue/pontil#8" --retry-failed
```

Saved status must still be less than 24 hours old. This command has not been run as part of these diagnostics. All 53 repository, outreach, opportunity pipeline, and runner offline tests passed after adding targeted selection. Resolving longer requests needs further Nightshift/provider investigation; a higher Python timeout is not a verified fix.
