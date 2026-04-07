from __future__ import annotations

import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from agent_definition import AGENT_CONFIG_GLOB, resolve_agent_config_dir


@dataclass(frozen=True)
class AgentConfigLocation:
    directory: Path
    source: str


def prepare_agent_config_location(
    *,
    config_dir: str | None = None,
    config_url: str | None = None,
) -> AgentConfigLocation:
    """
    Resolve where to read agent configs from.

    Precedence:
    1. explicit config_url argument
    2. A2A_AGENT_CONFIG_URL environment variable
    3. explicit config_dir argument
    4. A2A_AGENT_CONFIG_DIR environment variable
    5. bundled agents/ folder
    """
    resolved_url = (config_url or os.getenv("A2A_AGENT_CONFIG_URL") or "").strip()
    if resolved_url:
        directory = _download_config_archive(resolved_url)
        return AgentConfigLocation(
            directory=directory,
            source=f"url:{resolved_url}",
        )

    directory = resolve_agent_config_dir(config_dir)
    return AgentConfigLocation(directory=directory, source=f"dir:{directory}")


def _download_config_archive(url: str) -> Path:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix != ".zip":
        raise ValueError("A2A_AGENT_CONFIG_URL must point to a .zip archive")

    archive_path: Path
    if parsed.scheme in {"http", "https"}:
        archive_path = _download_http_archive(url)
    elif parsed.scheme == "file":
        archive_path = Path(parsed.path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Agent config archive not found: {archive_path}")
    else:
        raise ValueError("A2A_AGENT_CONFIG_URL must use http, https, or file scheme")

    extracted_dir = _extract_archive(archive_path)
    # clean up downloaded temp file if we created one
    if archive_path.exists() and parsed.scheme in {"http", "https"}:
        archive_path.unlink()
    return extracted_dir


def _download_http_archive(url: str) -> Path:
    fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="a2a_agent_configs_")
    os.close(fd)
    tmp_file = Path(tmp_path)
    with httpx.stream("GET", url, follow_redirects=True, timeout=30.0) as response:
        response.raise_for_status()
        with tmp_file.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    return tmp_file


def _extract_archive(archive_path: Path) -> Path:
    if not archive_path.exists():
        raise FileNotFoundError(f"Agent config archive not found: {archive_path}")

    target_root = Path(tempfile.mkdtemp(prefix="a2a_agent_configs_"))
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(target_root)

    root_matches = list(target_root.glob(AGENT_CONFIG_GLOB))
    if root_matches:
        return target_root

    for candidate in target_root.rglob(AGENT_CONFIG_GLOB):
        return candidate.parent

    raise FileNotFoundError(
        "Downloaded agent config archive did not contain any *_agent.toml files"
    )
