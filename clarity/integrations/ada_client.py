"""Ada client stub for conversational trust report explanation (Person C will implement)."""

from clarity.config import settings


class AdaClient:
    """Stub for Ada conversational explainer. Person C will implement."""

    def __init__(self, api_url: str = "", api_key: str = ""):
        """Initialize Ada client."""
        self.api_url = api_url or settings.ada_api_url
        self.api_key = api_key or settings.ada_api_key

    async def explain_trust_report(self, summary: dict, question: str) -> dict[str, str]:
        """Explain a trust report in plain language. To be implemented by Person C."""
        raise NotImplementedError("Ada integration implemented by Person C")

    def _local_explanation(self, summary: dict, question: str) -> dict[str, str]:
        """Fallback local explanation if Ada is unavailable."""
        raise NotImplementedError("Local explanation fallback to be implemented by Person C")
