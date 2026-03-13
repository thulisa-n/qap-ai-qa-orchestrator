from abc import ABC, abstractmethod
from typing import Any


class PKIAdapter(ABC):
    @abstractmethod
    def discover_certificates(self, target: str) -> dict[str, Any]:
        raise NotImplementedError


class DemoPKIAdapter(PKIAdapter):
    def discover_certificates(self, target: str) -> dict[str, Any]:
        return {
            "mode": "demo",
            "target": target,
            "certificates": [
                {"id": "demo-cert-001", "commonName": target, "expiryDays": 30},
                {"id": "demo-cert-002", "commonName": target, "expiryDays": 87},
            ],
        }


class SmallstepPKIAdapter(PKIAdapter):
    # Placeholder adapter for real PKI mode integration.
    def discover_certificates(self, target: str) -> dict[str, Any]:
        return {
            "mode": "real_pki_stub",
            "target": target,
            "message": "Integrate with step-ca/CA APIs in production environment.",
            "certificates": [],
        }
