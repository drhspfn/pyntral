"""Pydantic validation of admin write payloads without exposing user input."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError



def validate_payload(model: type[BaseModel] | None, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate declared fields, keep unrelated authorized fields unchanged.

    ``exclude_unset`` avoids writing model defaults not supplied by the caller.
    This validation never grants field permissions; the caller checks the
    output against the same ACL as the original request.
    """
    if model is None:
        return payload
    from .orm import AdminError
    try:
        parsed = model.model_validate(payload)
    except ValidationError as exc:
        # Never include raw input or arbitrary exception context (may include passwords).
        fields = sorted({str(item["loc"][0]) for item in exc.errors()
                         if item.get("loc")})
        raise AdminError(422, "Resource input validation failed", "validation_error",
                         {"fields": fields}) from None
    output = parsed.model_dump(exclude_unset=True)
    if not set(output).issubset(payload):
        raise AdminError(422, "Validator produced unexpected fields", "validation_error")
    return {**payload, **output}
