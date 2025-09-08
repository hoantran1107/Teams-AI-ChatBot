from typing import Optional

from pydantic import BaseModel, Field


class UpdatedInstruction(BaseModel):
	name: str = Field(..., description="Name of instruction set")
	reason: str = Field(
		...,
		description="Reason why this instruction set is suitable for the update request"
	)
	updated_instruction: list[str] = Field(
		...,
		description="List of updated instructions"
	)


class AllUpdatedInstructions(BaseModel):
	updates: Optional[list[UpdatedInstruction]] = Field(default_factory=list)