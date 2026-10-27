# Verification commands and their limits

Run from the project root using the same Python environment as the app.
The commands below do not publish, send outreach, or change credentials.

## Offline regression suite

```powershell
python -m unittest test_repository_download test_repository_review test_outreach_validation test_opportunity_pipeline test_opportunity_runner test_api_server test_nightshift_probe test_learning_flow test_restore_review_sources -v
node --check app.js
python test_agent_decision.py
```

The unittest suite most recently passed 100 tests. It covers bounded downloads,
fingerprints, citation/schema validation, discovery limits and blockers,
interrupted streams, preserved failures, retry caps, atomic writes and brief
Windows sharing failures, local API restrictions, and rejection of cached
health probes. `test_agent_decision.py` separately exercises the decision loop
in a temporary folder; it does not consume real practice attempts.

These are fixture and contract tests, not evidence of successful provider
calls, full clean-install reproducibility, semantic correctness of every AI
claim, or independent learner ability.

Step 12 also installed the pinned dependencies in an isolated Windows/Python
3.14 virtual environment: all 100 tests passed there and `python -m pip check`
reported no broken requirements. The resolved versions are in
`requirements-lock.txt`; the full sponsor-service setup remains unverified
on a clean machine.

## Read-only saved review consistency

```powershell
python check_review.py
```

At the prompt enter `01cdd3a0db1c4e21b8a850aa5593287d` to inspect the original
downloaded review. This checks identity, pinned commit, and citation existence.
It does not prove the claims' meaning. It does not re-query GitHub.

## Live sponsor checks — optional and explicit

```powershell
python test_meterless.py
python test_zetaris.py
python memory_recommendation.py
```

- Nightshift: unique matching reply, normal completion, explicit uncached
  provenance. This spends one bounded inference request. A small probe is
  not a repeatability test for long assessments.
- Zetaris: SELECT 1 confirms connectivity only. Use `zetaris_join.sql` on the
  SQL page to demonstrate the actual original evidence/opportunity join.
- H-MEM: real reference-engine recall changes the recommendation from
  provenance review to requesting independent evidence. The memory access
  counters can change. No practice attempt is added and O1 remains held.

Do not run `check_practice.py`, `check_followup.py`, `agent_decision.py`, or
generation scripts casually during rehearsal: they can replace results or
change state. The UI's learning section is a saved demonstration. If those
actions are needed, record exactly which inputs and origins were used and
preserve the original demo state first.

## Live Step 10 check

```powershell
python run_opportunities.py --review-id 01cdd3a0db1c4e21b8a850aa5593287d --discovery-id 17a5110ffc9f4d42924e4e7d4291f11b --no-ai
```

This creates a new run with fresh issue/repository/comment/timeline checks
but no AI calls. To assess a candidate, use the returned run ID and the
interface or the runner's `--candidate-id` option. A run's saved status must
be less than 24 hours old. Do not keep starting new runs merely to bypass a
candidate's two-attempt budget.

The latest recorded AI run is listed in `step10_verification.json`: five
candidates checked, three validated assessments, one issue held before AI,
and one provider timeout after its two permitted attempts.
All three assessments found no supported implementation fit in the limited
read_csv evidence. This is a valid abstention, not a successful placement.

## Recording checks

Show the saved/live distinction before each section. Show the fresh probe
and actual Zetaris join if claiming them live. Keep credential screens and
.env off the recording. If a provider request fails, show the failure and
label the saved result; do not narrate saved output as a live success.

## Connected-flow live integration check

```powershell
python verify_connected_demo.py
```

This uses the saved validated Nightshift assessment plus real Zetaris and
H-MEM in an isolated learning directory. It verifies failed identifiers,
passing assisted output, a different-input follow-up, recalled provenance,
the three-attempt stop, a correctly bound unsent draft, and unchanged real
practice state. `connected_demo_verification.json` is the result. The test
does not call a model again or establish independent learner ability.
