"""Offline checks for draft structure, length, and citation IDs."""

import json


def validate_draft(text, finish_reason, context):
    if finish_reason != "stop":
        raise ValueError("Generation did not finish normally.")

    draft = json.loads(text or "")
    if not isinstance(draft, dict):
        raise ValueError("Expected a JSON object.")
    if draft.get("opportunity_id") != context["opportunity_id"]:
        raise ValueError("Incorrect opportunity ID.")

    message = draft.get("draft")
    if not isinstance(message, str) or not 60 <= len(message.split()) <= 100:
        raise ValueError("Expected a message of 60-100 words.")

    valid_ids = {
        evidence_id
        for item in context["fit"]
        for evidence_id in item["evidence_ids"]
    }
    citations = draft.get("evidence_ids")
    if (
        not isinstance(citations, list)
        or not citations
        or any(not isinstance(item, str) for item in citations)
        or set(citations) - valid_ids
    ):
        raise ValueError("Invalid evidence citations.")

    notes = draft.get("review_notes")
    if (
        not isinstance(notes, list)
        or not notes
        or any(not isinstance(note, str) or not note.strip() for note in notes)
    ):
        raise ValueError("Missing review notes.")
    return draft
