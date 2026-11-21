"""Pydantic-validated Python/React RPC bridge; explicitly authorized per operation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable
from pydantic import BaseModel


@dataclass(slots=True)
class Bridge:
    name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[..., Any]  # (validated_input, BridgeContext) -> output_model
    description: str = ""
    min_role: str | None = None

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", self.name) is None:
            raise ValueError("Bridge name must be a URL-safe slug")
        for model in (self.input_model, self.output_model):
            if not isinstance(model, type) or not issubclass(model, BaseModel):
                raise TypeError("Bridge input_model and output_model must be Pydantic BaseModel types")

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema(mode="validation"),
            "outputSchema": self.output_model.model_json_schema(mode="serialization"),
        }


@dataclass(slots=True)
class BridgeContext:
    principal: Any
    session: Any
