from marshmallow import Schema, ValidationError, fields
from pydantic import BaseModel, Field

from src.constants.api_constant import FieldDescription
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import SourceType


class EnumField(fields.Field):
    def __init__(self, enum_class, *args, **kwargs):
        self.enum_class = enum_class
        super().__init__(*args, **kwargs)

    def _serialize(self, value, attr, obj):
        if value is None:
            return None
        return value.value if hasattr(value, "value") else value

    def _deserialize(self, value, attr, data, **kwargs):
        try:
            return self.enum_class(value)
        except ValueError:
            raise ValidationError(f"Must be one of: {[e.value for e in self.enum_class]}")


class RagConfluenceManagePostSchema(BaseModel):
    page_id: str = Field(..., min_length=1, description="The id of the page")
    collection_id: str = Field(..., min_length=1, description=FieldDescription.COLLECTION_ID)


class RagConfluenceManageGetSchema(BaseModel):
    source_name: str | None = Field(None, min_length=1, description=FieldDescription.SOURCE_NAME)


class RagConfluenceManageDeleteSchema(BaseModel):
    page_ids: list[str] = Field(..., min_length=1, description="The ids of the pages")
    source_name: str = Field(..., min_length=1, description="The name of the source")


class RagPagesManageGetSchema(BaseModel):
    source_name: str | None = Field(None, min_length=1, description=FieldDescription.SOURCE_NAME)


class ManageSourcePostSchema(Schema):
    source_name = fields.String(required=True)
    source_type = EnumField(
        SourceType,
        required=True,
        metadata={
            "description": "Type of the source",
            "enum": [e.value for e in SourceType],
        },
    )
    source_path = fields.String(
        required=False,
        metadata={"description": "Path to the source. If source type is GCP, this field must be provided."},
    )


class RagSourceDeleteSchema(Schema):
    source_name = fields.String(required=True)
