import logging
import os
from datetime import datetime
from io import BytesIO
from tempfile import gettempdir
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse

from src.services.auto_test.services.process import process_file_with_ai
from src.services.google_cloud_services.services.gcp_services import gcp_bucket_service

_logger = logging.getLogger(__name__)
# Create FastAPI router
router = APIRouter(prefix="/test", tags=["Auto Test RAG"])


@router.post(
    "",
    description="Upload a CSV or Excel file, process it in the background, and return status.",
)
async def process_csv_file(
    rag_source: Annotated[str, Form(description="Select RAG source")],
    file: Annotated[UploadFile, File(..., description="Upload CSV/Excel file")],
) -> dict:
    try:
        # Define supported file extensions
        SUPPORTED_EXTENSIONS = {".csv"}
        REQUIRED_COLUMNS = {"Question", "Correct Answer"}

        # Check file
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="Invalid or missing file upload")

        # Check if file extension is supported
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")

        # Read file content
        content = await file.read()

        # Read the file into a pandas DataFrame
        try:
            try:
                df = pd.read_csv(BytesIO(content), encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(BytesIO(content), encoding="latin1")
        except pd.errors.ParserError as e:
            raise HTTPException(status_code=400, detail=f"File parsing error: {e}")

        # Check for required columns in dataframe
        missing_columns = REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}",
            )

        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        processed_filename = f"{os.path.splitext(file.filename)[0]}_processed_{timestamp}.csv"
        processed_path = os.path.join(gettempdir(), processed_filename)

        df_process, stats = await process_file_with_ai(df, rag_source, processed_filename)
        # Save the processed DataFrame to a CSV file
        df_process.to_csv(processed_path, index=False)
        # Define the GCP storage path
        gcp_path = f"test_process/{processed_filename}"
        # Upload the processed file to GCP bucket
        await gcp_bucket_service.upload_file_to_gcp_bucket_async(processed_path, gcp_path)

        # Return response
        filename = f"{processed_filename}"
        return {
            "message": "File is processed",
            "file_name": filename,
            "total questions": stats.get("total_questions", 0),
            "average accuracy": stats.get("average_accuracy", 0.0),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.get("/download", description="Download the processed CSV file.")
async def download_csv_file(
    filename: Annotated[str, Query(description="Name of the processed file to download")],
)   -> FileResponse:
    try:
        # Check filename
        if not filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        gcp_path = f"test_process/{filename}"

        # Download the file from GCP to a local temporary directory
        local_file_path = gcp_bucket_service.download_file_from_gcp_bucket(
            file_name=gcp_path,
            destination_dir=gettempdir(),
        )

        # Check if file exists
        if not local_file_path or not os.path.exists(local_file_path):
            raise HTTPException(status_code=404, detail="File not found on GCP or still processing")

        # Return the file as a response
        response = FileResponse(path=local_file_path, media_type="text/csv", filename=filename)

        # Clean up file after response is sent (using response's background callback)
        def cleanup_file(res: Response):
            if os.path.exists(local_file_path):
                try:
                    os.remove(local_file_path)
                except OSError:
                    pass

        response.background = cleanup_file
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download error: {e}")
