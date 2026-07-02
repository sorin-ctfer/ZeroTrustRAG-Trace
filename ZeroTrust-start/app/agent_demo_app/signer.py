from __future__ import annotations

import hmac
import hashlib
from typing import Dict, Any

from .utils import canonical_json

SIGNATURE_EXCLUDE = {"signature", "validation", "_debug", "canonical_json_before_signature"}


def canonical_payload(package: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in package.items() if k not in SIGNATURE_EXCLUDE}


class ClaimPackageSignerVerifier:
    def sign(self, package: Dict[str, Any], secret: str) -> str:
        payload = canonical_json(canonical_payload(package)).encode("utf-8")
        return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    def verify(self, package: Dict[str, Any], secret: str) -> bool:
        expected = self.sign(package, secret)
        provided = package.get("signature", "")
        return hmac.compare_digest(expected, provided)

