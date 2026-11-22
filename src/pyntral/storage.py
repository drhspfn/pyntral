"""Storage adapters for authenticated resource attachments.

Objects are always addressed by opaque server-generated keys, never by
client-supplied filesystem paths or S3 URLs.
"""
from __future__ import annotations

import asyncio
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# An empty owner ID cannot be addressed by an upload route. Pending entries retain
# their resource so an admin only cleans up objects belonging to its own resources.
_PENDING_DELETE_RECORD = ""


class UploadBase(DeclarativeBase):
    pass


class UploadEntry(UploadBase):
    __tablename__ = "pyntral_uploads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[str] = mapped_column(String(120), nullable=False)
    object_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(240), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)


class StorageBackend(Protocol):
    async def put(self, key: str, content: bytes, mime_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None:
        """Delete an object idempotently, including when it is already absent."""
        ...


@dataclass(slots=True)
class LocalStorage:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not key or any(char not in "0123456789abcdef" for char in key):
            raise ValueError("Invalid storage key")
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Invalid storage path")
        return target

    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        target = self._path(key)
        def write():
            temp = target.with_name(target.name + ".tmp-" + uuid4().hex)
            try:
                with temp.open("xb") as stream:
                    stream.write(content)
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, missing_ok=True)


@dataclass(slots=True)
class S3Storage:
    """Boto3 storage for AWS S3 or S3-compatible MinIO endpoints.

    Requires `pip install pyntral[s3]`. Credentials are provided by the normal
    boto3 credential provider chain, never embedded in Pyntral metadata.
    """

    bucket: str
    endpoint_url: str | None = None
    region_name: str | None = None
    prefix: str = "pyntral/"

    def _client(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install pyntral[s3] to enable S3/MinIO uploads") from exc
        return boto3.client("s3", endpoint_url=self.endpoint_url, region_name=self.region_name)

    def _key(self, key: str) -> str:
        if not key or any(char not in "0123456789abcdef" for char in key):
            raise ValueError("Invalid storage key")
        return self.prefix + key

    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        def store():
            self._client().put_object(Bucket=self.bucket, Key=self._key(key), Body=content, ContentType=mime_type)
        await asyncio.to_thread(store)

    async def get(self, key: str) -> bytes:
        def fetch():
            from botocore.exceptions import ClientError
            try:
                obj = self._client().get_object(Bucket=self.bucket, Key=self._key(key))
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "NotFound", "404"):
                    raise FileNotFoundError from exc
                raise
            try:
                return obj["Body"].read()
            finally:
                obj["Body"].close()
        return await asyncio.to_thread(fetch)

    async def delete(self, key: str) -> None:
        def remove():
            self._client().delete_object(Bucket=self.bucket, Key=self._key(key))
        await asyncio.to_thread(remove)


def safe_upload_name(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    # Avoid CRLF header injection and path separators.
    name = "".join(c for c in name if c.isprintable() and c not in "\\/\r\n")[:180]
    return name or "attachment"


def normalize_mime(value: str, name: str) -> str:
    mime = value.split(";", 1)[0].strip().lower()
    if not mime or "/" not in mime:
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if len(mime) > 120 or any(ord(char) < 32 or ord(char) > 126 for char in mime):
        raise ValueError("Invalid content type")
    return mime
