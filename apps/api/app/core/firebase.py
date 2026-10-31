"""Firebase Admin SDK bootstrap.

The SDK uses Application Default Credentials in deployed environments and a
service-account file only when explicitly configured for local development.
"""

import firebase_admin
from firebase_admin import credentials, firestore, storage

from app.core.config import get_settings


def initialize_firebase() -> dict:
    settings = get_settings()
    if not firebase_admin._apps:
        options = {}
        if settings.firebase_project_id:
            options["projectId"] = settings.firebase_project_id
        if settings.firebase_storage_bucket:
            options["storageBucket"] = settings.firebase_storage_bucket
        cred = (
            credentials.Certificate(settings.google_application_credentials)
            if settings.google_application_credentials
            else credentials.ApplicationDefault()
        )
        firebase_admin.initialize_app(cred, options)

    return {"db": firestore.client(), "storage": storage.bucket()}
