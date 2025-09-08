import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.fastapi_config import fastapi_settings
from src.services.cronjob.controllers.daily_greeting import router as daily_greeting_router
from src.services.cronjob.controllers.document_rag_controller import router as document_rag_router
from src.services.cronjob.controllers.sprint_tracker_controller import router as sprint_tracker_router

# Create FastAPI application
reload_flag = os.getenv("ENVIRONMENT") != "production"
app = FastAPI(
    title="Cronjob Services",
    description="API for managing cronjob services including document RAG, sprint tracker, and daily greetings",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all cronjob routers
app.include_router(document_rag_router)
app.include_router(sprint_tracker_router)
app.include_router(daily_greeting_router)

if __name__ == "__main__":
    app_port = fastapi_settings.app.app_port
    uvicorn.run("main:app", host="0.0.0.0", port=app_port, reload=reload_flag)
