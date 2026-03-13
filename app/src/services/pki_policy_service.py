import json
from pathlib import Path

from app.src.schemas import (
    PKIProfileValidationRequest,
    PKIProfileValidationResponse,
)


def _load_pki_policy() -> dict:
    policy_path = (
        Path(__file__).resolve().parent.parent
        / "governance"
        / "policies"
        / "pki_policy.json"
    )
    return json.loads(policy_path.read_text(encoding="utf-8"))


def validate_pki_profile(
    payload: PKIProfileValidationRequest,
) -> PKIProfileValidationResponse:
    policy = _load_pki_policy()
    findings: list[str] = []
    recommendations: list[str] = []

    min_days = int(policy["baseline"]["minValidityDays"])
    max_days = int(policy["baseline"]["maxValidityDays"])
    min_key_size = int(policy["baseline"]["minimumRsaKeySize"])

    if not (min_days <= payload.validityDays <= max_days):
        findings.append(
            f"validityDays {payload.validityDays} is outside allowed range {min_days}-{max_days}."
        )
        recommendations.append("Use policy-compliant validity period.")

    if payload.keyAlgorithm == "RSA" and payload.keySize < min_key_size:
        findings.append(
            f"RSA keySize {payload.keySize} is below minimum {min_key_size}."
        )
        recommendations.append("Increase RSA key size to compliant baseline.")

    if payload.environment == "prod" and len(payload.sanDns) == 0:
        findings.append("Production certificate profile requires at least one SAN DNS entry.")
        recommendations.append("Populate sanDns with approved production hostnames.")

    if payload.commonName.lower() == "localhost" and payload.environment == "prod":
        findings.append("commonName localhost is not allowed for production profile.")
        recommendations.append("Use a publicly trusted production hostname.")

    return PKIProfileValidationResponse(
        compliant=len(findings) == 0,
        policyVersion=policy["version"],
        findings=findings,
        recommendations=recommendations,
    )
