from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator


MAX_ACCEPTANCE_CRITERIA_CHARS = 10000
MAX_CONTEXT_CHARS = 8000
MAX_FILE_CONTENT_CHARS = 200000
MAX_FEEDBACK_REPORT_CHARS = 300000


class GenerateTestsRequest(BaseModel):
    acceptanceCriteria: str = Field(
        validation_alias=AliasChoices("acceptanceCriteria", "acceptance_criteria"),
        min_length=10,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
    )
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)


class GeneratePlaywrightRequest(BaseModel):
    acceptanceCriteria: str = Field(
        validation_alias=AliasChoices("acceptanceCriteria", "acceptance_criteria"),
        min_length=10,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
    )
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)
    baseUrl: str | None = Field(
        default=None, validation_alias=AliasChoices("baseUrl", "base_url")
    )


class GenerateBothRequest(BaseModel):
    acceptanceCriteria: str = Field(
        validation_alias=AliasChoices("acceptanceCriteria", "acceptance_criteria"),
        min_length=10,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
    )
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)
    baseUrl: str | None = Field(
        default=None, validation_alias=AliasChoices("baseUrl", "base_url")
    )


class GenerateQAReportRequest(BaseModel):
    acceptanceCriteria: str = Field(
        validation_alias=AliasChoices(
            "acceptanceCriteria",
            "acceptance_criteria",
            "requirements",
        ),
        min_length=10,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
    )
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)


class AnalyzeFeedbackRequest(BaseModel):
    failureReport: str = Field(
        validation_alias=AliasChoices("failureReport", "failure_report"),
        min_length=20,
        max_length=MAX_FEEDBACK_REPORT_CHARS,
    )
    source: str = Field(default="playwright", pattern="^(playwright|junit|generic)$")
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)
    branchName: str | None = Field(
        default=None, validation_alias=AliasChoices("branchName", "branch_name")
    )
    issueKey: str | None = None
    commentOnJira: bool = False


class JiraAutomationTaskRequest(BaseModel):
    parentIssueKey: str | None = None
    issueType: str = "Task"
    acceptanceCriteria: str = Field(
        validation_alias=AliasChoices("acceptanceCriteria", "acceptance_criteria"),
        min_length=10,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
    )
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)
    baseUrl: str | None = Field(
        default=None, validation_alias=AliasChoices("baseUrl", "base_url")
    )


class JiraCommentRequest(BaseModel):
    issueKey: str
    acceptanceCriteria: str = Field(
        validation_alias=AliasChoices("acceptanceCriteria", "acceptance_criteria"),
        min_length=10,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
    )
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)


class FullQAFlowRequest(BaseModel):
    issueKey: str
    acceptanceCriteria: str = Field(
        validation_alias=AliasChoices("acceptanceCriteria", "acceptance_criteria"),
        min_length=10,
        max_length=MAX_ACCEPTANCE_CRITERIA_CHARS,
    )
    context: str | None = Field(default=None, max_length=MAX_CONTEXT_CHARS)
    baseUrl: str | None = Field(
        default=None, validation_alias=AliasChoices("baseUrl", "base_url")
    )
    commentOnJira: bool = True
    writePlaywrightFiles: bool = True
    createAutomationTask: bool = True
    automationIssueType: str = "Task"
    automationSummaryPrefix: str = "Automation: Implement generated Playwright tests"


class ProceedAnywayRequest(BaseModel):
    approvedBy: str | None = Field(default=None, min_length=2, max_length=120)
    reason: str | None = Field(default=None, min_length=5, max_length=1000)


class Step(BaseModel):
    action: str
    data: dict[str, Any] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str
    title: str
    priority: str
    type: str
    steps: list[Step]


class GenerateTestsResponse(BaseModel):
    tags: list[str]
    scenarios: list[Scenario]
    notes: str


class FileItem(BaseModel):
    path: str
    content: str = Field(min_length=1, max_length=MAX_FILE_CONTENT_CHARS)

    @field_validator("path")
    @classmethod
    def validate_relative_test_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("File path cannot be empty")
        if normalized.startswith("/") or normalized.startswith("\\"):
            raise ValueError("Absolute paths are not allowed")
        if ".." in normalized:
            raise ValueError("Path traversal is not allowed")
        if "\\" in normalized:
            raise ValueError("Backslash paths are not allowed")
        if not normalized.startswith("tests/"):
            raise ValueError("Generated files must be under tests/")
        if not (
            normalized.endswith(".spec.js")
            or normalized.endswith(".test.js")
            or normalized.endswith(".spec.ts")
            or normalized.endswith(".test.ts")
        ):
            raise ValueError("Generated file must be a Playwright spec/test file")
        return normalized


class GeneratePlaywrightResponse(BaseModel):
    tags: list[str]
    files: list[FileItem]
    notes: list[str]


class GenerateBothResponse(BaseModel):
    tests: GenerateTestsResponse
    playwright: GeneratePlaywrightResponse


class QAReportScenarioResult(BaseModel):
    scenario: str
    stepsTaken: list[str]
    expectedResult: str
    actualResult: str
    status: str = Field(pattern="^(Pass|Fail|Blocked|In Progress)$")


class QAReportBenchmark(BaseModel):
    page: str
    baseline: str
    postOptimization: str
    improvement: str


class GenerateQAReportResponse(BaseModel):
    note: str
    testScenariosAndResults: list[QAReportScenarioResult]
    performanceBenchmarking: list[QAReportBenchmark]
    environment: dict[str, str]
    testOutcome: str
    attachments: list[str]
    recommendations: list[str]
    tableView: str | None = None


class AutomationDecision(BaseModel):
    shouldCreateAutomationTask: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=5, max_length=2000)
    recommendedCoverage: str = Field(
        pattern="^(full_automation|partial_automation|manual_only)$"
    )
    automationRisk: str = Field(pattern="^(low|medium|high)$")
    riskReasons: list[str] = Field(default_factory=list, max_length=5)


class ArtifactCriticDecision(BaseModel):
    overallScore: float = Field(ge=0.0, le=1.0)
    scenarioQualityScore: float = Field(ge=0.0, le=1.0)
    playwrightQualityScore: float = Field(ge=0.0, le=1.0)
    isAcceptable: bool
    findings: list[str] = Field(default_factory=list, max_length=10)
    recommendations: list[str] = Field(default_factory=list, max_length=10)
    verdict: str = Field(pattern="^(pass|needs_revision)$")


class ValidatorDecision(BaseModel):
    isValid: bool
    verdict: str = Field(pattern="^(pass|needs_fix|fail)$")
    findings: list[str] = Field(default_factory=list, max_length=15)
    suggestedFixes: list[str] = Field(default_factory=list, max_length=15)


class RemediationDecision(BaseModel):
    action: str = Field(pattern="^(none|retry|heal|escalate)$")
    status: str = Field(pattern="^(not_needed|succeeded|failed|escalated)$")
    notes: list[str] = Field(default_factory=list, max_length=15)


class FailedTestInsight(BaseModel):
    testName: str
    classification: str = Field(pattern="^(flake|environment|regression)$")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, max_length=8)
    suggestedAction: str


class FeedbackAnalysisResponse(BaseModel):
    summary: str
    dominantClassification: str = Field(pattern="^(flake|environment|regression)$")
    confidence: float = Field(ge=0.0, le=1.0)
    findings: list[FailedTestInsight]
    recommendations: list[str] = Field(default_factory=list, max_length=10)
    suggestedRegressionTests: list[str] = Field(default_factory=list, max_length=10)
    suggestedJiraTaskSummary: str
    resolvedIssueKey: str | None = None
    jiraComment: dict[str, Any] | None = None


class PKIProfileValidationRequest(BaseModel):
    commonName: str = Field(min_length=3, max_length=255)
    sanDns: list[str] = Field(default_factory=list, max_length=50)
    validityDays: int = Field(ge=1, le=825)
    keyAlgorithm: str = Field(pattern="^(RSA|ECDSA)$")
    keySize: int = Field(ge=2048, le=16384)
    environment: str = Field(default="prod", pattern="^(prod|staging|dev)$")


class PKIProfileValidationResponse(BaseModel):
    compliant: bool
    policyVersion: str
    findings: list[str] = Field(default_factory=list, max_length=20)
    recommendations: list[str] = Field(default_factory=list, max_length=20)


class FullQAFlowResponse(BaseModel):
    scenarios: dict[str, Any]
    playwright: dict[str, Any]
    automationDecision: dict[str, Any] | None = None
    criticDecision: dict[str, Any] | None = None
    validatorDecision: dict[str, Any] | None = None
    remediationDecision: dict[str, Any] | None = None
    governanceDecision: dict[str, Any] | None = None
    coverageReport: dict[str, Any] | None = None
    jiraComment: dict[str, Any] | None = None
    filesWritten: dict[str, Any] | None = None
    automationTask: dict[str, Any] | None = None
