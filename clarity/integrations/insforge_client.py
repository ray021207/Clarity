"""InsForge Backend-as-a-Service client for database operations."""

import json
import httpx
from typing import Any, Optional
from datetime import datetime

from clarity.config import settings
from clarity.models import TrustReport


class InsForgeClient:
    """Client for InsForge REST API (Postgres, Realtime, Auth)."""

    def __init__(self, api_url: str = "", api_key: str = ""):
        """Initialize InsForge client with credentials."""
        self.api_url = api_url or settings.insforge_url
        self.api_key = api_key or settings.insforge_api_key
        self.http_client = httpx.Client(timeout=30.0)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    def _auth_headers(self) -> dict[str, str]:
        """Build authorization headers."""
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def store_trust_report(self, report: TrustReport) -> dict[str, Any]:
        """
        Store a trust report in InsForge Postgres.
        
        Inserts into `trust_reports` table.
        """
        payload = {
            "report_id": report.report_id,
            "exchange_id": report.exchange_id,
            "timestamp": report.timestamp.isoformat(),
            "overall_score": report.overall_score,
            "overall_risk": report.overall_risk.value,
            "verified_report": report.to_dict(),  # Full report as JSON
            "model_used": report.model_used,
            "temperature": report.temperature,
            "tokens_used": report.tokens_used,
        }

        # POST to InsForge PostgREST endpoint
        url = f"{self.api_url}/rest/v1/trust_reports"
        headers = self._auth_headers()

        try:
            response = self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to store trust report in InsForge: {e}")

    def get_trust_report(self, report_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve a trust report from InsForge by report_id.
        """
        url = f"{self.api_url}/rest/v1/trust_reports?report_id=eq.{report_id}"
        headers = self._auth_headers()

        try:
            response = self.http_client.get(url, headers=headers)
            response.raise_for_status()
            results = response.json()
            return results[0] if results else None
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to retrieve trust report from InsForge: {e}")

    def list_trust_reports(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """
        List recent trust reports from InsForge.
        
        Returns paginated list, most recent first.
        """
        url = f"{self.api_url}/rest/v1/trust_reports?order=timestamp.desc&limit={limit}&offset={offset}"
        headers = self._auth_headers()

        try:
            response = self.http_client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to list trust reports from InsForge: {e}")

    def store_exchange_log(self, exchange_id: str, exchange_data: dict[str, Any]) -> dict[str, Any]:
        """
        Store a complete exchange log in InsForge.
        
        Inserts into `exchange_logs` table.
        """
        payload = {
            "exchange_id": exchange_id,
            "timestamp": datetime.utcnow().isoformat(),
            "exchange_data": exchange_data,  # Full capture as JSON
        }

        url = f"{self.api_url}/rest/v1/exchange_logs"
        headers = self._auth_headers()

        try:
            response = self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to store exchange log in InsForge: {e}")

    def get_realtime_url(self, table: str, filter_key: str, filter_value: str) -> str:
        """
        Generate InsForge Realtime WebSocket URL for subscription.
        
        Used to push live updates to dashboard when reports are generated.
        
        Example:
            ws_url = client.get_realtime_url("trust_reports", "report_id", "uuid-here")
        """
        # InsForge Realtime WebSocket pattern
        ws_url = (
            f"{self.api_url.replace('https://', 'wss://').replace('http://', 'ws://')}"
            f"/realtime/v1?apikey={self.api_key}"
            f"&eventsPerSecond=10"
        )
        return ws_url

    def create_tables(self) -> None:
        """
        Create trust_reports and exchange_logs tables if they don't exist.
        
        This should be called once during setup (see setup_db.py).
        """
        # SQL to create tables
        sql_trust_reports = """
        CREATE TABLE IF NOT EXISTS trust_reports (
            id BIGSERIAL PRIMARY KEY,
            report_id TEXT UNIQUE NOT NULL,
            exchange_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT NOW(),
            overall_score FLOAT NOT NULL,
            overall_risk TEXT NOT NULL,
            verified_report JSONB NOT NULL,
            model_used TEXT,
            temperature FLOAT,
            tokens_used INT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_trust_reports_report_id ON trust_reports(report_id);
        CREATE INDEX IF NOT EXISTS idx_trust_reports_exchange_id ON trust_reports(exchange_id);
        """

        sql_exchange_logs = """
        CREATE TABLE IF NOT EXISTS exchange_logs (
            id BIGSERIAL PRIMARY KEY,
            exchange_id TEXT UNIQUE NOT NULL,
            timestamp TIMESTAMP DEFAULT NOW(),
            exchange_data JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_exchange_logs_exchange_id ON exchange_logs(exchange_id);
        """

        # Execute via PostgREST RPC or direct SQL endpoint
        # For now, log that this should be done via InsForge console
        print("⚠️  Tables must be created via InsForge dashboard or SQL console.")
        print("SQL for trust_reports:")
        print(sql_trust_reports)
        print("\nSQL for exchange_logs:")
        print(sql_exchange_logs)
