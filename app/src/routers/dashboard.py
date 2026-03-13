from html import escape
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from app.src.security import require_api_key
from app.src.services.job_service import list_jobs


router = APIRouter()


def _build_dashboard_metrics(*, sample_limit: int) -> dict[str, Any]:
    jobs = list_jobs(limit=sample_limit)
    total = len(jobs)
    status_counts = {"pending": 0, "running": 0, "succeeded": 0, "failed": 0}
    governance_blocked = 0
    validator_failed = 0
    automation_tasks_created = 0

    for job in jobs:
        status = job.get("status")
        if status in status_counts:
            status_counts[status] += 1

        result = job.get("result") or {}
        governance = result.get("governanceDecision") or {}
        validator = result.get("validatorDecision") or {}
        execution_trace = result.get("executionTrace") or {}

        if governance.get("allowedForAutomation") is False:
            governance_blocked += 1
        if validator.get("isValid") is False:
            validator_failed += 1
        if execution_trace.get("taskCreated") is True:
            automation_tasks_created += 1

    failed_recent = [
        {
            "jobId": item["jobId"],
            "issueKey": item["issueKey"],
            "error": item.get("error"),
            "completedAt": item.get("completedAt"),
        }
        for item in list_jobs(limit=10, status="failed")
    ]

    success_rate = round((status_counts["succeeded"] / total), 2) if total else 0.0
    return {
        "sampleSize": total,
        "sampleLimit": sample_limit,
        "statusCounts": status_counts,
        "successRate": success_rate,
        "governanceBlockedCount": governance_blocked,
        "validatorFailedCount": validator_failed,
        "automationTasksCreatedCount": automation_tasks_created,
        "recentFailedJobs": failed_recent,
    }


@router.get("/dashboard/metrics", operation_id="dashboard_metrics")
def dashboard_metrics(
    sample_limit: int = Query(default=200, ge=20, le=1000),
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    return _build_dashboard_metrics(sample_limit=sample_limit)


@router.get("/dashboard", response_class=HTMLResponse, operation_id="dashboard_view")
def dashboard_view(
    sample_limit: int = Query(default=200, ge=20, le=1000),
    _: None = Depends(require_api_key),
) -> str:
    metrics = _build_dashboard_metrics(sample_limit=sample_limit)
    status = metrics["statusCounts"]
    failed_rows = []
    for job in metrics["recentFailedJobs"]:
        failed_rows.append(
            "<tr>"
            f"<td>{escape(job['jobId'])}</td>"
            f"<td>{escape(job['issueKey'])}</td>"
            f"<td>{escape((job.get('error') or '')[:160])}</td>"
            f"<td>{escape(job.get('completedAt') or '-')}</td>"
            "</tr>"
        )

    failed_table = (
        "<table><thead><tr><th>Job ID</th><th>Issue</th><th>Error</th><th>Completed</th></tr></thead>"
        f"<tbody>{''.join(failed_rows) if failed_rows else '<tr><td colspan=4>No failed jobs in sample.</td></tr>'}</tbody></table>"
    )

    return f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>QAP Operations Dashboard</title>
    <style>
      body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
      .grid {{ display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 12px; margin: 16px 0 24px; }}
      .card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; background: #fafafa; }}
      .label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; }}
      .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; font-size: 14px; }}
      th {{ background: #f3f4f6; }}
      code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
    </style>
  </head>
  <body>
    <h1>QAP Operations Dashboard</h1>
    <p>Sampled latest <code>{metrics["sampleSize"]}</code> jobs (limit <code>{metrics["sampleLimit"]}</code>).</p>
    <div class="grid">
      <div class="card"><div class="label">Succeeded</div><div class="value">{status["succeeded"]}</div></div>
      <div class="card"><div class="label">Failed</div><div class="value">{status["failed"]}</div></div>
      <div class="card"><div class="label">Running</div><div class="value">{status["running"]}</div></div>
      <div class="card"><div class="label">Pending</div><div class="value">{status["pending"]}</div></div>
      <div class="card"><div class="label">Success Rate</div><div class="value">{metrics["successRate"]}</div></div>
      <div class="card"><div class="label">Governance Blocked</div><div class="value">{metrics["governanceBlockedCount"]}</div></div>
      <div class="card"><div class="label">Validator Failed</div><div class="value">{metrics["validatorFailedCount"]}</div></div>
      <div class="card"><div class="label">Automation Tasks Created</div><div class="value">{metrics["automationTasksCreatedCount"]}</div></div>
    </div>
    <h2>Recent Failed Jobs</h2>
    {failed_table}
  </body>
</html>
""".strip()
