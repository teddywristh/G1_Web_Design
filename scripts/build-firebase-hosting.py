#!/usr/bin/env python3
"""Prepare only the static frontend assets for Firebase Hosting."""

import argparse
import html
import shutil
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "apps/web"
DEST = ROOT / "dist/hosting"
ASSET_DIRS = ("html", "css", "js")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True, help="Public HTTPS origin of the API")
    args = parser.parse_args()
    parsed = urlsplit(args.api_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
        parser.error("--api-url must be a public HTTPS origin without a path")
    origin = args.api_url.rstrip("/")
    content = (SOURCE / "index.html").read_text(encoding="utf-8")
    old = '<meta name="api-base" content="http://127.0.0.1:8000" />'
    if content.count(old) != 1:
        raise SystemExit("Expected exactly one API base meta tag; build aborted")
    for directory in ASSET_DIRS:
        if not (SOURCE / directory).is_dir():
            raise SystemExit(f"Missing frontend directory: {directory}")
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    for directory in ASSET_DIRS:
        shutil.copytree(SOURCE / directory, DEST / directory, ignore=shutil.ignore_patterns(".*", "__pycache__"))
    index = DEST / "index.html"
    index.write_text(content.replace(old, f'<meta name="api-base" content="{html.escape(origin, quote=True)}" />'), encoding="utf-8")
    print(f"Hosting assets prepared in {DEST} for {origin}")


if __name__ == "__main__":
    main()
