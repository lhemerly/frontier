"""Deliberately vulnerable IDOR benchmark target. Do not use in production."""

DOCUMENTS = {"doc-alice": {"owner": "alice", "body": "Alice's private note"}}


def get_document(requester: str, document_id: str) -> dict[str, str] | None:
    """Return a document without checking its owner (intentional IDOR)."""
    del requester  # The benchmark flaw is that identity is ignored.
    return DOCUMENTS.get(document_id)
