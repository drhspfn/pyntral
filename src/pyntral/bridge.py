"""Pydantic-validated Python/React RPC bridge; explicitly authorized per operation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class BridgeFile:
    """Bounded, untrusted upload bytes. Verify actual content before processing."""
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class BridgeUpload:
    max_bytes: int = 5 * 1024 * 1024
    content_types: tuple[str, ...] = ("application/octet-stream",)

    def __post_init__(self) -> None:
        if type(self.max_bytes) is not int or not 1 <= self.max_bytes <= 64 * 1024 * 1024:
            raise ValueError("BridgeUpload max_bytes must be 1–64 MiB")
        if not isinstance(self.content_types, tuple) or not self.content_types or any(
            not isinstance(mime, str) or not re.fullmatch(r"[a-z0-9][a-z0-9!#@dataclass(slots=True)
class Bridge:^_.+-]*/(?:[a-z0-9][a-z0-9!#@dataclass(slots=True)
class Bridge:^_.+-]*|\*)", mime)
            for mime in self.content_types
        ):
            raise ValueError("BridgeUpload content_types must be explicit lowercase MIME types or type/*")

    def accepts(self, mime: str) -> bool:
        return any(mime == allowed or (allowed.endswith("/*") and mime.startswith(allowed[:-1]))
                   for allowed in self.content_types)


@dataclass(slots=True)
class Bridge:
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[..., Any]  # (validated_input, BridgeContext) -> output_model
    description: str = ""
    min_role: str | None = None
    upload: BridgeUpload | None = None

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", self.name) is None:
            raise ValueError("Bridge name must be a URL-safe slug")
        if self.upload is not None and not isinstance(self.upload, BridgeUpload):
            raise TypeError("upload must be BridgeUpload")
        for model in (self.input_model, self.output_model):
            if not isinstance(model, type) or not issubclass(model, BaseModel):
                raise TypeError("Bridge input_model and output_model must be Pydantic BaseModel types")

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(mode="validation"),
            "outputSchema": self.output_model.model_json_schema(mode="serialization"),
            **({"upload": {"maxBytes": self.upload.max_bytes, "contentTypes": list(self.upload.content_types)}} if self.upload else {}),
        }


@dataclass(slots=True)
class BridgeContext:
    principal: Any
    session: Any
    file: BridgeFile | None = None
