# Security Hardening Report

## Scope
This report covers security controls implemented in the API service and immediate next controls recommended for production-grade enterprise posture.

## Threat model focus
- Sensitive data leakage through API responses/logging.
- Prompt injection against LLM-backed generation endpoints.
- Path traversal and arbitrary file write from generated file paths.
- Unauthorized API access and abuse.
- External dependency failure and retry safety.

## Implemented controls

### 1) SDK migration and dependency hygiene
- Migrated from deprecated `google-generativeai` to `google-genai`.
- Kept dependencies explicit in `app/requirements.txt`.

Security value:
- Reduces dependency risk from unmaintained SDK paths.

### 2) Optional API key enforcement
- Added `API_AUTH_TOKEN` configuration and `X-API-Key` verification.
- All non-health endpoints now support auth enforcement when token is configured.

Security value:
- Prevents anonymous access in shared/staging/production deployments.
- Supports least-privilege rollout without blocking local development.

### 3) Prompt-injection guardrails
- Added prompt-injection marker detection for untrusted user fields.
- Added clear prompt delimiting and explicit "treat input as untrusted" instructions.

Security value:
- Reduces successful instruction-hijacking attempts.
- Enforces a stricter trust boundary between system instructions and user-provided content.

### 4) Strict schema validation for inbound content
- Added max length and minimum length constraints to input fields.
- Added strict file path validation for generated file outputs:
  - no absolute paths
  - no `..` traversal
  - no backslash path tricks
  - allow only `tests/` output
  - allow only Playwright spec/test suffixes

Security value:
- Prevents oversized payload abuse and file-system breakout attempts.

### 5) Defense-in-depth file write checks
- Added resolved-path containment check in file writing service.

Security value:
- Blocks path traversal even if upstream validation is bypassed.

### 6) Information disclosure minimization
- Replaced most raw exception details returned to clients with generic errors.
- Removed raw traceback printing from endpoint path.

Security value:
- Limits accidental leakage of internals, stack traces, and data fragments.

### 7) Baseline response hardening headers
- Added:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Cache-Control: no-store`

Security value:
- Improves client-side safety defaults and cache leakage resistance.

### 8) Automated security regression tests
- Added `pytest` security test suite under `app/tests/test_security.py`.
- Tests include:
  - API auth enforcement checks
  - prompt-injection rejection behavior
  - path traversal rejection and safe-path acceptance
- Wired into Bitbucket PR pipeline (`pytest app/tests -q`).

Security value:
- Prevents silent regressions in key controls during future development.

## How to answer "How do we prevent info bleed?"

For enterprise/security questionnaires, describe controls in three layers:

1. **Data minimization**
   - API does not return stack traces in normal error responses.
   - Sensitive credentials are env-based and excluded from source control.

2. **Access control**
   - API key enforcement is available (`API_AUTH_TOKEN` + `X-API-Key`).
   - Health endpoint can remain public while business endpoints are protected.

3. **Output and write constraints**
   - LLM outputs are schema-validated before use.
   - Generated files are constrained to a safe directory with path containment checks.

## Injection resistance status

### Prompt injection
- **Mitigated** by:
  - marker detection
  - explicit untrusted-data prompt framing
  - strict response schema validation

### Path injection / traversal
- **Mitigated** by:
  - schema-level path allowlist
  - resolved-path containment guard

### Command injection
- **Low current risk** in API runtime because generated content is written, not executed by backend shell.

### SQL/NoSQL injection
- **Not applicable** in current codebase (no database query layer present).

## Residual risk (cannot be reduced to zero)
- LLMs can still produce malformed or low-quality content under adversarial input.
- API key alone is not sufficient for full enterprise IAM compliance.
- Third-party dependency compromise risk remains and needs SCA/SBOM controls.

## Recommended next controls (enterprise-ready)

1. Add structured audit logs with request IDs and redaction.
2. Add rate limiting and abuse detection (per API key + IP).
3. Add secret manager integration (Vault/AWS Secrets Manager/GCP Secret Manager).
4. Add egress restrictions and network policy controls.
5. Add SAST + dependency scanning + image scanning in CI.
6. Add WAF/API gateway in front of service.
7. Add unit/integration security tests for prompt and path abuse regressions.
8. Add auth upgrade path (OIDC/JWT/mTLS) for B2B customers.

## Verification checklist for security testing

### Access control
- [ ] With `API_AUTH_TOKEN` set, request without `X-API-Key` returns 401.
- [ ] Wrong `X-API-Key` returns 401.
- [ ] Correct key succeeds.

### Prompt-injection tests
- [ ] Submit acceptance criteria containing "ignore previous instructions".
- [ ] Confirm request is rejected (or not executed) as expected.

### File path safety tests
- [ ] Attempt generated path `../outside.txt` -> rejected.
- [ ] Attempt absolute path `/tmp/a.spec.js` -> rejected.
- [ ] Attempt `tests/valid.spec.js` -> accepted.

### Error disclosure tests
- [ ] Force backend error and verify response does not include traceback/internal stack details.

### Header checks
- [ ] Verify security headers are present on API responses.

## Conclusion
The current hardening materially improves resistance to common API and LLM-integration attacks (injection, traversal, data leakage). It is a strong baseline for pre-production. For enterprise certification and customer assurance, implement the recommended next controls and continuously validate via automated security tests.
