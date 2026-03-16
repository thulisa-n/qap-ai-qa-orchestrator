import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.src.agents.decision_explainer_agent import build_decision_explanation
from app.src.agents.critic_agent import run_artifact_critic
from app.src.agents.remediation_agent import plan_remediation
from app.src.agents.validator_agent import validate_agent_outputs
from app.src.governance.engine import evaluate_governance_gate
from app.src.schemas import (
    ArtifactCriticDecision,
    AutomationDecision,
    FullQAFlowRequest,
    GeneratePlaywrightRequest,
    GeneratePlaywrightResponse,
    GenerateTestsResponse,
    JiraAutomationTaskRequest,
    JiraCommentRequest,
    ProceedAnywayRequest,
    RemediationDecision,
    ValidatorDecision,
)
from app.src.services.file_service import write_playwright_files
from app.src.services.job_service import (
    cleanup_jobs,
    create_job,
    get_job,
    get_job_trace,
    list_jobs,
    mark_job_failed,
    mark_job_running,
    mark_job_succeeded,
    update_job_result,
)
from app.src.services.jira_service import (
    format_tests_for_jira,
    jira_add_comment,
    jira_add_labels,
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
    section_boundary_pattern = re.compile(
        r"^(h[1-6]\.|summary\b|description\b|optional context\b|expected qap output\b|definition of done\b|notes\b)",
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
            if section_boundary_pattern.match(stripped):
                break
            candidate_lines.append(stripped)
    else:
        candidate_lines = [line.strip() for line in lines if line.strip()]

    items: list[str] = []
    for line in candidate_lines:
        cleaned = re.sub(r"^#{1,6}\s+", "", line)
        cleaned = re.sub(r"^[\-\*\u2022]\s+", "", cleaned)
        cleaned = re.sub(r"^\d+[\.\)]\s+", "", cleaned)
        cleaned = cleaned.replace("{{", "").replace("}}", "").replace("`", "")
        # Ignore obvious non-AC instruction lines.
        if section_boundary_pattern.match(cleaned):
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


def _format_governance_report_for_jira(governance_decision: dict) -> str:
    lines = [
        "h3. QAP Governance Gate",
        f"*Framework:* {governance_decision.get('framework', 'ISTQB Foundation 4.0')}",
        f"*Allowed for automation:* {'Yes' if governance_decision.get('allowedForAutomation') else 'No'}",
        f"*Requires human approval:* {'Yes' if governance_decision.get('requiresHumanApproval') else 'No'}",
        f"*Coverage ratio:* {governance_decision.get('coverageRatio', 0.0)}",
        f"*Automation risk:* {governance_decision.get('automationRisk', 'unknown')}",
    ]
    violations = governance_decision.get("violations", [])
    if violations:
        lines.append("*Policy violations:*")
        lines.extend([f"- {violation}" for violation in violations])
    else:
        lines.append("*Policy violations:* None")
    lines.append(f"*Summary:* {governance_decision.get('summary', 'No summary provided.')}")
    return "\n".join(lines)


def _format_critic_report_for_jira(critic_decision: ArtifactCriticDecision) -> str:
    lines = [
        "h3. QAP Critic Validation",
        f"*Overall score:* {critic_decision.overallScore}",
        f"*Scenario quality:* {critic_decision.scenarioQualityScore}",
        f"*Playwright quality:* {critic_decision.playwrightQualityScore}",
        f"*Acceptable for handoff:* {'Yes' if critic_decision.isAcceptable else 'No'}",
        f"*Verdict:* {critic_decision.verdict}",
    ]
    if critic_decision.findings:
        lines.append("*Findings:*")
        lines.extend([f"- {finding}" for finding in critic_decision.findings])
    if critic_decision.recommendations:
        lines.append("*Recommendations:*")
        lines.extend([f"- {item}" for item in critic_decision.recommendations])
    return "\n".join(lines)


def _format_validator_report_for_jira(validator_decision: ValidatorDecision) -> str:
    lines = [
        "h3. QAP Validator Gate",
        f"*Valid:* {'Yes' if validator_decision.isValid else 'No'}",
        f"*Verdict:* {validator_decision.verdict}",
    ]
    if validator_decision.findings:
        lines.append("*Findings:*")
        lines.extend([f"- {item}" for item in validator_decision.findings])
    if validator_decision.suggestedFixes:
        lines.append("*Suggested fixes:*")
        lines.extend([f"- {item}" for item in validator_decision.suggestedFixes])
    return "\n".join(lines)


def _format_remediation_report_for_jira(remediation_decision: RemediationDecision) -> str:
    lines = [
        "h3. QAP Remediation Decision",
        f"*Action:* {remediation_decision.action}",
        f"*Status:* {remediation_decision.status}",
    ]
    if remediation_decision.failureCategory:
        lines.append(f"*Failure category:* {remediation_decision.failureCategory}")
    if remediation_decision.healStrategy:
        lines.append(f"*Heal strategy:* {remediation_decision.healStrategy}")
    if remediation_decision.notes:
        lines.append("*Notes:*")
        lines.extend([f"- {item}" for item in remediation_decision.notes])
    return "\n".join(lines)


def _format_unfixable_escalation_for_jira(
    *,
    validator_decision: ValidatorDecision,
    remediation_decision: RemediationDecision,
) -> str:
    lines = [
        "h3. QAP Escalation Required",
        f"*Category:* {remediation_decision.failureCategory or 'unclassified'}",
        "*Reason:* Automated healing did not proceed for this failure profile.",
        "",
        "h4. Recommended human actions",
        "- Review validator and critic findings in trace output.",
        "- Resolve governance/policy ambiguities before re-triggering QA flow.",
        "- Use `/jobs/{jobId}/retry` after fixes, or `/jobs/{jobId}/proceed-anyway` with explicit approval.",
    ]
    if validator_decision.findings:
        lines.append("")
        lines.append("h4. Blocking findings")
        lines.extend([f"- {item}" for item in validator_decision.findings[:5]])
    return "\n".join(lines)


def _derive_outcome_labels(
    *,
    validator_decision: ValidatorDecision,
    governance_decision: dict,
    task_created: dict | None,
) -> list[str]:
    labels: list[str] = []
    if not validator_decision.isValid or not governance_decision.get("allowedForAutomation", False):
        labels.append("qap-needs-review")
    else:
        labels.append("qap-approved")

    if task_created:
        labels.append("qap-automation-complete")
    return labels


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


def _run_generation_and_gates(
    payload: FullQAFlowRequest,
    *,
    context_override: str | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    effective_context = context_override if context_override is not None else payload.context

    tests_prompt = build_tests_prompt(payload.acceptanceCriteria, effective_context)
    tests_text = call_llm(tests_prompt)
    tests = GenerateTestsResponse.model_validate_json(tests_text)
    coverage_report = _analyze_coverage(payload.acceptanceCriteria, tests)

    pw_prompt = build_playwright_prompt(
        payload.acceptanceCriteria, effective_context, payload.baseUrl
    )
    pw_text = call_llm(pw_prompt)
    playwright = GeneratePlaywrightResponse.model_validate_json(pw_text)

    critic_decision = run_artifact_critic(
        acceptance_criteria=payload.acceptanceCriteria,
        context=effective_context,
        tests_json=tests.model_dump_json(),
        playwright_json=playwright.model_dump_json(),
        llm_caller=call_llm,
    )

    decision_prompt = build_automation_decision_prompt(
        payload.acceptanceCriteria,
        effective_context,
        tests.model_dump_json(),
    )
    decision_text = call_llm(decision_prompt)
    automation_decision = AutomationDecision.model_validate_json(decision_text)
    validator_decision = validate_agent_outputs(
        tests=tests,
        playwright=playwright,
        critic=critic_decision,
        automation=automation_decision,
    )
    remediation_decision = plan_remediation(
        validator_decision,
        critic_decision,
        attempt_number=attempt_number,
    )
    governance_decision = evaluate_governance_gate(
        coverage_report=coverage_report,
        tests=tests,
        automation_decision=automation_decision,
        critic_decision=critic_decision,
    )

    return {
        "tests": tests,
        "coverage_report": coverage_report,
        "playwright": playwright,
        "critic_decision": critic_decision,
        "automation_decision": automation_decision,
        "validator_decision": validator_decision,
        "remediation_decision": remediation_decision,
        "governance_decision": governance_decision,
    }


def _run_full_qa_flow(payload: FullQAFlowRequest) -> dict:
    pass_one = _run_generation_and_gates(payload, attempt_number=1)
    tests = pass_one["tests"]
    coverage_report = pass_one["coverage_report"]
    playwright = pass_one["playwright"]
    critic_decision = pass_one["critic_decision"]
    automation_decision = pass_one["automation_decision"]
    validator_decision = pass_one["validator_decision"]
    remediation_decision = pass_one["remediation_decision"]
    governance_decision = pass_one["governance_decision"]

    attempt_states: list[dict[str, Any]] = [
        {
            "attemptNumber": 1,
            "strategy": "initial_generation",
            "scoreBefore": None,
            "scoreAfter": critic_decision.overallScore,
            "outcome": (
                "passed"
                if validator_decision.isValid and governance_decision["allowedForAutomation"]
                else "heal_requested"
                if remediation_decision.action == "heal"
                else "escalated"
                if remediation_decision.action == "escalate"
                else "blocked"
            ),
        }
    ]

    retry_count = 0
    retry_reason: str | None = None
    if not validator_decision.isValid and remediation_decision.action == "heal":
        retry_count = 1
        retry_reason = "validator_needs_fix"
        previous_score = critic_decision.overallScore
        heal_context = (payload.context or "") + (
            "\n\n[HEAL_RETRY]\n"
            "Regenerate artifacts and resolve validator findings with stricter fidelity to AC.\n"
            f"Findings: {'; '.join(validator_decision.findings)}\n"
            f"Suggested fixes: {'; '.join(validator_decision.suggestedFixes)}"
        )
        pass_two = _run_generation_and_gates(
            payload,
            context_override=heal_context,
            attempt_number=2,
        )
        tests = pass_two["tests"]
        coverage_report = pass_two["coverage_report"]
        playwright = pass_two["playwright"]
        critic_decision = pass_two["critic_decision"]
        automation_decision = pass_two["automation_decision"]
        validator_decision = pass_two["validator_decision"]
        remediation_decision = pass_two["remediation_decision"]
        governance_decision = pass_two["governance_decision"]
        attempt_states.append(
            {
                "attemptNumber": 2,
                "strategy": "heal_retry",
                "healStrategy": remediation_decision.healStrategy or "enhance_prompt_quality",
                "scoreBefore": previous_score,
                "scoreAfter": critic_decision.overallScore,
                "outcome": (
                    "passed"
                    if validator_decision.isValid and governance_decision["allowedForAutomation"]
                    else "escalated"
                    if remediation_decision.action == "escalate"
                    else "blocked"
                ),
            }
        )

    jira_comment = None
    if payload.commentOnJira:
        comment = format_tests_for_jira(tests)
        jira_add_comment(payload.issueKey, comment)
        jira_add_comment(payload.issueKey, _format_coverage_report_for_jira(coverage_report))
        jira_comment = {"issueKey": payload.issueKey, "status": "comment_added"}
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
        jira_add_comment(payload.issueKey, _format_critic_report_for_jira(critic_decision))
        jira_add_comment(payload.issueKey, _format_validator_report_for_jira(validator_decision))
        if remediation_decision.action != "none":
            jira_add_comment(
                payload.issueKey,
                _format_remediation_report_for_jira(remediation_decision),
            )
            if (
                remediation_decision.action == "escalate"
                and remediation_decision.failureCategory
                and remediation_decision.failureCategory.startswith("unfixable_")
            ):
                jira_add_comment(
                    payload.issueKey,
                    _format_unfixable_escalation_for_jira(
                        validator_decision=validator_decision,
                        remediation_decision=remediation_decision,
                    ),
                )
        jira_add_comment(payload.issueKey, _format_governance_report_for_jira(governance_decision))

    files_written = None
    if payload.writePlaywrightFiles:
        files_written = write_playwright_files(playwright.files)

    task_created = None
    if (
        payload.createAutomationTask
        and automation_decision.shouldCreateAutomationTask
        and validator_decision.isValid
        and governance_decision["allowedForAutomation"]
    ):
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

    labels = _derive_outcome_labels(
        validator_decision=validator_decision,
        governance_decision=governance_decision,
        task_created=task_created,
    )
    try:
        jira_add_labels(payload.issueKey, labels)
    except Exception as exc:
        # Labels should enrich workflow state, but must not fail the main QA flow.
        print(f"[jira/full-qa-flow] label update skipped for {payload.issueKey}: {exc}")

    return {
        "status": "ok",
        "executionTrace": {
            "steps": [
                "generate_tests",
                "analyze_coverage",
                "generate_playwright",
                "critic_validation",
                "automation_decision",
                "validator_gate",
                "remediation_planning",
                "governance_gate",
                "jira_reporting",
            ],
            "taskCreated": bool(task_created),
            "retryAttempted": retry_count > 0,
            "retryCount": retry_count,
            "retryReason": retry_reason,
            "attemptState": {
                "attempts": attempt_states,
                "finalOutcome": attempt_states[-1]["outcome"] if attempt_states else "unknown",
            },
        },
        "automationDecision": automation_decision.model_dump(),
        "criticDecision": critic_decision.model_dump(),
        "validatorDecision": validator_decision.model_dump(),
        "remediationDecision": remediation_decision.model_dump(),
        "governanceDecision": governance_decision,
        "decisionExplanation": build_decision_explanation(
            critic_decision=critic_decision.model_dump(),
            validator_decision=validator_decision.model_dump(),
            governance_decision=governance_decision,
            automation_decision=automation_decision.model_dump(),
        ),
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


def _run_full_qa_flow_background(payload_data: dict, job_id: str) -> None:
    try:
        mark_job_running(job_id)
        payload = FullQAFlowRequest.model_validate(payload_data)
        result = _run_full_qa_flow(payload)
        mark_job_succeeded(job_id, result)
    except Exception as exc:
        issue_key = payload_data.get("issueKey", "unknown-issue")
        mark_job_failed(job_id, str(exc))
        print(f"[jira/full-qa-flow-async] background error for {issue_key}: {exc}")


@router.post("/jira/full-qa-flow-async", operation_id="jira_full_qa_flow_async")
def jira_full_qa_flow_async(
    payload: FullQAFlowRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
) -> dict:
    try:
        job_id = str(uuid4())
        payload_dict = payload.model_dump()
        create_job(job_id=job_id, issue_key=payload.issueKey, request_payload=payload_dict)
        background_tasks.add_task(
            _run_full_qa_flow_background, payload_dict, job_id
        )
        return {
            "status": "accepted",
            "mode": "async",
            "jobId": job_id,
            "jobStatusPath": f"/jobs/{job_id}",
            "issueKey": payload.issueKey,
            "message": "Full QA flow started in background.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/jobs/{job_id}", operation_id="get_async_job_status")
def get_async_job_status(
    job_id: str,
    _: None = Depends(require_api_key),
) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/jobs/{job_id}/trace", operation_id="get_async_job_trace")
def get_async_job_trace(
    job_id: str,
    _: None = Depends(require_api_key),
) -> dict:
    trace = get_job_trace(job_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Job not found.")
    return trace


@router.get("/jobs/{job_id}/explain-decision", operation_id="explain_async_job_decision")
def explain_async_job_decision(
    job_id: str,
    _: None = Depends(require_api_key),
) -> dict:
    trace = get_job_trace(job_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Job not found.")

    explanation = trace.get("decisionExplanation") or build_decision_explanation(
        critic_decision=(trace.get("criticDecision") or {}),
        validator_decision=(trace.get("validatorDecision") or {}),
        governance_decision=(trace.get("governanceDecision") or {}),
        automation_decision={},
    )
    return {
        "jobId": trace["jobId"],
        "issueKey": trace["issueKey"],
        "status": trace["status"],
        "decisionExplanation": explanation,
    }


@router.post("/jobs/{job_id}/retry", operation_id="retry_async_job")
def retry_async_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_api_key),
) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    request_payload = job.get("requestPayload")
    if not request_payload:
        raise HTTPException(
            status_code=400,
            detail="Job retry is unavailable because original request payload was not persisted.",
        )

    payload = FullQAFlowRequest.model_validate(request_payload)
    new_job_id = str(uuid4())
    create_job(
        job_id=new_job_id,
        issue_key=payload.issueKey,
        request_payload=request_payload,
    )
    background_tasks.add_task(_run_full_qa_flow_background, request_payload, new_job_id)

    try:
        jira_add_comment(
            payload.issueKey,
            (
                "h3. QAP Retry Requested\n"
                f"*Source job:* {job_id}\n"
                f"*New job:* {new_job_id}\n"
                "Reason: Regenerate with validator/critic fixes."
            ),
        )
    except Exception as exc:
        print(f"[jobs/retry] Jira comment skipped for {payload.issueKey}: {exc}")

    return {
        "status": "accepted",
        "mode": "retry",
        "sourceJobId": job_id,
        "jobId": new_job_id,
        "jobStatusPath": f"/jobs/{new_job_id}",
        "issueKey": payload.issueKey,
    }


@router.post("/jobs/{job_id}/proceed-anyway", operation_id="proceed_anyway_async_job")
def proceed_anyway_async_job(
    job_id: str,
    payload: ProceedAnywayRequest | None = None,
    _: None = Depends(require_api_key),
) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    result = job.get("result")
    if not result:
        raise HTTPException(status_code=400, detail="Job does not have a result payload yet.")

    issue_key = job["issueKey"]
    if result.get("automationTask"):
        return {
            "status": "already_created",
            "jobId": job_id,
            "issueKey": issue_key,
            "automationTask": result.get("automationTask"),
        }

    automation_decision = result.get("automationDecision") or {}
    playwright = result.get("playwright") or {}
    files = playwright.get("files") or []
    summary = f"{issue_key} | Automation: Manual override implementation task"
    description = (
        "Manual Override Decision\n"
        "-----------------------\n"
        "QA requested proceed-anyway despite validator/governance block.\n"
        f"Coverage recommendation: {automation_decision.get('recommendedCoverage', 'unknown')}\n"
        f"Confidence: {automation_decision.get('confidence', 'unknown')}\n"
        f"Automation risk: {automation_decision.get('automationRisk', 'unknown')}\n\n"
        "Generated Playwright files:\n"
        + ("\n".join(f"- {item.get('path', 'unknown')}" for item in files) if files else "- None")
    )

    created, used_issue_type, issue_type_warning = _create_issue_with_fallback(
        summary=summary,
        description=description,
        issue_type="Task",
        parent_key=issue_key,
    )

    created_key = created.get("key")
    if created_key and used_issue_type.lower() not in {"sub-task", "subtask"}:
        jira_link_issues(
            inward_issue_key=issue_key,
            outward_issue_key=created_key,
            link_type_name="Relates",
        )

    if issue_type_warning:
        jira_add_comment(
            issue_key,
            "h3. Automation Task Fallback\n"
            "Proceed-anyway attempted with fallback issue type.\n\n"
            f"Details: {issue_type_warning}",
        )

    jira_add_comment(
        issue_key,
        (
            "h3. QAP Manual Override\n"
            f"Proceed-anyway approved for job `{job_id}`.\n"
            f"Created automation task: `{created.get('key', 'unknown')}`.\n"
            f"*Approved by:* {payload.approvedBy if payload and payload.approvedBy else 'unknown'}\n"
            f"*Reason:* {payload.reason if payload and payload.reason else 'No reason provided'}"
        ),
    )

    approved_at = datetime.now(timezone.utc).isoformat()
    result["automationTask"] = created
    result["manualOverride"] = {
        "proceedAnyway": True,
        "sourceJobId": job_id,
        "approvedBy": payload.approvedBy if payload and payload.approvedBy else "unknown",
        "approvedAt": approved_at,
        "reason": payload.reason if payload and payload.reason else "No reason provided",
    }
    update_job_result(job_id, result)

    return {
        "status": "created",
        "mode": "proceed_anyway",
        "jobId": job_id,
        "issueKey": issue_key,
        "automationTask": created,
        "overrideAudit": result["manualOverride"],
    }


@router.post("/jobs/cleanup", operation_id="cleanup_async_jobs")
def cleanup_async_jobs(
    older_than_days: int = Query(default=30, ge=1, le=3650, alias="olderThanDays"),
    status: str | None = Query(default=None, pattern="^(pending|running|succeeded|failed)$"),
    _: None = Depends(require_api_key),
) -> dict:
    result = cleanup_jobs(older_than_days=older_than_days, status=status)
    return {
        "status": "ok",
        "retention": {"olderThanDays": older_than_days, "status": status},
        **result,
    }


@router.get("/jobs", operation_id="list_async_jobs")
def list_async_jobs(
    limit: int = Query(default=20, ge=1, le=200),
    status: str | None = Query(default=None, pattern="^(pending|running|succeeded|failed)$"),
    issue_key: str | None = Query(default=None, alias="issueKey"),
    _: None = Depends(require_api_key),
) -> dict:
    jobs = list_jobs(limit=limit, status=status, issue_key=issue_key)
    return {
        "count": len(jobs),
        "limit": limit,
        "filters": {"status": status, "issueKey": issue_key},
        "jobs": jobs,
    }
