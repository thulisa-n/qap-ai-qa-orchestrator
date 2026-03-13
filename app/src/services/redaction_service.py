import re

EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")
GEMINI_KEY_PATTERN = re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")
ATLASSIAN_TOKEN_PATTERN = re.compile(r"\bATATT[0-9A-Za-z._=\-]{20,}\b")
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_\-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;]+)"
)


def redact_sensitive_text(text: str | None) -> str:
    if not text:
        return ""

    sanitized = text
    sanitized = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)
    sanitized = GEMINI_KEY_PATTERN.sub("[REDACTED_GEMINI_KEY]", sanitized)
    sanitized = ATLASSIAN_TOKEN_PATTERN.sub("[REDACTED_ATLASSIAN_TOKEN]", sanitized)
    sanitized = SECRET_ASSIGNMENT_PATTERN.sub(r"\1=[REDACTED_SECRET]", sanitized)
    return sanitized


def sanitize_external_text(text: str | None, *, max_chars: int = 12000) -> str:
    sanitized = redact_sensitive_text(text)
    sanitized = sanitized.replace("\x00", "")
    if len(sanitized) > max_chars:
        return sanitized[:max_chars] + "\n[TRUNCATED_FOR_SAFETY]"
    return sanitized
