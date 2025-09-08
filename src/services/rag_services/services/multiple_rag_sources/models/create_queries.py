from pydantic import BaseModel, Field


class Queries(BaseModel):
    source_name: str = Field(
        ...,
        description="The source name",
    )
    queries: list[str] = Field(
        ...,
        description="The list of 3-5 ENGLISH queries",
    )


class QueriesCollection(BaseModel):
    reasoning: str = Field(
        ...,
        description=(
            "Explain your overall query generation strategy, why you selected these "
            "specific sources, and how your queries address the user's information "
            "needs"
        ),
    )
    queries: list[Queries] = Field(
        ...,
        description=("The list of queries for each source. Each source should have 3-5 ENGLISH queries."),
    )
