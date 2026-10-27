# Third-party components and public source evidence

The project uses the official Meterless H-MEM reference implementation,
version 0.1.0, under Apache-2.0. Its source is included under
`meterless-hmem/reference/src/`; preserve `meterless-hmem/LICENSE` and the
upstream reference README/package metadata. Upstream:
https://github.com/Meterless/Meterless/tree/main/engines/hmem

Python and npm dependencies retain their upstream licenses when installed.
Their dependency directories are not included in the source submission.

The saved review metadata identifies public GitHub files and pinned commits.
Downloaded third-party Python source directories are excluded from the
submission and Git tracking. `restore_review_sources.py` can re-fetch the
public source at the saved commit and verify its fingerprints locally.
The short evidence excerpts retain file/line provenance and do not establish
the contributor's authorship or mastery.

Nightshift and Zetaris are external sponsor services. Their installers,
Docker images, credentials and licenses are not redistributed in this project.
