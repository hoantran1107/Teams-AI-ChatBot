from datetime import datetime

from pydantic import BaseModel, Field


class ConfluenceApiResponse(BaseModel):
    page_id: str = Field(alias="id")
    page_name: str = Field(alias="title")
    created_date: datetime
    updated_date: datetime
    version: int

    class Config:
        populate_by_name = True

    @classmethod
    def from_api_response(cls, data):
        return cls(
            id=data["id"],
            title=data["title"],
            created_date=data["history"]["createdDate"],
            updated_date=data["version"]["when"],
            version=data["version"]["number"],
        )
