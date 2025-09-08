import json
import mimetypes
import os.path
from pathlib import Path
from tempfile import gettempdir
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from src.constants.app_constants import MIME_TYPE
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service

# Create router
router = APIRouter(prefix="/gcp", tags=["GCP Bucket Services"])


@router.get("/download", description="Download file from GCP bucket based on dataset key")
async def download_file(
    file_name: Annotated[str, Query(description="File name to download from GCP bucket")],
) -> FileResponse:
    """Download file from GCP bucket based on dataset key."""
    try:
        # Use gcp_path from DATASETS configuration
        result = gcp_bucket_service.download_file_from_gcp_bucket(
            file_name=file_name,
            destination_dir=gettempdir(),
        )
        if not result:
            raise HTTPException(status_code=400, detail="Failed to download file")

        file_path = os.path.realpath(result)
        if not file_path or not Path(file_path).exists():
            raise HTTPException(status_code=404, detail="File not found on GCP or still processing")

        # Determine the media type based on file extension
        media_type, _ = mimetypes.guess_type(file_name)
        if media_type is None:
            # Fallback to a generic media type if type cannot be determined
            media_type = "application/octet-stream"

        # Return the file as a response
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=file_name,
            headers={"Content-Disposition": f"attachment; filename={file_name}"},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Value error: {e}") from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Runtime error: {e}") from e


@router.put("/upload", description="Upload file to GCP bucket")
async def upload_file(
    file: Annotated[UploadFile, File(description="File to upload to GCP bucket")],
    destination_file_name: Annotated[str, Form(description="Destination file name in GCP bucket")],
) -> Response:
    """Upload a file to GCP bucket."""
    response = {"data": None, "error": None, "status": "failed"}
    try:
        content = await file.read()
        if not file.filename:
            raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

        temp_file_path = Path(gettempdir()) / file.filename
        with temp_file_path.open("wb") as temp_file:
            temp_file.write(content)

        await gcp_bucket_service.upload_file_to_gcp_bucket_async(
            source_file_name=str(temp_file_path),
            destination_file_name=destination_file_name,
        )
        response["status"] = "success"
        response["data"] = "File uploaded successfully"
    except FileNotFoundError as e:
        response["error"] = f"File not found: {e}"
    except ValueError as e:
        response["error"] = f"Value error: {e}"
    except RuntimeError as e:
        response["error"] = f"Runtime error: {e}"

    status_code = 201 if response["status"] == "success" else 500
    return Response(content=json.dumps(response), media_type=MIME_TYPE, status_code=status_code)


@router.delete("/delete", description="Delete file from GCP bucket")
async def delete_file(
    file_name: Annotated[str, Query(description="File name to delete from GCP bucket")],
) -> Response:
    """Delete file from GCP bucket."""
    try:
        gcp_bucket_service.delete_file_from_gcp_bucket(file_name)
        return Response(status_code=204)
    except FileNotFoundError as e:
        return Response(content=json.dumps({"error": f"File not found: {e}"}), media_type=MIME_TYPE, status_code=404)
    except ValueError as e:
        return Response(content=json.dumps({"error": f"Value error: {e}"}), media_type=MIME_TYPE, status_code=400)
    except RuntimeError as e:
        return Response(content=json.dumps({"error": f"Runtime error: {e}"}), media_type=MIME_TYPE, status_code=500)
