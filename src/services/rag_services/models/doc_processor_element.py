from typing import Any

from pydantic import BaseModel


class DocProcessorElement(BaseModel):
    """DocProcessorElement is a class that represents a processed element of a document."""

    type: str
    text: Any
    base64: str | None = None  # Optional base_64 field
    metadata: dict[str, Any] | None = None  # Optional metadata field
