import logging
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Updated imports to use proper location after restructuring
from src.config.database_config import SessionLocal, init_db
from src.config.fastapi_config import fastapi_settings
from src.config.log_setup import setup_logging
from src.config.urls import init_routers

# Local imports
from src.routes.teams_route import add_teams_route_fastapi
from src.routes.test_route import add_test_route_fastapi
from src.services.cronjob.models.source_handler.gcp_handler import GCS_EXECUTOR

# Check if the environment is set to production turn log level to WARNING
env = os.environ.get("ENVIRONMENT", "development").lower()
log_level = logging.INFO if env in ["production", "prod"] else logging.DEBUG

# Set up logging
setup_logging(level=log_level)
logger = logging.getLogger(__name__)


# Lifespan context manager for FastAPI startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:  # noqa: ARG001
    """Lifespan context manager for FastAPI application."""
    # Startup
    logger.info("FastAPI application startup")

    # Initialize database tables
    try:
        logger.info("Initializing database tables...")
        init_db()
        logger.info("Database tables initialized successfully")
    except Exception:
        logger.exception("Error initializing database")

    yield  # This is where the application runs
    # Shutdown
    GCS_EXECUTOR.shutdown()
    logger.info("FastAPI application shutdown")


# Create FastAPI application
app = FastAPI(
    title=fastapi_settings.api_title,
    description=fastapi_settings.api_description,
    version=fastapi_settings.api_version,
    lifespan=lifespan,
    debug=fastapi_settings.app.debug,
)


# Add root route to redirect to documentation
@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect root URL to API documentation."""
    return RedirectResponse(url="/docs")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You may want to restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app = add_teams_route_fastapi(app)
if env not in ["production", "prod"]:
    app = add_test_route_fastapi(app)

# Initialize all other API routes
init_routers(app)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Middleware to handle database sessions for FastAPI."""
    # Create a new session for this request
    db = SessionLocal()

    try:
        # Set the session for the current request context
        request.state.db = db

        # Process the request
        response = await call_next(request)
        return response
    except Exception:
        logger.exception("Exception in db_session_middleware")
        # Rollback on exception
        db.rollback()
        raise
    finally:
        # Close the session when done
        db.close()


if __name__ == "__main__":
    # FastAPI and Uvicorn handle async natively, no need for manual event loop management
    app_port = fastapi_settings.app.app_port
    logger.info("Starting FastAPI application on port %s", app_port)
    uvicorn.run("main:app", host="0.0.0.0", port=app_port, reload=False)
