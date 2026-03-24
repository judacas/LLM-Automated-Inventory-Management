from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from config_loader import prepare_agent_config_location


def _write_agent_zip(tmp_path: Path) -> Path:
    bundle_root = tmp_path / "bundle"
    agents_dir = bundle_root / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agents_dir / "math_agent.toml"
    agent_file.write_text(
        "\n".join(
            [
                "[a2a]",
                "name = 'Math Agent'",
                "description = 'desc'",
                "version = '1.0.0'",
                "health_message = 'ok'",
                "",
                "[foundry]",
                "agent_name = 'math'",
                "",
                "[[skills]]",
                "id = 'math'",
                "name = 'Math'",
                "description = 'desc'",
            ]
        ),
        encoding="utf-8",
    )

    archive_path = tmp_path / "agents.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(agent_file, arcname="agents/math_agent.toml")
    return archive_path


def test_prepare_prefers_url_over_dir(tmp_path: Path) -> None:
    archive = _write_agent_zip(tmp_path)
    local_dir = tmp_path / "local"
    local_dir.mkdir()
    location = prepare_agent_config_location(
        config_dir=str(local_dir),
        config_url=archive.as_uri(),
    )

    assert location.directory.exists()
    toml_files = list(location.directory.glob("*_agent.toml"))
    assert toml_files, "downloaded archive should surface agent configs"
    assert location.source.startswith("url:")


def test_prepare_returns_explicit_directory(tmp_path: Path) -> None:
    local_dir = tmp_path / "local_agents"
    local_dir.mkdir()
    (local_dir / "quote_agent.toml").write_text(
        "[a2a]\nname='Quote'\ndescription='d'\nversion='1'\nhealth_message='ok'\n\n"
        "[foundry]\nagent_name='quote'\n\n[[skills]]\nid='s'\nname='S'\n"
        "description='d'\n",
        encoding="utf-8",
    )

    location = prepare_agent_config_location(config_dir=str(local_dir))
    assert location.directory == local_dir
    assert location.source.endswith(str(local_dir))


def test_prepare_rejects_non_http_file_scheme() -> None:
    with pytest.raises(ValueError):
        prepare_agent_config_location(config_url="ftp://example.com/agents.zip")
