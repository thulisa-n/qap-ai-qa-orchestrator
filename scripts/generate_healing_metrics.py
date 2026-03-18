import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _safe_rate(numerator: int, denominator: int) -> float:
    return round((numerator / denominator), 4) if denominator else 0.0


def _load_job_results(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT job_id, issue_key, status, result_json, completed_at FROM jobs ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    results: list[dict[str, Any]] = []
    for job_id, issue_key, status, result_json, completed_at in rows:
        if not result_json:
            continue
        try:
            result = json.loads(result_json)
        except json.JSONDecodeError:
            continue
        trace = (result or {}).get("executionTrace") or {}
        attempts = ((trace.get("attemptState") or {}).get("attempts")) or []
        if not attempts:
            continue
        results.append(
            {
                "jobId": job_id,
                "issueKey": issue_key,
                "status": status,
                "completedAt": completed_at,
                "retryCount": int(trace.get("retryCount") or 0),
                "finalOutcome": (trace.get("attemptState") or {}).get("finalOutcome") or "unknown",
                "attempts": len(attempts),
            }
        )
    return results


def _build_badge(*, label: str, message: str, color: str) -> dict[str, Any]:
    return {"schemaVersion": 1, "label": label, "message": message, "color": color}


def _rate_color(rate: float, *, higher_is_better: bool = True) -> str:
    if higher_is_better:
        if rate >= 0.8:
            return "brightgreen"
        if rate >= 0.6:
            return "yellow"
        return "orange"
    if rate <= 0.2:
        return "brightgreen"
    if rate <= 0.4:
        return "yellow"
    return "red"


def generate_metrics(*, db_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = _load_job_results(db_path)
    total_runs = len(runs)
    healed_runs = sum(
        1
        for item in runs
        if item["finalOutcome"] == "passed" and item["retryCount"] > 0
    )
    escalated_runs = sum(1 for item in runs if item["finalOutcome"] == "escalated")
    avg_attempts = round(
        (sum(item["attempts"] for item in runs) / total_runs), 2
    ) if total_runs else 0.0

    healing_rate = _safe_rate(healed_runs, total_runs)
    escalation_rate = _safe_rate(escalated_runs, total_runs)
    dashboard_data = {
        "lastUpdate": datetime.now(timezone.utc).isoformat(),
        "totalRuns": total_runs,
        "healedRuns": healed_runs,
        "escalatedRuns": escalated_runs,
        "healingRate": healing_rate,
        "escalationRate": escalation_rate,
        "averageAttempts": avg_attempts,
        "recentRuns": runs[:20],
    }

    (output_dir / "dashboard-data.json").write_text(
        json.dumps(dashboard_data, indent=2),
        encoding="utf-8",
    )
    (output_dir / "healing-rate.json").write_text(
        json.dumps(
            _build_badge(
                label="healing rate",
                message=f"{round(healing_rate * 100, 1)}%",
                color=_rate_color(healing_rate, higher_is_better=True),
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "escalation-rate.json").write_text(
        json.dumps(
            _build_badge(
                label="escalation rate",
                message=f"{round(escalation_rate * 100, 1)}%",
                color=_rate_color(escalation_rate, higher_is_better=False),
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    avg_color = "brightgreen" if avg_attempts <= 1.3 else "yellow" if avg_attempts <= 2.0 else "orange"
    (output_dir / "average-attempts.json").write_text(
        json.dumps(
            _build_badge(
                label="average attempts",
                message=f"{avg_attempts}",
                color=avg_color,
            ),
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate healing metrics badge JSON files.")
    parser.add_argument(
        "--db-path",
        default="app/.data/jobs.db",
        help="Path to jobs sqlite database.",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/metrics",
        help="Directory where metrics json files are written.",
    )
    args = parser.parse_args()
    generate_metrics(
        db_path=Path(args.db_path).resolve(),
        output_dir=Path(args.output_dir).resolve(),
    )


if __name__ == "__main__":
    main()
