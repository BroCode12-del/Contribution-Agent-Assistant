# Nightshift provider support note — draft only

Not sent. No credentials, private memory, or full prompts are included.

- Nightshift installed version: 1.2.1 (confirmed by its CLI).
- App: student-contribution-demo; Runtime loopback chat-completions API.
- Actual successful route: nvidia/nemotron-3.5-lightning-30b-a3b.
- Request shape: streaming, max_tokens 8192, meterless-tier-split off.
- Three other candidate assessments succeeded uncached in the current run.
- https://github.com/MojeZcg/ClipQR/issues/40 timed out on both permitted requests with provider_deadline. Its retry budget is exhausted.
- Installed providers.js sets CLOUD_FETCH_DEADLINE_MS = 45_000 around upstream fetch. Increasing the Python read timeout does not override that timer.
- The project now supplies exact numbered source passages and materializes quotes itself; source-format validation failures are distinct from this transport deadline.

Nightshift request IDs correlated to the final failed attempt by its saved start time:

Please confirm whether this build has a supported per-app/provider deadline override or a supported way to set Nemotron thinking controls through the Runtime chat API. Is there a recommended update for delayed upstream headers? No installed Runtime source has been patched.
