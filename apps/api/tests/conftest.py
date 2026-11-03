"""Tests always target a demo project, never developer or production data."""

import os

import pytest

os.environ.update(
    {
        "APP_ENV": "test",
        "FIREBASE_PROJECT_ID": "demo-legal-api",
        "FIREBASE_STORAGE_BUCKET": "demo-legal-api.appspot.com",
        "FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:9099",
        "FIRESTORE_EMULATOR_HOST": "127.0.0.1:8081",
        "STORAGE_EMULATOR_HOST": "http://127.0.0.1:9198",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
        "EMBEDDING_PROVIDER": "openai",
        "OPENROUTER_EMBEDDING_API_KEY": "",
        "OPENROUTER_EMBEDDING_MODEL": "",
        "OFFICIAL_WEB_ENABLED": "false",
        "EMBEDDING_MAX_CHUNKS": "0",
    }
)


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_FIREBASE_INTEGRATION") != "1":
        skip = pytest.mark.skip(reason="Set RUN_FIREBASE_INTEGRATION=1 with all emulators running")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
