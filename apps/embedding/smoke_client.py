"""Check the running endpoint using only the Python standard library."""

import json
import math
import os
import time
from urllib.request import Request, urlopen

base = os.getenv("EMBEDDING_URL", "http://127.0.0.1:8010").rstrip("/")
headers = {"Content-Type": "application/json"}
if os.getenv("EMBEDDING_API_KEY"):
    headers["Authorization"] = "Bearer " + os.environ["EMBEDDING_API_KEY"]
for kind in ("query", "passage"):
    started = time.monotonic()
    request = Request(
        base + "/v1/embeddings",
        headers=headers,
        data=json.dumps(
            {
                "input": ["Điều kiện đơn phương chấm dứt hợp đồng lao động là gì?"],
                "input_type": kind,
                "dimensions": 1536,
            }
        ).encode(),
    )
    with urlopen(request, timeout=180) as response:
        result = json.load(response)
    vector = result["data"][0]["embedding"]
    assert len(vector) == 1536 and all(math.isfinite(x) for x in vector)
    norm = math.sqrt(sum(x * x for x in vector))
    assert abs(norm - 1) < 1e-5
    print(
        json.dumps(
            {
                "input_type": kind,
                "dimensions": len(vector),
                "norm": norm,
                "latency_seconds": round(time.monotonic() - started, 3),
            }
        )
    )
