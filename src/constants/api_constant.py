class StatusCode:
    OK = 200


class MediaType:
    JSON = "application/json"


class FieldDescription:
    """Description for the API."""

    COLLECTION_ID = "ID of the RAG source collection"
    ADD_GCP_FILE = "Add gcp file to a RAG source"
    GET_PAGES = "Get all pages tracking information"
    DELETE_PAGES = "Delete pages for a source"
    SOURCE_NAME = "The name of the source"
