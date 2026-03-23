from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class ConfigurationSource(Protocol):
    """Protocol for configuration sources (local filesystem or Azure Blob Storage)."""

    async def list_config_files(self, pattern: str) -> list[str]:
        """List configuration files matching the pattern."""
        ...

    async def read_config_file(self, filename: str) -> bytes:
        """Read a configuration file and return its content as bytes."""
        ...

    async def get_last_modified(self, filename: str) -> datetime | None:
        """Get the last modified time of a configuration file."""
        ...

    def get_source_info(self) -> dict[str, str]:
        """Get information about the configuration source."""
        ...


class LocalFileSource:
    """Configuration source that reads from local filesystem."""

    def __init__(self, directory: Path):
        self.directory = directory
        logger.info(f"Using local file configuration source: {directory}")

    async def list_config_files(self, pattern: str) -> list[str]:
        """List configuration files matching the pattern."""
        if not self.directory.exists():
            raise FileNotFoundError(f"Config directory not found: {self.directory}")
        if not self.directory.is_dir():
            raise NotADirectoryError(f"Config path is not a directory: {self.directory}")

        paths = sorted(self.directory.glob(pattern))
        return [path.name for path in paths]

    async def read_config_file(self, filename: str) -> bytes:
        """Read a configuration file and return its content as bytes."""
        file_path = self.directory / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with file_path.open("rb") as f:
            return f.read()

    async def get_last_modified(self, filename: str) -> datetime | None:
        """Get the last modified time of a configuration file."""
        file_path = self.directory / filename
        if not file_path.exists():
            return None
        return datetime.fromtimestamp(file_path.stat().st_mtime)

    def get_source_info(self) -> dict[str, str]:
        """Get information about the configuration source."""
        return {
            "type": "local_filesystem",
            "directory": str(self.directory.resolve()),
        }


class AzureBlobSource:
    """Configuration source that reads from Azure Blob Storage."""

    def __init__(
        self,
        connection_string: str | None = None,
        container_name: str = "agent-configs",
        blob_prefix: str = "",
    ):
        from azure.storage.blob.aio import ContainerClient
        from azure.identity.aio import DefaultAzureCredential

        self.container_name = container_name
        self.blob_prefix = blob_prefix

        # Support both connection string and managed identity authentication
        if connection_string:
            self.container_client = ContainerClient.from_connection_string(
                connection_string, container_name
            )
            auth_method = "connection_string"
        else:
            # Use managed identity via DefaultAzureCredential
            account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
            if not account_url:
                raise ValueError(
                    "AZURE_STORAGE_ACCOUNT_URL required when not using connection string"
                )
            credential = DefaultAzureCredential()
            self.container_client = ContainerClient(
                account_url=account_url,
                container_name=container_name,
                credential=credential,
            )
            auth_method = "managed_identity"

        logger.info(
            f"Using Azure Blob configuration source: container={container_name}, "
            f"prefix={blob_prefix or '(root)'}, auth={auth_method}"
        )

    async def list_config_files(self, pattern: str) -> list[str]:
        """List configuration files matching the pattern.

        For Azure Blob Storage, we list all blobs with the given prefix
        and filter by the pattern (e.g., *_agent.toml).
        """
        import fnmatch

        # Convert glob pattern to filter blobs
        # pattern is like "*_agent.toml"
        prefix = self.blob_prefix

        blob_names = []
        async for blob in self.container_client.list_blobs(name_starts_with=prefix):
            blob_name = blob.name
            # Remove prefix to get relative name
            if prefix and blob_name.startswith(prefix):
                relative_name = blob_name[len(prefix) :].lstrip("/")
            else:
                relative_name = blob_name

            # Filter by pattern
            if fnmatch.fnmatch(relative_name, pattern):
                blob_names.append(blob_name)

        return sorted(blob_names)

    async def read_config_file(self, filename: str) -> bytes:
        """Read a configuration file and return its content as bytes."""
        blob_name = f"{self.blob_prefix}/{filename}".strip("/")
        blob_client = self.container_client.get_blob_client(blob_name)

        try:
            download_stream = await blob_client.download_blob()
            content = await download_stream.readall()
            return content
        except Exception as e:
            raise FileNotFoundError(f"Blob not found: {blob_name}") from e

    async def get_last_modified(self, filename: str) -> datetime | None:
        """Get the last modified time of a configuration file."""
        blob_name = f"{self.blob_prefix}/{filename}".strip("/")
        blob_client = self.container_client.get_blob_client(blob_name)

        try:
            properties = await blob_client.get_blob_properties()
            return properties.last_modified
        except Exception:
            return None

    def get_source_info(self) -> dict[str, str]:
        """Get information about the configuration source."""
        return {
            "type": "azure_blob_storage",
            "container": self.container_name,
            "prefix": self.blob_prefix or "(root)",
        }

    async def close(self):
        """Close the container client."""
        await self.container_client.close()


@dataclass
class ConfigurationMetadata:
    """Metadata about loaded configuration."""

    source_type: str
    loaded_at: datetime
    file_count: int
    source_info: dict[str, str]


class ConfigurationLoader:
    """Loads agent configuration with caching and hot-reload support."""

    def __init__(
        self,
        source: ConfigurationSource,
        cache_ttl_seconds: int = 60,
    ):
        self.source = source
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cached_configs: dict[str, tuple[bytes, datetime]] = {}
        self._last_list_time: datetime | None = None
        self._cached_file_list: list[str] = []

    async def list_config_files(
        self, pattern: str, use_cache: bool = True
    ) -> list[str]:
        """List configuration files, optionally using cache."""
        now = datetime.now()

        if (
            use_cache
            and self._last_list_time
            and (now - self._last_list_time) < self.cache_ttl
        ):
            logger.debug("Using cached file list")
            return self._cached_file_list

        logger.info(f"Listing configuration files with pattern: {pattern}")
        files = await self.source.list_config_files(pattern)
        self._cached_file_list = files
        self._last_list_time = now
        return files

    async def read_config_file(
        self, filename: str, use_cache: bool = True
    ) -> dict[str, object]:
        """Read and parse a configuration file, optionally using cache."""
        now = datetime.now()

        if use_cache and filename in self._cached_configs:
            cached_content, cached_time = self._cached_configs[filename]
            if (now - cached_time) < self.cache_ttl:
                logger.debug(f"Using cached config for {filename}")
                return tomllib.loads(cached_content.decode("utf-8"))

        logger.info(f"Loading configuration file: {filename}")
        content = await self.source.read_config_file(filename)
        self._cached_configs[filename] = (content, now)

        return tomllib.loads(content.decode("utf-8"))

    async def reload_all(self) -> None:
        """Force reload of all configurations by clearing the cache."""
        logger.info("Clearing configuration cache")
        self._cached_configs.clear()
        self._last_list_time = None
        self._cached_file_list = []

    def get_metadata(self) -> ConfigurationMetadata:
        """Get metadata about the current configuration state."""
        return ConfigurationMetadata(
            source_type=self.source.get_source_info()["type"],
            loaded_at=self._last_list_time or datetime.now(),
            file_count=len(self._cached_file_list),
            source_info=self.source.get_source_info(),
        )


def create_config_source(
    config_dir: str | None = None,
    use_azure_blob: bool | None = None,
) -> ConfigurationSource:
    """Create a configuration source based on environment variables.

    Priority:
    1. If use_azure_blob is explicitly True or AZURE_BLOB_CONFIG_SOURCE=true, use Azure Blob
    2. If config_dir or A2A_AGENT_CONFIG_DIR is set, use local filesystem
    3. Default to local filesystem with default directory

    Environment variables:
    - AZURE_BLOB_CONFIG_SOURCE: Set to "true" to enable Azure Blob Storage
    - AZURE_STORAGE_CONNECTION_STRING: Connection string for Azure Storage (optional)
    - AZURE_STORAGE_ACCOUNT_URL: Storage account URL for managed identity auth
    - AZURE_BLOB_CONTAINER_NAME: Container name (default: "agent-configs")
    - AZURE_BLOB_PREFIX: Blob prefix/folder (default: "")
    - A2A_AGENT_CONFIG_DIR: Local directory for config files
    """
    # Check if Azure Blob should be used
    use_blob = use_azure_blob or os.getenv("AZURE_BLOB_CONFIG_SOURCE", "").lower() in (
        "true",
        "1",
        "yes",
    )

    if use_blob:
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("AZURE_BLOB_CONTAINER_NAME", "agent-configs")
        blob_prefix = os.getenv("AZURE_BLOB_PREFIX", "")

        return AzureBlobSource(
            connection_string=connection_string,
            container_name=container_name,
            blob_prefix=blob_prefix,
        )
    else:
        # Use local filesystem
        from agent_definition import resolve_agent_config_dir

        directory = resolve_agent_config_dir(config_dir)
        return LocalFileSource(directory)
