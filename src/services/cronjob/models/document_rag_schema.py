from marshmallow import Schema, fields


class CronJobAPISchema(Schema):
    collection = fields.String(
        required=True,
        metadata={"description": "The name of the RAG source."},
    )


class PageIdConfluenceSchema(Schema):
    page_id = fields.String(required=True)
