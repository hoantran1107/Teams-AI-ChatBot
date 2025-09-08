from marshmallow import fields, Schema


class DownloadFileSchema(Schema):
    file_name = fields.String(
        required=True, description="File name to download from GCP bucket"
    )


class UploadFileSchema(Schema):
    source_file_name = fields.String(
        required=True, description="Source file name to upload to GCP bucket"
    )
    destination_file_name = fields.String(
        required=True, description="Destination file name in GCP bucket"
    )


class DeleteFileSchema(Schema):
    file_name = fields.String(
        required=True, description="File name to delete from GCP bucket"
    )
