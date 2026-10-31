from app.services.firebase_storage import delete_file, download_file, upload_file


def test_storage_upload_download_delete(tmp_path):
    source = tmp_path / "legal_test.txt"
    downloaded = tmp_path / "downloaded.txt"
    source.write_text("Legal AI Firebase Storage Emulator Test", encoding="utf-8")
    storage_path = "temporary/legal_test.txt"

    result = upload_file(str(source), storage_path, "text/plain")
    assert result["storage_path"] == storage_path

    download_file(storage_path, str(downloaded))
    assert downloaded.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")

    result = delete_file(storage_path)
    assert result == {"deleted": True, "storage_path": storage_path}
