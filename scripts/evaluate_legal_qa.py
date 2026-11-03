#!/usr/bin/env python3
"""Score recorded /rag/ask responses against a frozen gold manifest.

The manifest is a JSON object {"cases": [...]} where each case has id, split,
required_evidence, expected_status and optional forbidden_evidence. Predictions
are a JSON object {case_id: response}. No paid API is called here.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))

from app.evaluation.metrics import score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("-k", type=int, default=20)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    predictions = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    cases = [case for case in manifest["cases"] if case["split"] == args.split]
    print(json.dumps(score(cases, predictions, args.k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
