from unittest.mock import Mock

from app.repositories.document_repository import DocumentRepository


def test_document_repository_get_returns_none_for_missing_document():
    db = Mock()
    snapshot = Mock(exists=False)
    db.collection.return_value.document.return_value.get.return_value = snapshot

    assert DocumentRepository(db).get("missing") is None


def test_document_repository_get_returns_data_for_existing_document():
    db = Mock()
    snapshot = Mock(exists=True)
    snapshot.to_dict.return_value = {"title": "Luật mẫu"}
    db.collection.return_value.document.return_value.get.return_value = snapshot

    assert DocumentRepository(db).get("law-1") == {"title": "Luật mẫu"}
