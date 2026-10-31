"""Private PDF storage operations."""

from pathlib import Path
from typing import Any


class StorageService:
    def __init__(self, bucket: Any, max_size_bytes: int = 20 * 1024 * 1024):
        self.bucket = bucket
        self.max_size_bytes = max_size_bytes

    def upload_pdf(self, file_path: str, destination: str) -> str:
        path = Path(file_path)
        if path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are accepted")
        if path.stat().st_size > self.max_size_bytes:
            raise ValueError("PDF exceeds the configured size limit")
        blob = self.bucket.blob(destination)
        blob.upload_from_filename(str(path), content_type="application/pdf")
        return destination

    def download_pdf(self, source: str, destination: str) -> None:
        self.bucket.blob(source).download_to_filename(destination)

    def delete_pdf(self, source: str) -> None:
        self.bucket.blob(source).delete()

    def signed_url(self, source: str, expiration_seconds: int = 900) -> str:
        from datetime import timedelta

        return self.bucket.blob(source).generate_signed_url(expiration=timedelta(seconds=expiration_seconds), method="GET")
