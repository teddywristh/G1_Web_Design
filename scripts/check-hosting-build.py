#!/usr/bin/env python3
"""Fail closed if the public Hosting artifact contains unexpected files or keys."""

import re
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "dist/hosting"
expected = {"html": ".html", "css": ".css", "js": ".js"}
public_files = {"index.html", "assets/logo.png"}
private = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb'"private_key"\s*:\s*"|\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}'
)
files = list(root.rglob("*"))
if not (root / "index.html").is_file():
    raise SystemExit("Missing Hosting entry point")
for item in files:
    rel = item.relative_to(root)
    if item.is_symlink() or any(part.startswith(".") for part in rel.parts):
        raise SystemExit(f"Unexpected hidden file or symlink: {rel}")
    if item.is_dir():
        if len(rel.parts) != 1 or rel.name not in {*expected, "assets"}:
            raise SystemExit(f"Unexpected directory: {rel}")
        continue
    if rel.as_posix() not in public_files and (
        len(rel.parts) != 2 or rel.parts[0] not in expected or item.suffix != expected[rel.parts[0]]
    ):
        raise SystemExit(f"Unexpected file in Hosting artifact: {rel}")
    if private.search(item.read_bytes()):
        raise SystemExit(f"Possible private credential in Hosting artifact: {rel}")
for directory in expected:
    if not any((root / directory).glob("*" + expected[directory])):
        raise SystemExit(f"Missing Hosting assets in {directory}")
logo = root / "assets/logo.png"
if not logo.is_file() or not logo.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
    raise SystemExit("Missing or invalid Hosting logo")
print("Hosting artifact checks passed")
