import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed

from app.core.local_storage import LocalBucket


def test_local_storage_generation_and_listing(tmp_path):
    bucket = LocalBucket(tmp_path / "objects")
    blob = bucket.blob("pdfs/a.pdf")
    blob.upload_from_string(b"first", if_generation_match=0)
    generation = blob.generation
    with pytest.raises(PreconditionFailed):
        blob.upload_from_string(b"other", if_generation_match=0)
    target = tmp_path / "download"
    blob.download_to_filename(target, if_generation_match=generation)
    assert target.read_bytes() == b"first"
    assert [item.name for item in bucket.list_blobs(prefix="pdfs/")] == ["pdfs/a.pdf"]
    blob.upload_from_string(b"second")
    with pytest.raises(PreconditionFailed):
        blob.delete(if_generation_match=generation)
    blob.delete(if_generation_match=blob.generation)
    with pytest.raises(NotFound):
        blob.reload()


def test_local_storage_rejects_path_traversal(tmp_path):
    bucket = LocalBucket(tmp_path)
    for name in ("../secret", "/etc/passwd", "a/../../secret", ".lock"):
        with pytest.raises(ValueError):
            bucket.blob(name)
