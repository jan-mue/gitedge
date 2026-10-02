"""Abstract blob storage client with Vercel Blob and MinIO implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import botocore.exceptions  # type: ignore[import-untyped]
from aiobotocore.session import get_session  # type: ignore[import-untyped]
from vercel.blob import Access, AsyncBlobClient, BlobNotFoundError

if TYPE_CHECKING:
    from aiobotocore.session import ClientCreatorContext

logger = logging.getLogger(__name__)


class BlobStorageClient(ABC):
    """Abstract base class for blob storage operations.

    Provides a unified interface for storing and retrieving binary data
    (Git pack files, index files, etc.) from different blob storage backends.
    """

    @abstractmethod
    async def put(self, key: str, data: bytes) -> None:
        """Store binary data at the given key.

        Args:
            key: Storage key/path for the data.
            data: Binary data to store.
        """

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Retrieve binary data for the given key.

        Args:
            key: Storage key/path to retrieve.

        Returns:
            The binary data, or None if not found.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete data at the given key.

        Args:
            key: Storage key/path to delete.
        """

    @abstractmethod
    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys with the given prefix.

        Args:
            prefix: Key prefix to filter by.

        Returns:
            List of matching keys.
        """


class VercelBlobClient(BlobStorageClient):
    """Blob storage client using Vercel Blob Storage.

    Uses the vercel.blob.AsyncBlobClient SDK for async operations.
    The VERCEL_BLOB_TOKEN environment variable must be set.
    """

    def __init__(self, token: str | None = None, access: Access = "private") -> None:
        """Initialize the Vercel Blob client.

        Args:
            token: Optional explicit token. If None, reads from VERCEL_BLOB_TOKEN env var.
            access: Access mode of the Blob store. Must match the store's configuration,
                otherwise Vercel rejects the request.
        """
        self._client = AsyncBlobClient(token=token) if token else AsyncBlobClient()
        self._access = access

    async def put(self, key: str, data: bytes) -> None:
        """Store binary data in Vercel Blob Storage."""
        await self._client.put(
            key,
            data,
            access=self._access,
            content_type="application/octet-stream",
            add_random_suffix=False,
        )

    async def get(self, key: str) -> bytes | None:
        """Retrieve binary data from Vercel Blob Storage."""
        try:
            result = await self._client.get(key, access=self._access)
        except BlobNotFoundError:
            logger.debug("Blob not found: %s", key)
            return None
        if result is None:
            return None
        return result.content  # type: ignore[no-any-return]

    async def delete(self, key: str) -> None:
        """Delete data from Vercel Blob Storage."""
        try:
            await self._client.delete([key])
        except BlobNotFoundError:
            logger.debug("Blob not found while deleting: %s", key)

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys with the given prefix in Vercel Blob Storage."""
        listing = await self._client.list_objects(prefix=prefix)
        return [blob.pathname for blob in listing.blobs]


class S3Client(BlobStorageClient):
    """Blob storage client using S3 (e.g. MinIO) via aiobotocore.

    Used for integration testing as a local replacement for Vercel Blob Storage.
    """

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False) -> None:
        """Initialize the S3 client.

        Args:
            endpoint: S3 server endpoint (host:port).
            access_key: S3 access key.
            secret_key: S3 secret key.
            bucket: Bucket name to use.
            secure: Whether to use HTTPS.
        """
        self._session = get_session()
        protocol = "https" if secure else "http"
        self._endpoint_url = f"{protocol}://{endpoint}"
        self._access_key = access_key
        self._secret_key = secret_key
        self._bucket = bucket
        self._bucket_created = False

    def _create_client(self) -> ClientCreatorContext:
        """Create a new aiobotocore S3 client."""
        return self._session.create_client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
        )

    async def _ensure_bucket(self) -> None:
        """Ensure the target bucket exists, creating it if necessary."""
        if self._bucket_created:
            return

        async with self._create_client() as client:
            try:
                await client.head_bucket(Bucket=self._bucket)
            except botocore.exceptions.ClientError as e:
                error_code = str(e.response.get("Error", {}).get("Code", ""))
                if error_code == "404":
                    await client.create_bucket(Bucket=self._bucket)
                else:
                    raise
            self._bucket_created = True

    async def put(self, key: str, data: bytes) -> None:
        """Store binary data in S3."""
        await self._ensure_bucket()
        async with self._create_client() as client:
            await client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType="application/octet-stream",
            )

    async def get(self, key: str) -> bytes | None:
        """Retrieve binary data from S3."""
        await self._ensure_bucket()
        try:
            async with self._create_client() as client:
                response = await client.get_object(Bucket=self._bucket, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()  # type: ignore[no-any-return]
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                logger.debug("Object not found in S3: %s", key)
                return None
            raise

    async def delete(self, key: str) -> None:
        """Delete data from S3."""
        await self._ensure_bucket()
        async with self._create_client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys with the given prefix in S3."""
        await self._ensure_bucket()
        keys = []
        async with self._create_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                keys.extend([obj["Key"] for obj in page.get("Contents", []) if "Key" in obj])
        return keys
