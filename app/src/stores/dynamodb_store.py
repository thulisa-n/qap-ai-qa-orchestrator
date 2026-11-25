import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.src.stores.dynamodb_table import dynamodb_resource
from app.src.stores.models import (
    healing_session_record,
    healing_sessions_from_attempts,
    job_record,
    job_trace,
    utc_now_iso,
)
from app.src.settings import get_settings


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _json_text(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _json_load(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    return json.loads(value)


class DynamoDbJobStore:
    """Single-table DynamoDB adapter. Trace data stays inside the job result."""

    def __init__(self) -> None:
        settings = get_settings()
        self._table_name = settings.dynamodb_table
        self._table = dynamodb_resource().Table(self._table_name)

    def create_job(
        self,
        *,
        job_id: str,
        issue_key: str,
        request_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        created_at = utc_now_iso()
        job = job_record(
            job_id=job_id,
            issue_key=issue_key,
            status="pending",
            created_at=created_at,
            started_at=None,
            completed_at=None,
            result=None,
            request_payload=request_payload,
            error=None,
        )
        self._table.put_item(Item=self._job_item(job))
        return job

    def mark_job_running(self, job_id: str) -> None:
        self._update_job(
            job_id,
            "SET #status = :status, started_at = :started_at, gsi1pk = :gsi1pk",
            {":status": "running", ":started_at": utc_now_iso(), ":gsi1pk": "STATUS#running"},
        )

    def mark_job_succeeded(self, job_id: str, result: dict[str, Any]) -> None:
        self._update_job(
            job_id,
            "SET #status = :status, completed_at = :completed_at, result_json = :result_json, gsi1pk = :gsi1pk REMOVE #error",
            {
                ":status": "succeeded",
                ":completed_at": utc_now_iso(),
                ":result_json": json.dumps(result),
                ":gsi1pk": "STATUS#succeeded",
            },
        )

    def mark_job_failed(self, job_id: str, error: str) -> None:
        self._update_job(
            job_id,
            "SET #status = :status, completed_at = :completed_at, #error = :error, gsi1pk = :gsi1pk",
            {
                ":status": "failed",
                ":completed_at": utc_now_iso(),
                ":error": error,
                ":gsi1pk": "STATUS#failed",
            },
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        response = self._table.get_item(Key={"pk": f"JOB#{job_id}", "sk": "METADATA"})
        item = response.get("Item")
        if not item:
            return None
        return self._job_from_item(item)

    def get_job_trace(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if not job:
            return None
        return job_trace(job)

    def update_job_result(self, job_id: str, result: dict[str, Any]) -> None:
        self._update_job(
            job_id,
            "SET result_json = :result_json",
            {":result_json": json.dumps(result)},
        )

    def list_jobs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        issue_key: str | None = None,
    ) -> list[dict[str, Any]]:
        if status:
            kwargs: dict[str, Any] = {
                "IndexName": "GSI1",
                "KeyConditionExpression": Key("gsi1pk").eq(f"STATUS#{status}"),
                "ScanIndexForward": False,
            }
            if issue_key:
                kwargs["FilterExpression"] = Attr("issue_key").eq(issue_key)
            items = self._query_all(**kwargs)
        elif issue_key:
            items = self._query_all(
                IndexName="GSI2",
                KeyConditionExpression=Key("gsi2pk").eq(f"ISSUE#{issue_key}"),
                ScanIndexForward=False,
            )
        else:
            items = self._scan_all(Attr("entity_type").eq("job"))
            items.sort(key=lambda item: (item.get("created_at") or "", item.get("job_id") or ""), reverse=True)
        return [self._job_from_item(item) for item in items[:limit]]

    def cleanup_jobs(self, *, older_than_days: int = 30, status: str | None = None) -> dict[str, int]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        if status:
            items = self._query_all(
                IndexName="GSI1",
                KeyConditionExpression=Key("gsi1pk").eq(f"STATUS#{status}"),
            )
        else:
            items = self._scan_all(Attr("entity_type").eq("job"))

        to_delete: list[str] = []
        for item in items:
            created_at = item.get("created_at")
            if not created_at:
                continue
            created_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            if created_dt < cutoff:
                to_delete.append(str(item.get("job_id") or str(item["pk"]).removeprefix("JOB#")))

        if to_delete:
            keys: list[dict[str, str]] = []
            for job_id in to_delete:
                keys.append({"pk": f"JOB#{job_id}", "sk": "METADATA"})
                for healing in self._healing_items(job_id):
                    keys.append({"pk": healing["pk"], "sk": healing["sk"]})
            with self._table.batch_writer() as batch:
                for key in keys:
                    batch.delete_item(Key=key)
        return {"deleted": len(to_delete), "evaluated": len(items)}

    def upsert_healing_sessions(
        self,
        *,
        job_id: str,
        issue_key: str,
        attempts: list[dict[str, Any]],
    ) -> None:
        if not attempts:
            return
        sessions = healing_sessions_from_attempts(
            job_id=job_id,
            issue_key=issue_key,
            attempts=attempts,
            created_at=utc_now_iso(),
        )
        if not sessions:
            return

        existing = self._healing_items(job_id)
        if existing:
            with self._table.batch_writer() as batch:
                for item in existing:
                    batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
        with self._table.batch_writer() as batch:
            for session in sessions:
                batch.put_item(Item=self._healing_item(session))

    def list_healing_sessions(
        self,
        *,
        limit: int = 20,
        issue_key: str | None = None,
        status: str | None = None,
        strategy: str | None = None,
    ) -> list[dict[str, Any]]:
        if status:
            kwargs: dict[str, Any] = {
                "IndexName": "GSI3",
                "KeyConditionExpression": Key("gsi3pk").eq(f"HEALSTATUS#{status}"),
                "ScanIndexForward": False,
            }
            filters = []
            if issue_key:
                filters.append(Attr("issue_key").eq(issue_key))
            if strategy:
                filters.append(Attr("strategy").eq(strategy))
            if filters:
                expression = filters[0]
                for extra in filters[1:]:
                    expression = expression & extra
                kwargs["FilterExpression"] = expression
            items = self._query_all(**kwargs)
        else:
            expression = Attr("entity_type").eq("healing")
            if issue_key:
                expression = expression & Attr("issue_key").eq(issue_key)
            if strategy:
                expression = expression & Attr("strategy").eq(strategy)
            items = self._scan_all(expression)

        sessions = [self._healing_from_item(item) for item in items]
        sessions.sort(key=lambda session: (session["createdAt"], session["attempt"]), reverse=True)
        return sessions[:limit]

    def _update_job(self, job_id: str, update_expression: str, values: dict[str, Any]) -> None:
        names: dict[str, str] = {}
        if "#status" in update_expression:
            names["#status"] = "status"
        if "#error" in update_expression:
            names["#error"] = "error"
        kwargs: dict[str, Any] = {
            "Key": {"pk": f"JOB#{job_id}", "sk": "METADATA"},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": values,
            "ConditionExpression": "attribute_exists(pk)",
        }
        if names:
            kwargs["ExpressionAttributeNames"] = names
        try:
            self._table.update_item(**kwargs)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    def _query_all(self, **kwargs: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))
            start = response.get("LastEvaluatedKey")
            if not start:
                return items
            kwargs["ExclusiveStartKey"] = start

    def _scan_all(self, filter_expression: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"FilterExpression": filter_expression}
        while True:
            response = self._table.scan(**kwargs)
            items.extend(response.get("Items", []))
            start = response.get("LastEvaluatedKey")
            if not start:
                return items
            kwargs["ExclusiveStartKey"] = start

    def _healing_items(self, job_id: str) -> list[dict[str, Any]]:
        return self._query_all(
            KeyConditionExpression=Key("pk").eq(f"JOB#{job_id}") & Key("sk").begins_with("HEAL#"),
        )

    def _job_item(self, job: dict[str, Any]) -> dict[str, Any]:
        created_at = job["createdAt"]
        job_id = job["jobId"]
        item: dict[str, Any] = {
            "pk": f"JOB#{job_id}",
            "sk": "METADATA",
            "entity_type": "job",
            "job_id": job_id,
            "issue_key": job["issueKey"],
            "status": job["status"],
            "created_at": created_at,
            "gsi1pk": f"STATUS#{job['status']}",
            "gsi1sk": f"{created_at}#{job_id}",
            "gsi2pk": f"ISSUE#{job['issueKey']}",
            "gsi2sk": f"{created_at}#{job_id}",
        }
        if job.get("startedAt"):
            item["started_at"] = job["startedAt"]
        if job.get("completedAt"):
            item["completed_at"] = job["completedAt"]
        result_json = _json_text(job.get("result"))
        if result_json is not None:
            item["result_json"] = result_json
        request_json = _json_text(job.get("requestPayload"))
        if request_json is not None:
            item["request_json"] = request_json
        if job.get("error"):
            item["error"] = job["error"]
        return item

    def _job_from_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return job_record(
            job_id=str(item.get("job_id") or str(item["pk"]).removeprefix("JOB#")),
            issue_key=str(item["issue_key"]),
            status=str(item["status"]),
            created_at=str(item["created_at"]),
            started_at=item.get("started_at"),
            completed_at=item.get("completed_at"),
            result=_json_load(item.get("result_json")),
            request_payload=_json_load(item.get("request_json")),
            error=item.get("error"),
        )

    def _healing_item(self, session: dict[str, Any]) -> dict[str, Any]:
        attempt = int(session["attempt"])
        item: dict[str, Any] = {
            "pk": f"JOB#{session['jobId']}",
            "sk": f"HEAL#{attempt:04d}",
            "entity_type": "healing",
            "session_id": session["sessionId"],
            "job_id": session["jobId"],
            "issue_key": session["issueKey"],
            "attempt": attempt,
            "strategy": session["strategy"],
            "status": session["status"],
            "created_at": session["createdAt"],
            "gsi3pk": f"HEALSTATUS#{session['status']}",
            "gsi3sk": f"{session['createdAt']}#{session['sessionId']}",
        }
        score_before = _decimal(session.get("scoreBefore"))
        score_after = _decimal(session.get("scoreAfter"))
        if score_before is not None:
            item["score_before"] = score_before
        if score_after is not None:
            item["score_after"] = score_after
        return item

    def _healing_from_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return healing_session_record(
            session_id=str(item["session_id"]),
            job_id=str(item["job_id"]),
            issue_key=str(item["issue_key"]),
            attempt=int(item["attempt"]),
            strategy=str(item["strategy"]),
            status=str(item["status"]),
            score_before=_float(item.get("score_before")),
            score_after=_float(item.get("score_after")),
            created_at=str(item["created_at"]),
        )
