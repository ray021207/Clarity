"""TinyFish client stub for web fact-checking (Person B will implement)."""

from clarity.config import settings


class TinyFishClient:
    """Stub for TinyFish web verification. Person B will implement."""

    def __init__(self, api_key: str = ""):
        """Initialize TinyFish client."""
        self.api_key = api_key or settings.tinyfish_api_key

    async def verify_claim_on_web(self, claim: str, source_url: str = "") -> dict[str, any]:
        """Verify a claim on the web. To be implemented by Person B."""
        raise NotImplementedError("TinyFish integration implemented by Person B")

    async def verify_claims_batch(self, claims: list[str]) -> list[dict[str, any]]:
        """Verify multiple claims in parallel. To be implemented by Person B."""
        raise NotImplementedError("TinyFish integration implemented by Person B")
