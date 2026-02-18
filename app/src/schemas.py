from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator


MAX_ACCEPTANCE_CRITERIA_CHARS = 10000
MAX_CONTEXT_CHARS = 8000
MAX_FILE_CONTENT_CHARS = 200000


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


class AutomationDecision(BaseModel):
    shouldCreateAutomationTask: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=5, max_length=2000)
    recommendedCoverage: str = Field(
        pattern="^(full_automation|partial_automation|manual_only)$"
    )


class FullQAFlowResponse(BaseModel):
    scenarios: dict[str, Any]
    playwright: dict[str, Any]
    automationDecision: dict[str, Any] | None = None
    jiraComment: dict[str, Any] | None = None
    filesWritten: dict[str, Any] | None = None
    automationTask: dict[str, Any] | None = None
