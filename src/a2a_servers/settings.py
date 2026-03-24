from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    url_mode: str
    forwarded_base_url: str
    log_level_name: str

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
) -> ServerSettings:
    resolved_url_mode = (
        (url_mode or os.getenv("A2A_URL_MODE") or "local").strip().lower()
    )
    if resolved_url_mode not in {"local", "forwarded"}:
        raise ValueError("A2A_URL_MODE must be either 'local' or 'forwarded'")

    return ServerSettings(
        host=(host if host is not None else os.getenv("A2A_HOST", "localhost")).strip(),
        port=port if port is not None else int(os.getenv("A2A_PORT", "10007")),
        url_mode=resolved_url_mode,
        forwarded_base_url=(
            forwarded_base_url or os.getenv("A2A_FORWARDED_BASE_URL") or ""
        ).strip(),
        log_level_name=(os.getenv("LOG_LEVEL", "INFO")).strip().upper(),
    )
