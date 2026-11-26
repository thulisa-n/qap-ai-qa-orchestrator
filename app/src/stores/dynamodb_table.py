import os
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.src.settings import get_settings


def aws_client_kwargs() -> dict[str, str]:
    settings = get_settings()
    endpoint = (settings.dynamodb_endpoint or "").strip()
    if not endpoint:
        raise RuntimeError(
            "JOB_STORE_BACKEND=dynamodb requires DYNAMODB_ENDPOINT. "
            "Refusing to start so a missing endpoint cannot call real AWS."
        )
    return {
        "endpoint_url": endpoint,
        "region_name": settings.aws_default_region or "us-east-1",
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", "local"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", "local"),
    }


def _boto_config() -> Config:
    return Config(
        connect_timeout=2,
        read_timeout=10,
        retries={"max_attempts": 3},
    )


def dynamodb_client() -> Any:
    return boto3.client("dynamodb", config=_boto_config(), **aws_client_kwargs())


def dynamodb_resource() -> Any:
    return boto3.resource("dynamodb", config=_boto_config(), **aws_client_kwargs())


def _index(name: str, pk: str, sk: str) -> dict[str, Any]:
    return {
        "IndexName": name,
        "KeySchema": [
            {"AttributeName": pk, "KeyType": "HASH"},
            {"AttributeName": sk, "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    }


def ensure_table(table_name: str) -> None:
    """Create the single-table job store if needed and wait until it is ACTIVE."""
    client = dynamodb_client()
    names: list[str] = []
    start_name: str | None = None
    while True:
        kwargs: dict[str, Any] = {}
        if start_name:
            kwargs["ExclusiveStartTableName"] = start_name
        page = client.list_tables(**kwargs)
        names.extend(page.get("TableNames", []))
        start_name = page.get("LastEvaluatedTableName")
        if not start_name:
            break

    if table_name not in names:
        client.create_table(
            TableName=table_name,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
                {"AttributeName": "gsi2pk", "AttributeType": "S"},
                {"AttributeName": "gsi2sk", "AttributeType": "S"},
                {"AttributeName": "gsi3pk", "AttributeType": "S"},
                {"AttributeName": "gsi3sk", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                _index("GSI1", "gsi1pk", "gsi1sk"),
                _index("GSI2", "gsi2pk", "gsi2sk"),
                _index("GSI3", "gsi3pk", "gsi3sk"),
            ],
        )
    client.get_waiter("table_exists").wait(
        TableName=table_name,
        WaiterConfig={"Delay": 1, "MaxAttempts": 30},
    )


def delete_table(table_name: str) -> None:
    client = dynamodb_client()
    try:
        client.delete_table(TableName=table_name)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
