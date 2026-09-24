from app.document_store import get_document


def test_owner_can_read_document() -> None:
    assert get_document("alice", "doc-alice")["owner"] == "alice"


def test_other_user_cannot_read_document() -> None:
    assert get_document("mallory", "doc-alice") is None
