from datetime import datetime

from pydantic import BaseModel, Field


class Content(BaseModel):
    id: str


class ConfluenceCQLInstance(BaseModel):
    content: Content
    title: str
    last_modified: datetime = Field(alias="lastModified")

    @property
    def id(self) -> str:
        return self.content.id

    def to_dict(self):
        return {"page_id": self.id, "title": self.title, "last_modified": self.last_modified}
