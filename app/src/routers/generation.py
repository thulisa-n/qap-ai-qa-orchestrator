import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.src.schemas import (
    AnalyzeFeedbackRequest,
    FeedbackAnalysisResponse,
    GenerateBothRequest,
    GenerateBothResponse,
    GeneratePlaywrightRequest,
    GeneratePlaywrightResponse,
    GenerateQAReportRequest,
    GenerateQAReportResponse,
    GenerateTestsRequest,
    GenerateTestsResponse,
    PKIProfileValidationRequest,
    PKIProfileValidationResponse,
)
from app.src.domain.pki_adapter import DemoPKIAdapter, SmallstepPKIAdapter
from app.src.services.llm_service import (
    build_feedback_analysis_prompt,
    build_qa_report_prompt,
    build_playwright_prompt,
    build_tests_prompt,
    call_llm,
)
from app.src.services.jira_service import jira_add_comment
from app.src.services.pki_policy_service import validate_pki_profile
from app.src.security import require_api_key


router = APIRouter()
ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def _build_qa_report_table_view(report: GenerateQAReportResponse) -> str:
    lines: list[str] = []
    lines.append("h3. QAP QA Report")
    lines.append(report.note)
    lines.append("")
    lines.append("h4. Test Scenarios and Results")
    lines.append("||Scenario||Steps Taken||Expected Result||Actual Result||Status||")
    for row in report.testScenariosAndResults:
        steps = "<br/>".join(row.stepsTaken)
        lines.append(
            f"|{row.scenario}|{steps}|{row.expectedResult}|{row.actualResult}|{row.status}|"
        )

    lines.append("")
    lines.append("h4. Performance Benchmarking")
    lines.append("||Page||Baseline||Post-Optimization||Improvement||")
    for row in report.performanceBenchmarking:
        lines.append(
            f"|{row.page}|{row.baseline}|{row.postOptimization}|{row.improvement}|"
        )

    lines.append("")
    lines.append("h4. Environment")
    for key, value in report.environment.items():
        lines.append(f"*{key}:* {value}")

    lines.append("")
    lines.append(f"h4. Test Outcome: {report.testOutcome}")

    if report.attachments:
        lines.append("")
        lines.append("h4. Attachments")
        lines.extend([f"- {item}" for item in report.attachments])

    if report.recommendations:
        lines.append("")
        lines.append("h4. Recommendations")
        lines.extend([f"- {item}" for item in report.recommendations])

    return "\n".join(lines)


def _build_feedback_table_view(report: FeedbackAnalysisResponse) -> str:
    lines: list[str] = [
        "h3. QAP Closed-Loop Feedback Analysis",
        f"*Dominant classification:* {report.dominantClassification}",
        f"*Confidence:* {report.confidence}",
        f"*Summary:* {report.summary}",
        "",
        "h4. Findings",
        "||Test||Classification||Confidence||Evidence||Suggested Action||",
    ]
    for finding in report.findings:
        evidence = "<br/>".join(finding.evidence)
        lines.append(
            f"|{finding.testName}|{finding.classification}|{finding.confidence}|{evidence}|{finding.suggestedAction}|"
        )

    if report.recommendations:
        lines.append("")
        lines.append("h4. Recommendations")
        lines.extend([f"- {item}" for item in report.recommendations])

    if report.suggestedRegressionTests:
        lines.append("")
        lines.append("h4. Suggested Regression Tests")
        lines.extend([f"- {item}" for item in report.suggestedRegressionTests])

    lines.append("")
    lines.append(f"*Suggested Jira task summary:* {report.suggestedJiraTaskSummary}")
    return "\n".join(lines)


def _resolve_issue_key_for_feedback(payload: AnalyzeFeedbackRequest) -> str | None:
    if payload.issueKey:
        return payload.issueKey
    searchable = " ".join(
        [
            payload.branchName or "",
            payload.context or "",
            payload.failureReport or "",
        ]
    )
    match = ISSUE_KEY_PATTERN.search(searchable)
    if match:
        return match.group(1)
    return None


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/generate-tests",
    response_model=GenerateTestsResponse,
    operation_id="generate_tests",
)
def generate_tests_endpoint(
    payload: GenerateTestsRequest, _: None = Depends(require_api_key)
) -> GenerateTestsResponse:
    try:
        prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        text = call_llm(prompt)
        try:
            return GenerateTestsResponse.model_validate_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Model output did not match the expected schema.",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post(
    "/generate-playwright",
    response_model=GeneratePlaywrightResponse,
    operation_id="generate_playwright",
)
def generate_playwright_endpoint(
    payload: GeneratePlaywrightRequest,
    _: None = Depends(require_api_key),
) -> GeneratePlaywrightResponse:
    try:
        prompt = build_playwright_prompt(
            payload.acceptanceCriteria,
            payload.context,
            payload.baseUrl,
        )
        text = call_llm(prompt)
        try:
            return GeneratePlaywrightResponse.model_validate_json(text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Model output did not match the expected schema.",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post(
    "/generate-both",
    response_model=GenerateBothResponse,
    operation_id="generate_both",
)
def generate_both_endpoint(
    payload: GenerateBothRequest, _: None = Depends(require_api_key)
) -> GenerateBothResponse:
    try:
        tests_prompt = build_tests_prompt(payload.acceptanceCriteria, payload.context)
        tests_text = call_llm(tests_prompt)
        try:
            tests_obj = GenerateTestsResponse.model_validate_json(tests_text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Tests output did not match the expected schema.",
            )

        pw_prompt = build_playwright_prompt(
            payload.acceptanceCriteria, payload.context, payload.baseUrl
        )
        pw_text = call_llm(pw_prompt)
        try:
            pw_obj = GeneratePlaywrightResponse.model_validate_json(pw_text)
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Playwright output did not match the expected schema.",
            )

        return GenerateBothResponse(tests=tests_obj, playwright=pw_obj)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post(
    "/feedback/analyze-failures",
    response_model=FeedbackAnalysisResponse,
    operation_id="analyze_feedback_failures",
)
def analyze_feedback_failures_endpoint(
    payload: AnalyzeFeedbackRequest, _: None = Depends(require_api_key)
) -> FeedbackAnalysisResponse:
    try:
        resolved_issue_key = _resolve_issue_key_for_feedback(payload)
        if payload.commentOnJira and not resolved_issue_key:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not resolve issueKey for Jira comment. "
                    "Provide issueKey explicitly or include a ticket key (e.g., QAP-123) "
                    "in branchName/context/failureReport."
                ),
            )
        prompt = build_feedback_analysis_prompt(
            payload.failureReport,
            payload.source,
            payload.context,
        )
        text = call_llm(prompt)
        try:
            analysis = FeedbackAnalysisResponse.model_validate_json(text).model_copy(
                update={"resolvedIssueKey": resolved_issue_key}
            )
            if payload.commentOnJira and resolved_issue_key:
                jira_add_comment(resolved_issue_key, _build_feedback_table_view(analysis))
                return analysis.model_copy(
                    update={
                        "jiraComment": {
                            "issueKey": resolved_issue_key,
                            "status": "comment_added",
                        }
                    }
                )
            return analysis
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="Feedback analysis output did not match the expected schema.",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.post(
    "/pki/validate-profile",
    response_model=PKIProfileValidationResponse,
    operation_id="pki_validate_profile",
)
def pki_validate_profile_endpoint(
    payload: PKIProfileValidationRequest, _: None = Depends(require_api_key)
) -> PKIProfileValidationResponse:
    return validate_pki_profile(payload)


@router.get("/pki/discover", operation_id="pki_discover")
def pki_discover_endpoint(
    mode: str = Query(default="demo", pattern="^(demo|real_pki)$"),
    target: str = Query(default="the-internet.herokuapp.com"),
    _: None = Depends(require_api_key),
) -> dict:
    adapter = DemoPKIAdapter() if mode == "demo" else SmallstepPKIAdapter()
    return adapter.discover_certificates(target)


@router.post(
    "/generate-qa-report",
    response_model=GenerateQAReportResponse,
    operation_id="generate_qa_report",
)
def generate_qa_report_endpoint(
    payload: GenerateQAReportRequest, _: None = Depends(require_api_key)
) -> GenerateQAReportResponse:
    try:
        prompt = build_qa_report_prompt(payload.acceptanceCriteria, payload.context)
        text = call_llm(prompt)
        try:
            report = GenerateQAReportResponse.model_validate_json(text)
            return report.model_copy(
                update={"tableView": _build_qa_report_table_view(report)}
            )
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="QA report output did not match the expected schema.",
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error.")
