"""Firebase Storage helpers for local development and backend use."""

import os
from pathlib import Path
from typing import Any

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import storage
from google.auth.credentials import AnonymousCredentials

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def initialize_firebase() -> None:
    """Initialize Firebase Admin once using the current environment."""
    if firebase_admin._apps:
        return

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")

    if not project_id or not bucket_name:
        raise ValueError("Missing Firebase configuration")

    if project_id == "demo-legal-ai" and not os.getenv("STORAGE_EMULATOR_HOST"):
        raise RuntimeError(
            "Storage Emulator is required for demo-legal-ai; "
            "set STORAGE_EMULATOR_HOST before initializing Firebase"
        )

    options = {
        "projectId": project_id,
        "storageBucket": bucket_name,
    }
    emulator_host = os.getenv("STORAGE_EMULATOR_HOST")
    if emulator_host:
        if not emulator_host.startswith(("http://", "https://")):
            emulator_host = f"http://{emulator_host}"
            # google-cloud-storage uses this value as an HTTP base URL.
            os.environ["STORAGE_EMULATOR_HOST"] = emulator_host
        # The Storage Emulator does not require Google credentials. Anonymous
        # credentials prevent the Admin SDK from attempting ADC discovery.
        firebase_admin.initialize_app(AnonymousCredentials(), options=options)
    else:
        # Production uses Application Default Credentials or Workload Identity.
        firebase_admin.initialize_app(options=options)


def get_storage_bucket() -> Any:
    initialize_firebase()
    return storage.bucket()


def upload_file(
    local_file_path: str,
    destination_path: str,
    content_type: str = "application/octet-stream",
) -> dict[str, str]:
    bucket = get_storage_bucket()
    blob = bucket.blob(destination_path)
    blob.upload_from_filename(local_file_path, content_type=content_type)

    return {
        "file_name": blob.name.split("/")[-1],
        "storage_path": blob.name,
        "bucket": bucket.name,
    }


def download_file(storage_path: str, destination_path: str) -> str:
    bucket = get_storage_bucket()
    bucket.blob(storage_path).download_to_filename(destination_path)
    return destination_path


def delete_file(storage_path: str) -> dict[str, object]:
    bucket = get_storage_bucket()
    bucket.blob(storage_path).delete()
    return {"deleted": True, "storage_path": storage_path}
