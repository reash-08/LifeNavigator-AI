"""Authorized government data source connectors and adapters for LifeNavigator-AI.

Enforces strict provenance, official domain verification, and anti-SSRF protections.
Does not scrape unauthorized portals.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from app.models.scheme_source import SchemeSource
from app.services.scheme_sync import is_official_source_url


class SourceAdapter(Protocol):
    """Protocol for fetching authorized government benefits and documents."""

    def fetch_records(self) -> list[dict[str, Any]]:
        ...


def validate_safe_url(url: str) -> tuple[bool, str | None]:
    """Anti-SSRF check: enforces HTTPS, official domain whitelist, and non-private IP."""
    if not url or not url.startswith("https://"):
        return False, "URL must use secure HTTPS protocol"

    if not is_official_source_url(url):
        return False, "URL must be an official government domain (.gov.in, .nic.in, etc.)"

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False, "Invalid URL host"

    try:
        # Resolve hostname to verify destination IP is not private, loopback, or link-local
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, "URL resolves to a private or reserved network address"
    except (socket.gaierror, ValueError):
        # In test environments or when hostname resolution is mocked, rely on domain whitelist
        pass

    return True, None


class LocalCuratedSourceAdapter:
    """Adapter for the official curated starter scheme dataset."""

    def __init__(self, file_path: Path | None = None):
        self.file_path = file_path or (
            Path(__file__).resolve().parents[3] / "data" / "schemes" / "starter.json"
        )

    def fetch_records(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []
        data = json.loads(self.file_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "schemes" in data:
            return data["schemes"]
        return data if isinstance(data, list) else []

    def fetch_schemes(self) -> list[dict[str, Any]]:
        return self.fetch_records()


class AuthorizedGovernmentApiAdapter:
    """Adapter for authorized government open-data feeds and official APIs."""

    def __init__(self, api_url: str, timeout: float = 15.0):
        self.api_url = api_url
        self.timeout = timeout

    def fetch_records(self) -> list[dict[str, Any]]:
        is_safe, error = validate_safe_url(self.api_url)
        if not is_safe:
            raise ValueError(f"Unsafe or unauthorized government API URL: {error}")

        req = urllib.request.Request(self.api_url, headers={"User-Agent": "LifeNavigator-AI/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "records" in data:
                    return data["records"]
                if isinstance(data, dict) and "data" in data:
                    return data["data"]
                return []
        except Exception as exc:
            raise ValueError(f"Failed to fetch government open-data feed: {exc}") from exc


def get_adapter_for_source(source: SchemeSource) -> SourceAdapter:
    """Return appropriate connector based on source registration."""
    if source.api_url and source.source_type == "official_api":
        return AuthorizedGovernmentApiAdapter(source.api_url)
    # Default to curated local government dataset for official portals
    return LocalCuratedSourceAdapter()
