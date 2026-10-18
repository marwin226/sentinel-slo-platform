"""Constant-rate synthetic traffic generator (stdlib only) — keeps SLIs populated.

TARGET_URL=http://localhost:8080 RPS=10 python -m app.loadgen
"""

# ruff: noqa: S310, S311  - operator-configured http(s) target; random is for traffic mix, not crypto
from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.error
import urllib.request

SKUS = ["sku-espresso", "sku-grinder", "sku-kettle"]


def _request(base: str) -> int:
    if random.random() < 0.3:
        req = urllib.request.Request(f"{base}/api/v1/products")
    else:
        body = {
            "customer_id": f"c{random.randint(1, 500)}",
            "items": [{"sku": random.choice(SKUS), "quantity": random.randint(1, 3)}],
        }
        req = urllib.request.Request(
            f"{base}/api/v1/checkout",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError):
        return 0


def run(base: str, rps: float, duration: float | None = None) -> None:
    if not base.startswith(("http://", "https://")):
        raise ValueError("TARGET_URL must be an http(s) URL")
    interval = 1.0 / rps
    deadline = time.monotonic() + duration if duration else None
    next_at = time.monotonic()
    while deadline is None or time.monotonic() < deadline:
        threading.Thread(target=_request, args=(base,), daemon=True).start()
        next_at += interval
        time.sleep(max(0.0, next_at - time.monotonic()))


if __name__ == "__main__":
    run(
        os.getenv("TARGET_URL", "http://localhost:8080").rstrip("/"),
        float(os.getenv("RPS", "10")),
        float(os.environ["DURATION_SECONDS"]) if os.getenv("DURATION_SECONDS") else None,
    )
