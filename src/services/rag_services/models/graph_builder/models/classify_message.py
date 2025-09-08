from typing import Literal
from pydantic import BaseModel, Field


class ClassifyMessage(BaseModel):
	category: Literal["greeting", "feedback", "mixed_feedback", "message"] = Field(
		...,
		description="Category of the message"
	)
	reason: str = Field(
		...,
		description="Reason why this instruction set is suitable for the update request"
	)
