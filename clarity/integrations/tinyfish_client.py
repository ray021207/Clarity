"""TinyFish client for web fact-checking."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from clarity.config import settings


class TinyFishClient:
    """TinyFish web verification integration."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://agent.tinyfish.ai/v1/automation/run",
        timeout_seconds: float = 25.0,
    ):
        self.api_key = api_key or settings.tinyfish_api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def _normalize_result(self, claim: str, payload: Any, status_code: int = 200) -> dict[str, Any]:
        """
        Normalize TinyFish responses into a stable internal schema.

        We intentionally handle several shapes because provider payload formats can vary.
        """
        result = {
            "claim": claim,
            "status": "inconclusive",
            "verified": None,
            "confidence": None,
            "evidence": [],
            "raw": payload,
        }

        if status_code >= 400:
            result["error"] = f"http_{status_code}"
            return result

        if not isinstance(payload, dict):
            result["error"] = "unexpected_payload_shape"
            return result

        # Common fields
        verified = payload.get("verified")
        if isinstance(verified, bool):
            result["verified"] = verified
            result["status"] = "verified" if verified else "false"

        label = str(payload.get("verdict", payload.get("status", ""))).lower()
        if label in {"verified", "true", "supported", "correct"}:
            result["status"] = "verified"
            result["verified"] = True
        elif label in {"false", "incorrect", "refuted", "unsupported"}:
            result["status"] = "false"
            result["verified"] = False
        elif label in {"inconclusive", "unknown", "uncertain"}:
            result["status"] = "inconclusive"

        confidence = payload.get("confidence", payload.get("score"))
        if isinstance(confidence, (float, int)):
            result["confidence"] = float(confidence)

        evidence = payload.get("evidence") or payload.get("sources") or payload.get("citations") or []
        if isinstance(evidence, list):
            result["evidence"] = evidence

        # Nested wrappers
        if result["status"] == "inconclusive":
            nested = payload.get("result")
            if isinstance(nested, dict):
                return self._normalize_result(claim=claim, payload=nested, status_code=status_code)

        return result

    async def verify_claim_on_web(self, claim: str, source_url: str = "") -> dict[str, Any]:
        """Verify one claim against web sources via TinyFish."""
        claim = (claim or "").strip()
        if not claim:
            raise RuntimeError("Hallucination agent received an empty claim for verification.")

        if not self.api_key:
            raise RuntimeError("TINYFISH_API_KEY is required. Please set it in your environment.")

        target_url = source_url.strip() or "https://en.wikipedia.org/wiki/Main_Page"
        payload: dict[str, Any] = {
            # TinyFish automation endpoint expects these top-level fields.
            "url": target_url,
            "goal": (
                "Fact-check this claim using reliable sources reachable from the page.\n"
                f"Claim: {claim}\n"
                "Return JSON object with keys: verified (boolean), verdict (string), "
                "confidence (0..1), evidence (array of source snippets/urls)."
            ),
            # Keep task metadata for compatibility with previous integration attempts.
            "task": {
                "type": "fact_check",
                "claim": claim,
                "source_url": target_url,
            },
        }

        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

        try:
            timeout = httpx.Timeout(self.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)
            data = response.json() if response.content else {}
            if response.status_code >= 400:
                raise RuntimeError(
                    f"TinyFish verification failed with HTTP {response.status_code}: {data}"
                )
            return self._normalize_result(claim=claim, payload=data, status_code=response.status_code)
        except Exception as exc:
            raise RuntimeError(f"TinyFish verification error: {type(exc).__name__}: {exc}") from exc

    async def verify_claims_batch(self, claims: list[str]) -> list[dict[str, Any]]:
        """Verify multiple claims concurrently and preserve input order."""
        tasks = [self.verify_claim_on_web(claim=claim) for claim in claims]
        return await asyncio.gather(*tasks, return_exceptions=False)
