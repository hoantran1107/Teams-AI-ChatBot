from pydantic import BaseModel, Field


class GradeDocuments(BaseModel):
	"""Binary score for relevance check on retrieved documents."""
	binary_scores: list[int] = Field(
		description="Documents are relevant to the question, 1 for relevant, 0 for irrelevant"
	)
