import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.src.schemas import (
    AutomationDecision,
    FullQAFlowRequest,
    GeneratePlaywrightRequest,
    GeneratePlaywrightResponse,
    GenerateTestsResponse,
    JiraAutomationTaskRequest,
    JiraCommentRequest,
)
from app.src.services.file_service import write_playwright_files
from app.src.services.jira_service import (
    format_tests_for_jira,
    jira_add_comment,
    jira_create_issue,
    jira_link_issues,
)
from app.src.services.llm_service import (
    build_automation_decision_prompt,
    build_playwright_prompt,
    build_tests_prompt,
    call_llm,
)
from app.src.security import require_api_key


router = APIRouter()


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "when",
    "then",
    "must",
    "should",
    "have",
    "after",
    "before",
    "within",
    "user",
    "users",
}


def _extract_acceptance_criteria_items(raw_text: str) -> list[str]:
    lines = (raw_text or "").splitlines()
    section_heading_pattern = re.compile(
        r"^(h[1-6]\.|#{1,6}\s|summary\b|description\b|optional context\b|expected qap output\b|notes\b)",
        re.IGNORECASE,
    )

    # Prefer extracting explicit AC section content when present.
    start_index = None
    for idx, line in enumerate(lines):
        if "acceptance criteria" in line.strip().lower():
            start_index = idx + 1
            break

    candidate_lines: list[str] = []
    if start_index is not None:
        for line in lines[start_index:]:
            stripped = line.strip()
            if not stripped:
                continue
            if section_heading_pattern.match(stripped):
                break
            candidate_lines.append(stripped)
    else:
        candidate_lines = [line.strip() for line in lines if line.strip()]

    items: list[str] = []
    for line in candidate_lines:
        cleaned = re.sub(r"^[\-\*\u2022]\s+", "", line)
        cleaned = re.sub(r"^\d+[\.\)]\s+", "", cleaned)
        cleaned = cleaned.replace("{{", "").replace("}}", "").replace("`", "")
        # Ignore obvious non-AC instruction lines.
        if section_heading_pattern.match(cleaned):
            continue
        if len(cleaned) >= 8:
            items.append(cleaned)

    if items:
        return items
    fallback = (raw_text or "").strip()
    return [fallback] if fallback else []


def _tokenize_for_coverage(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-zA-Z0-9]+", text.lower()))
    return {token for token in tokens if len(token) >= 4 and token not in STOPWORDS}


def _analyze_coverage(acceptance_criteria: str, tests: GenerateTestsResponse) -> dict:
    ac_items = _extract_acceptance_criteria_items(acceptance_criteria)
    scenario_texts = [
        " ".join(
            [
                scenario.title,
                *[step.action for step in scenario.steps],
            ]
        ).lower()
        for scenario in tests.scenarios
    ]
    scenario_tokens = [_tokenize_for_coverage(text) for text in scenario_texts]

    coverage_rows: list[dict[str, str]] = []
    covered_count = 0
    for ac in ac_items:
        ac_tokens = _tokenize_for_coverage(ac)
        best_overlap = 0
        for sc_tokens in scenario_tokens:
            overlap = len(ac_tokens.intersection(sc_tokens))
            if overlap > best_overlap:
                best_overlap = overlap

        required_overlap = 1 if len(ac_tokens) <= 2 else 2
        is_covered = best_overlap >= required_overlap
        if is_covered:
            covered_count += 1
        coverage_rows.append(
            {
                "acceptanceCriteria": ac,
                "status": "covered" if is_covered else "missing",
            }
        )

    total = len(coverage_rows)
    score = (covered_count / total) if total else 0.0
    return {
        "total": total,
        "covered": covered_count,
        "missing": total - covered_count,
        "score": round(score, 2),
        "items": coverage_rows,
    }


def _format_coverage_report_for_jira(coverage_report: dict) -> str:
    lines = [
        "h3. QAP Coverage Report",
        "",
        "h4. Acceptance Criteria Coverage",
        "||Acceptance Criterion||Status||",
    ]
    for row in coverage_report.get("items", []):
        status_label = "Covered" if row["status"] == "covered" else "Missing"
        lines.append(f"|{row['acceptanceCriteria']}|{status_label}|")
    lines.extend(
        [
            "",
            f"*Coverage score:* {coverage_report.get('covered', 0)} / {coverage_report.get('total', 0)}",
            f"*Coverage ratio:* {coverage_report.get('score', 0.0)}",
        ]
    )
    return "\n".join(lines)


def _create_issue_with_fallback(
    *,
    summary: str,
    description: str,
    issue_type: str,
    parent_key: str | None,
) -> tuple[dict, str, str | None]:
    try:
        created = jira_create_issue(
            summary=summary,
            description=description,
            issue_type=issue_type,
            parent_key=parent_key,
        )
        return created, issue_type, None
    except RuntimeError as exc:
        message = str(exc)
        # Some projects do not have "Sub-task" issue type enabled; fall back to Task.
        if issue_type.lower() in {"sub-task", "subtask"} and "valid issue type" in message.lower():
            fallback_issue_type = "Task"
            created = jira_create_issue(
                summary=summary,
                description=description
                + "\n\nFallback note: Requested issue type was unavailable; created as Task.",
                issue_type=fallback_issue_type,
                parent_key=None,
            )
            return created, fallback_issue_type, message
        raise


def _run_full_qa_flow(payload: FullQAFlowRequest) -> dict:
    tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
    tests_text = call_llm(tests_prompt)
    tests = GenerateTestsResponse.model_validate_json(tests_text)
    coverage_report = _analyze_coverage(payload.acceptanceCriteria, tests)

    jira_comment = None
    if payload.commentOnJira:
        comment = format_tests_for_jira(tests)
        jira_add_comment(payload.issueKey, comment)
        jira_add_comment(payload.issueKey, _format_coverage_report_for_jira(coverage_report))
        jira_comment = {"issueKey": payload.issueKey, "status": "comment_added"}

    pw_prompt = build_playwright_prompt(
        payload.acceptanceCriteria, payload.context, payload.baseUrl
    )
    pw_text = call_llm(pw_prompt)
    playwright = GeneratePlaywrightResponse.model_validate_json(pw_text)

    decision_prompt = build_automation_decision_prompt(
        payload.acceptanceCriteria,
        payload.context,
        tests.model_dump_json(),
    )
    decision_text = call_llm(decision_prompt)
    automation_decision = AutomationDecision.model_validate_json(decision_text)
    if payload.commentOnJira:
        decision_comment_lines = [
            "h3. AI QA Agent Decision",
            f"*Create automation task:* {'Yes' if automation_decision.shouldCreateAutomationTask else 'No'}",
            f"*Recommended coverage:* {automation_decision.recommendedCoverage}",
            f"*Confidence:* {automation_decision.confidence}",
            f"*Automation risk:* {automation_decision.automationRisk}",
            f"*Reason:* {automation_decision.reason}",
        ]
        if automation_decision.riskReasons:
            decision_comment_lines.append("*Risk reasons:*")
            decision_comment_lines.extend(
                [f"- {risk_reason}" for risk_reason in automation_decision.riskReasons]
            )
        jira_add_comment(payload.issueKey, "\n".join(decision_comment_lines))

    files_written = None
    if payload.writePlaywrightFiles:
        files_written = write_playwright_files(playwright.files)

    task_created = None
    if payload.createAutomationTask and automation_decision.shouldCreateAutomationTask:
        summary = f"{payload.issueKey} | {payload.automationSummaryPrefix}"
        description = (
            "Automation Decision\n"
            "-------------------\n"
            f"Coverage recommendation: {automation_decision.recommendedCoverage}\n"
            f"Confidence: {automation_decision.confidence}\n"
                f"Automation risk: {automation_decision.automationRisk}\n"
            f"Reason: {automation_decision.reason}\n\n"
                "Risk Reasons\n"
                "------------\n"
                + (
                    "\n".join(f"- {risk_reason}" for risk_reason in automation_decision.riskReasons)
                    if automation_decision.riskReasons
                    else "- No material risk factors detected."
                )
                + "\n\n"
            "Generated Playwright tests are ready.\n\nFiles:\n"
            + "\n".join(f"- {file_item.path}" for file_item in playwright.files)
        )
        task_created, used_issue_type, issue_type_warning = _create_issue_with_fallback(
            summary=summary,
            description=description,
            issue_type=payload.automationIssueType,
            parent_key=payload.issueKey,
        )

        # If created issue is not a Sub-task, create a link back to parent story.
        if used_issue_type.lower() not in {"sub-task", "subtask"}:
            created_key = task_created.get("key")
            if created_key:
                jira_link_issues(
                    inward_issue_key=payload.issueKey,
                    outward_issue_key=created_key,
                    link_type_name="Relates",
                )
        if issue_type_warning:
            jira_add_comment(
                payload.issueKey,
                "h3. Automation Task Fallback\n"
                f"Requested issue type `{payload.automationIssueType}` was not available. "
                f"Created as `Task` instead.\n\nDetails: {issue_type_warning}",
            )

    return {
        "status": "ok",
        "automationDecision": automation_decision.model_dump(),
        "coverageReport": coverage_report,
        "jiraComment": jira_comment,
        "tests": tests.model_dump(),
        "playwright": playwright.model_dump(),
        "filesWritten": files_written,
        "automationTask": task_created,
    }


@router.post("/jira/comment-tests", operation_id="jira_comment_tests")
def jira_comment_tests_endpoint(
    payload: JiraCommentRequest, _: None = Depends(require_api_key)
) -> dict[str, str]:
    try:
        prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        text = call_llm(prompt)
        tests = GenerateTestsResponse.model_validate_json(text)

        comment = format_tests_for_jira(tests)
        jira_add_comment(payload.issueKey, comment)
        return {"status": "comment_added", "issueKey": payload.issueKey}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post("/playwright/write-files", operation_id="playwright_write_files")
def playwright_write_files_endpoint(
    payload: GeneratePlaywrightRequest, _: None = Depends(require_api_key)
) -> dict:
    try:
        prompt = build_playwright_prompt(
            payload.acceptanceCriteria, payload.context, payload.baseUrl
        )
        text = call_llm(prompt)
        pw = GeneratePlaywrightResponse.model_validate_json(text)
        created = write_playwright_files(pw.files)
        return {
            "message": "Playwright tests written successfully",
            "files": created,
            "notes": pw.notes,
            "tags": pw.tags,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post("/jira/create-automation-task", operation_id="jira_create_automation_task")
def jira_create_automation_task_endpoint(
    payload: JiraAutomationTaskRequest, _: None = Depends(require_api_key)
) -> dict:
    try:
        tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        tests_text = call_llm(tests_prompt)
        tests = GenerateTestsResponse.model_validate_json(tests_text)

        pw_prompt = build_playwright_prompt(
            payload.acceptanceCriteria, payload.context, payload.baseUrl
        )
        pw_text = call_llm(pw_prompt)
        pw = GeneratePlaywrightResponse.model_validate_json(pw_text)

        description_lines = []
        description_lines.append("AI Generated Test Scenarios")
        description_lines.append("--------------------------")
        for scenario in tests.scenarios:
            description_lines.append(f"\n{scenario.id} — {scenario.title}")
            description_lines.append(
                f"Priority: {scenario.priority} | Type: {scenario.type}"
            )
            description_lines.append("Steps:")
            for index, step in enumerate(scenario.steps, 1):
                description_lines.append(f"{index}. {step.action}")

        description_lines.append("\n\nGenerated Playwright Files")
        description_lines.append("-------------------------")
        for file_item in pw.files:
            description_lines.append(f"- {file_item.path}")

        if pw.notes:
            description_lines.append("\nNotes")
            description_lines.append("-----")
            description_lines.extend([f"- {note}" for note in pw.notes])

        created, used_issue_type, issue_type_warning = _create_issue_with_fallback(
            summary="Automation: Generate Playwright tests from acceptance criteria",
            description="\n".join(description_lines),
            issue_type=payload.issueType,
            parent_key=payload.parentIssueKey,
        )

        if payload.parentIssueKey and used_issue_type.lower() not in {
            "sub-task",
            "subtask",
        }:
            created_key = created.get("key")
            if created_key:
                jira_link_issues(
                    inward_issue_key=payload.parentIssueKey,
                    outward_issue_key=created_key,
                    link_type_name="Relates",
                )
        if issue_type_warning and payload.parentIssueKey:
            jira_add_comment(
                payload.parentIssueKey,
                "h3. Automation Task Fallback\n"
                f"Requested issue type `{payload.issueType}` was not available. "
                f"Created as `Task` instead.\n\nDetails: {issue_type_warning}",
            )

        return {"status": "created", "issue": created}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post("/jira/full-qa-flow", operation_id="jira_full_qa_flow")
def jira_full_qa_flow(
    payload: FullQAFlowRequest, _: None = Depends(require_api_key)
) -> dict:
    try:
        return _run_full_qa_flow(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


def _run_full_qa_flow_background(payload_data: dict) -> None:
    try:
        payload = FullQAFlowRequest.model_validate(payload_data)
        _run_full_qa_flow(payload)
    except Exception as exc:
        issue_key = payload_data.get("issueKey", "unknown-issue")
        print(f"[jira/full-qa-flow-async] background error for {issue_key}: {exc}")


@router.post("/jira/full-qa-flow-async", operation_id="jira_full_qa_flow_async")
def jira_full_qa_flow_async(
    payload: FullQAFlowRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
) -> dict:
    try:
        background_tasks.add_task(_run_full_qa_flow_background, payload.model_dump())
        return {
            "status": "accepted",
            "mode": "async",
            "issueKey": payload.issueKey,
            "message": "Full QA flow started in background.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")
