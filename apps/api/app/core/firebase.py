"""One Firebase initialization path for API, maintenance and legacy helpers."""

import os
from threading import Lock

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.auth.credentials import AnonymousCredentials

from app.core.config import get_settings

_lock = Lock()


class EmulatorCredentials(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


def initialize_firebase() -> dict:
    settings = get_settings()
    with _lock:
        if not firebase_admin._apps:
            if not settings.firebase_project_id or not settings.firebase_storage_bucket:
                raise ValueError("FIREBASE_PROJECT_ID and FIREBASE_STORAGE_BUCKET required")
            for name in (
                "firebase_auth_emulator_host",
                "firestore_emulator_host",
                "storage_emulator_host",
            ):
                value = getattr(settings, name)
                if value:
                    if name == "storage_emulator_host" and not value.startswith(
                        ("http://", "https://")
                    ):
                        value = "http://" + value
                    os.environ[name.upper()] = value
            if settings.firestore_emulator_host:
                cred = EmulatorCredentials()
            elif settings.google_application_credentials:
                cred = credentials.Certificate(settings.google_application_credentials)
            else:
                cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(
                cred,
                {
                    "httpTimeout": 5,
                    "projectId": settings.firebase_project_id,
                    "storageBucket": settings.firebase_storage_bucket,
                },
            )
    return {"db": firestore.client(), "storage": storage.bucket()}
