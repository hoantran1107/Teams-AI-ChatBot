import uvicorn
from src.cloud_runs.document_handler.docs_handler import convert_gcp_file_to_markdown_async
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.post("/")
async def handle_docs(request: Request):
    request_json = await request.json()
    gcp_url = await convert_gcp_file_to_markdown_async(request_json)

    return JSONResponse(content={"url": gcp_url})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
