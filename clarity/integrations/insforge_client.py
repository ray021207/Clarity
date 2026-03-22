"""InsForge Backend-as-a-Service client for database operations."""

import json
import logging
from typing import Any, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import Json

from clarity.config import settings
from clarity.models import TrustReport

logger = logging.getLogger(__name__)


class InsForgeClient:
    """Client for InsForge database (direct PostgreSQL or REST API)."""

    def __init__(self, database_url: str = "", api_url: str = "", api_key: str = ""):
        """Initialize InsForge client with credentials."""
        self.database_url = database_url or settings.insforge_database_url
        self.api_url = api_url or settings.insforge_url
        self.api_key = api_key or settings.insforge_api_key
        self.use_direct_db = bool(self.database_url)
        
        if self.use_direct_db:
            logger.info("InsForge using direct PostgreSQL connection")
        else:
            logger.warning("InsForge using REST API (slower). Consider using INSFORGE_DATABASE_URL")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    def _get_db_connection(self):
        """Get a PostgreSQL connection."""
        if not self.database_url:
            raise RuntimeError("INSFORGE_DATABASE_URL not configured")
        
        try:
            conn = psycopg2.connect(self.database_url)
            return conn
        except Exception as e:
            raise RuntimeError(f"Failed to connect to InsForge database: {e}")

    def store_trust_report(self, report: TrustReport) -> dict[str, Any]:
        """
        Store a trust report in InsForge.
        Uses direct PostgreSQL if configured, falls back to REST API.
        """
        
        if self.use_direct_db:
            return self._store_trust_report_direct(report)
        else:
            return self._store_trust_report_api(report)

    def _store_trust_report_direct(self, report: TrustReport) -> dict[str, Any]:
        """Store trust report via direct PostgreSQL."""
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            # Insert report
            cur.execute("""
                INSERT INTO trust_reports (
                    report_id, exchange_id, timestamp, overall_score, overall_risk,
                    verified_report, model_used, temperature, tokens_used
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, report_id, timestamp
            """, (
                report.report_id,
                report.exchange_id,
                report.timestamp,
                report.overall_score,
                report.overall_risk.value,
                Json(report.to_dict()),
                report.model_used,
                report.temperature,
                report.tokens_used,
            ))
            
            result = cur.fetchone()
            conn.commit()
            conn.close()
            
            return {
                "id": result[0],
                "report_id": result[1],
                "timestamp": str(result[2]),
                "status": "stored",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to store trust report: {e}")

    def _store_trust_report_api(self, report: TrustReport) -> dict[str, Any]:
        """Store trust report via REST API (legacy)."""
        import httpx
        
        payload = {
            "report_id": report.report_id,
            "exchange_id": report.exchange_id,
            "timestamp": report.timestamp.isoformat(),
            "overall_score": report.overall_score,
            "overall_risk": report.overall_risk.value,
            "verified_report": report.to_dict(),
            "model_used": report.model_used,
            "temperature": report.temperature,
            "tokens_used": report.tokens_used,
        }

        url = f"{self.api_url}/rest/v1/trust_reports"
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to store trust report via REST API: {e}")

    def get_trust_report(self, report_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a trust report by report_id."""
        
        if self.use_direct_db:
            return self._get_trust_report_direct(report_id)
        else:
            return self._get_trust_report_api(report_id)

    def _get_trust_report_direct(self, report_id: str) -> Optional[dict[str, Any]]:
        """Get trust report via direct PostgreSQL."""
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT * FROM trust_reports WHERE report_id = %s", (report_id,))
            row = cur.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Convert row to dict
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))
        except Exception as e:
            logger.error(f"Failed to retrieve trust report: {e}")
            return None

    def _get_trust_report_api(self, report_id: str) -> Optional[dict[str, Any]]:
        """Get trust report via REST API (legacy)."""
        import httpx
        
        url = f"{self.api_url}/rest/v1/trust_reports?report_id=eq.{report_id}"
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            response = httpx.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            results = response.json()
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to retrieve trust report via REST API: {e}")
            return None

    def list_trust_reports(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """List recent trust reports."""
        
        if self.use_direct_db:
            return self._list_trust_reports_direct(limit, offset)
        else:
            return self._list_trust_reports_api(limit, offset)

    def _list_trust_reports_direct(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """List trust reports via direct PostgreSQL."""
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute(
                "SELECT * FROM trust_reports ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                (limit, offset)
            )
            rows = cur.fetchall()
            conn.close()
            
            if not rows:
                return []
            
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list trust reports: {e}")
            return []

    def _list_trust_reports_api(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        """List trust reports via REST API (legacy)."""
        import httpx
        
        url = f"{self.api_url}/rest/v1/trust_reports?order=timestamp.desc&limit={limit}&offset={offset}"
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            response = httpx.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list trust reports via REST API: {e}")
            return []

    def store_exchange_log(self, exchange_id: str, exchange_data: dict[str, Any]) -> dict[str, Any]:
        """Store a complete exchange log."""
        
        if self.use_direct_db:
            return self._store_exchange_log_direct(exchange_id, exchange_data)
        else:
            return self._store_exchange_log_api(exchange_id, exchange_data)

    def _store_exchange_log_direct(self, exchange_id: str, exchange_data: dict[str, Any]) -> dict[str, Any]:
        """Store exchange log via direct PostgreSQL."""
        try:
            conn = self._get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO exchange_logs (exchange_id, timestamp, exchange_data)
                VALUES (%s, %s, %s)
                RETURNING id, exchange_id, timestamp
            """, (
                exchange_id,
                datetime.utcnow(),
                Json(exchange_data),
            ))
            
            result = cur.fetchone()
            conn.commit()
            conn.close()
            
            return {
                "id": result[0],
                "exchange_id": result[1],
                "timestamp": str(result[2]),
                "status": "stored",
            }
        except Exception as e:
            raise RuntimeError(f"Failed to store exchange log: {e}")

    def _store_exchange_log_api(self, exchange_id: str, exchange_data: dict[str, Any]) -> dict[str, Any]:
        """Store exchange log via REST API (legacy)."""
        import httpx
        
        payload = {
            "exchange_id": exchange_id,
            "timestamp": datetime.utcnow().isoformat(),
            "exchange_data": exchange_data,
        }

        url = f"{self.api_url}/rest/v1/exchange_logs"
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to store exchange log via REST API: {e}")

    def create_tables(self) -> None:
        """Create trust_reports and exchange_logs tables if they don't exist."""
        
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

        print("⚠️  Tables must be created via InsForge dashboard or SQL console.")
        print("SQL for trust_reports:")
        print(sql_trust_reports)
        print("\nSQL for exchange_logs:")
        print(sql_exchange_logs)
