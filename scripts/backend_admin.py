#!/usr/bin/env python3
"""Explicit project-targeted admin provisioning and dry-run reconciliation."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))

from app.core.config import get_settings
from app.core.firebase import initialize_firebase
from app.repositories.backend import BackendRepository
from app.services.documents import reconcile
from firebase_admin import auth


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", required=True, help="Must match FIREBASE_PROJECT_ID"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Persist changes; default is dry-run"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("grant-admin")
    admin.add_argument("--uid", required=True)
    sub.add_parser("reconcile")
    args = parser.parse_args()
    settings = get_settings()
    if args.project != settings.firebase_project_id:
        parser.error("--project does not match runtime configuration")
    clients = initialize_firebase()
    repo = BackendRepository(clients["db"])
    if args.command == "reconcile":
        result = reconcile(repo, clients["storage"], dry_run=not args.apply)
        print(json.dumps({"dryRun": not args.apply, **result}))
        return 1 if result["errors"] else 0
    identity = auth.get_user(args.uid)
    if identity.disabled:
        parser.error("Cannot grant admin to disabled Firebase identity")
    profile = repo.get("users", args.uid)
    if not profile:
        parser.error("User must bootstrap their profile before admin provisioning")
    if not profile.get("isActive"):
        parser.error("Cannot grant admin to inactive profile")
    if args.apply:

        def change(current):
            if not current or not current.get("isActive"):
                raise ValueError("Profile missing or disabled")
            return {"role": "admin"} if current.get("role") != "admin" else None

        repo.mutate(
            "users",
            args.uid,
            change,
            actor="operator",
            event="user.admin_granted",
            request_id="admin-cli",
        )
    print(json.dumps({"dryRun": not args.apply, "uid": args.uid, "role": "admin"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
