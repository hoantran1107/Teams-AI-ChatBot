from marshmallow import fields, Schema


class GetRagSchema(Schema):
	question = fields.String(required=True)
	is_use_history = fields.Boolean(required=False, missing=False)
	analyze_mode = fields.Boolean(required=False, missing=False)


class GetRagDynamicSchema(Schema):
	question = fields.String(required=True)
	rag_source = fields.String(required=True)
	analyze_mode = fields.Boolean(required=False, missing=False)


class GetMultiRagSourceSchema(Schema):
	question = fields.String(required=True)
	rag_sources = fields.List(
		fields.String(), required=True,
		description="List of RAG sources which can be used to answer the question"
	)
	session_id = fields.String(
		required=False,
		description='Optional session identifier to maintain context (conversation history) across multiple requests'
	)
	analyze_mode = fields.Boolean(required=False, missing=False)


class PostRagSchema(Schema):
	is_summary_version = fields.Boolean(required=False, missing=True)


class PostRagStoreSchema(Schema):
	is_summary_version = fields.Boolean(
		required=False, missing=False, load_default=False
	)
	doc_id_prefix = fields.String(required=True)


class PutRagStoreSchema(Schema):
	is_summary_version = fields.Boolean(
		required=False, missing=False, load_default=False
	)
	doc_name_prefix = fields.String(required=True)
	link_to_gcp_bucket = fields.String(required=True)


class DeleteRagStoreSchema(Schema):
	is_summary_version = fields.Boolean(
		required=False, missing=False, load_default=False
	)
	doc_name_prefix = fields.String(required=True)


class GetRagStoreSchema(Schema):
	is_summary_version = fields.Boolean(
		required=False, missing=False, load_default=False
	)
	doc_id_prefix = fields.String(required=False, load_default="")
	page_size = fields.Integer(required=False, missing=10)
	page = fields.Integer(required=False, missing=1)
