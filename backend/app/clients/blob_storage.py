"""Synchronous object storage for Git commands running in worker threads."""

from __future__ import annotations

import logging
import tempfile
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, BinaryIO, override

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from vercel.blob import Access, BlobClient, BlobNotFoundError

if TYPE_CHECKING:
    from collections.abc import Generator
    from os import PathLike

logger = logging.getLogger(__name__)


class BlobStorageClient(ABC):
    """Streaming object storage for synchronous Git operations."""

    @abstractmethod
    def put(self, key: str, data: bytes | BinaryIO) -> None:
        """Upload bytes or a readable file at its current position."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete an object."""

    @abstractmethod
    def list_keys(self, prefix: str) -> list[str]:
        """List every object key under a prefix."""

    @abstractmethod
    def download(self, key: str, path: str | PathLike[str]) -> None:
        """Stream an object to disk, raising FileNotFoundError for missing keys."""

    @contextmanager
    def open(self, key: str) -> Generator[BinaryIO]:
        """Open a temporary download for the lifetime of its reader."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "object"
            self.download(key, path)
            with path.open("rb") as stream:
                yield stream


class VercelBlobClient(BlobStorageClient):
    """Vercel's synchronous Blob SDK, preserving private access and immutable caching."""

    def __init__(self, token: str | None = None, access: Access = "private") -> None:
        """Bind the configured Blob store."""
        self._client = BlobClient(token=token) if token else BlobClient()
        self._access = access

    @override
    def put(self, key: str, data: bytes | BinaryIO) -> None:
        """Upload an immutable Git pack or index."""
        self._client.put(
            key,
            data,
            access=self._access,
            content_type="application/octet-stream",
            add_random_suffix=False,
            overwrite=True,
            cache_control_max_age=31536000,
        )

    @override
    def download(self, key: str, path: str | PathLike[str]) -> None:
        """Stream a download to disk rather than materializing its entire body."""
        try:
            self._client.download_file(key, path, access=self._access)
        except BlobNotFoundError as error:
            raise FileNotFoundError(key) from error

    @override
    def delete(self, key: str) -> None:
        """Delete an object."""
        try:
            self._client.delete([key])
        except BlobNotFoundError:
            logger.debug("Blob not found while deleting: %s", key)

    @override
    def list_keys(self, prefix: str) -> list[str]:
        """Read every listing page."""
        keys: list[str] = []
        cursor = None
        while True:
            listing = self._client.list_objects(prefix=prefix, cursor=cursor, limit=1000)
            keys.extend(blob.pathname for blob in listing.blobs)
            if not listing.has_more:
                return keys
            if not listing.cursor:
                raise ValueError("Blob listing has more results but no pagination cursor")
            cursor = listing.cursor


class S3Client(BlobStorageClient):
    """Synchronous boto3 adapter for S3-compatible object storage."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False) -> None:
        """Create a thread-safe client shared by worker-thread Git operations."""
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if secure else 'http'}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self._bucket = bucket
        self._bucket_created = False
        self._bucket_lock = Lock()

    def _ensure_bucket(self) -> None:
        with self._bucket_lock:
            if self._bucket_created:
                return
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except ClientError as error:
                if str(error.response.get("Error", {}).get("Code", "")) != "404":
                    raise
                self._client.create_bucket(Bucket=self._bucket)
            self._bucket_created = True

    @override
    def put(self, key: str, data: bytes | BinaryIO) -> None:
        """Stream an upload through boto3."""
        self._ensure_bucket()
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType="application/octet-stream")

    @override
    def download(self, key: str, path: str | PathLike[str]) -> None:
        """Stream to a local file for Dulwich's memory-mapped readers."""
        self._ensure_bucket()
        try:
            self._client.download_file(self._bucket, key, str(path))
        except ClientError as error:
            if str(error.response.get("Error", {}).get("Code")) in {"404", "NoSuchKey"}:
                raise FileNotFoundError(key) from error
            raise

    @override
    def delete(self, key: str) -> None:
        """Delete an object."""
        self._ensure_bucket()
        self._client.delete_object(Bucket=self._bucket, Key=key)

    @override
    def list_keys(self, prefix: str) -> list[str]:
        """List all matching keys across S3 pages."""
        self._ensure_bucket()
        pages = self._client.get_paginator("list_objects_v2").paginate(Bucket=self._bucket, Prefix=prefix)
        return [obj["Key"] for page in pages for obj in page.get("Contents", [])]
