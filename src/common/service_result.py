from dataclasses import dataclass
from typing import Any, Literal

from src.enums.enum import ServiceResultEnum


@dataclass
class ServiceResult:
    status: Literal[ServiceResultEnum.FAILED, ServiceResultEnum.SUCCESS] = ServiceResultEnum.FAILED
    data: Any | None = None
    error: str | None = None
    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "data": self.data,
            "error": self.error,
        }