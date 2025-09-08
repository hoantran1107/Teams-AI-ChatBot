from typing import Optional

from pydantic import BaseModel, Field


class TableAnalysisGeneratedCode(BaseModel):
	"""Generated code for table analysis."""
	python_code: Optional[str] = Field(
		description=(
			"Python code generated for table analysis. If the code is not generated, these"
			"are possible values: NOT_AN_ANALYSIS_QUESTION, IRRELEVANT_QUESTION, UNKNOWN_ANSWER"
		)
	)
