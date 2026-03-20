from __future__ import annotations

import os
from dataclasses import dataclass, field

from a2a_servers.agent_store import DEFAULT_TABLE_NAME


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    url_mode: str
    forwarded_base_url: str
    log_level_name: str
    project_endpoint: str | None = None
    # Azure Table Storage – set one of these to enable DB-backed agent loading
    storage_connection_string: str | None = None
    storage_account_url: str | None = None
    agents_table_name: str = field(default=DEFAULT_TABLE_NAME)

    @property
    def use_db(self) -> bool:
        """True when DB credentials are configured."""
        return bool(self.storage_connection_string or self.storage_account_url)

    @property
    def public_base_url(self) -> str:
        if self.url_mode == "forwarded":
            if not self.forwarded_base_url:
                raise ValueError(
                    "A2A_FORWARDED_BASE_URL is required when A2A_URL_MODE=forwarded"
                )
            return self.forwarded_base_url.rstrip("/")

        return f"http://{self.host}:{self.port}"

    def agent_base_url_for(self, slug: str) -> str:
        return f"{self.public_base_url}/{slug.strip('/')}"

    def agent_card_url_for(self, slug: str) -> str:
        return f"{self.agent_base_url_for(slug)}/"


def load_server_settings(
    *,
    host: str | None = None,
    port: int | None = None,
    url_mode: str | None = None,
    forwarded_base_url: str | None = None,
    require_project_endpoint: bool = True,
) -> ServerSettings:
    resolved_url_mode = (
        (url_mode or os.getenv("A2A_URL_MODE") or "local").strip().lower()
    )
    if resolved_url_mode not in {"local", "forwarded"}:
        raise ValueError("A2A_URL_MODE must be either 'local' or 'forwarded'")

    project_endpoint = (os.getenv("AZURE_AI_PROJECT_ENDPOINT") or "").strip() or None
    if require_project_endpoint and project_endpoint is None:
        raise ValueError(
            "Missing required environment variable: AZURE_AI_PROJECT_ENDPOINT"
        )

    return ServerSettings(
        host=(host if host is not None else os.getenv("A2A_HOST", "localhost")).strip(),
        port=port if port is not None else int(os.getenv("A2A_PORT", "10007")),
        url_mode=resolved_url_mode,
        forwarded_base_url=(
            forwarded_base_url or os.getenv("A2A_FORWARDED_BASE_URL") or ""
        ).strip(),
        log_level_name=(os.getenv("LOG_LEVEL", "INFO")).strip().upper(),
        project_endpoint=project_endpoint,
        storage_connection_string=(
            os.getenv("AZURE_STORAGE_CONNECTION_STRING") or ""
        ).strip()
        or None,
        storage_account_url=(os.getenv("AZURE_STORAGE_ACCOUNT_URL") or "").strip()
        or None,
        agents_table_name=(os.getenv("A2A_AGENTS_TABLE") or DEFAULT_TABLE_NAME).strip(),
    )
