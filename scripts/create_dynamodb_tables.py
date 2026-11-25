#!/usr/bin/env python3
"""Create the QAP DynamoDB Local table.

Idempotent. Retries the port so CI can start amazon/dynamodb-local and call this
immediately. Talks only to DYNAMODB_ENDPOINT. It does not use an AWS account.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

from app.src.settings import get_settings
from app.src.stores.dynamodb_table import ensure_table


def main() -> None:
    settings = get_settings()
    endpoint = (settings.dynamodb_endpoint or "").strip()
    if not endpoint:
        raise SystemExit(
            "DYNAMODB_ENDPOINT is required. This script only provisions DynamoDB Local."
        )

    last_error: Exception | None = None
    for _ in range(30):
        try:
            ensure_table(settings.dynamodb_table)
        except (EndpointConnectionError, BotoCoreError, ClientError, OSError) as exc:
            last_error = exc
            time.sleep(1)
            continue
        print(f"DynamoDB table {settings.dynamodb_table} is ACTIVE at {endpoint}")
        return

    raise SystemExit(f"DynamoDB Local did not become ready at {endpoint}: {last_error}")


if __name__ == "__main__":
    main()
