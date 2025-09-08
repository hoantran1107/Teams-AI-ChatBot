# Import our FastAPI routers
from src.services.auto_test.controllers.auto_test_controller import (
    router as test_router,
)
from src.services.cronjob.controllers.daily_greeting import (
    router as daily_greeting_router,
)
from src.services.cronjob.controllers.document_rag_controller import (
    router as cronjob_router,
)
from src.services.cronjob.controllers.sprint_tracker_controller import (
    router as sprint_tracker_router,
)
from src.services.google_cloud_services.controllers.gcp_controller import (
    router as gcp_router,
)
from src.services.manage_rag_sources.controllers.manage_pages import (
    router as rag_pages_router,
)
from src.services.manage_rag_sources.controllers.manage_sources import (
    router as rag_sources_router,
)
from src.services.n8n_services.controller.n8n_controller import (
    router as n8n_router,
)
from src.services.rag_services.controller.dynamic_rag_controller import (
    router as dynamic_rag_router,
)
from src.services.rag_services.controller.kb_rag_controller import (
    router as kb_rag_router,
)
from src.services.rag_services.controller.multiple_source_rag import (
    router as multi_rag_router,
)
from src.services.rag_services.controller.remove_rag_source import (
    router as remove_rag_router,
)
from src.services.rag_services.controller.url_redirect_controller import (
    router as url_redirect_router,
)

# List of all API routers to be registered with the FastAPI app
api_routers = [
    cronjob_router,
    kb_rag_router,
    multi_rag_router,
    dynamic_rag_router,
    gcp_router,
    rag_sources_router,
    rag_pages_router,
    test_router,
    sprint_tracker_router,
    daily_greeting_router,
    url_redirect_router,
    remove_rag_router,
    n8n_router,
]


def init_routers(app) -> None:
    """Initialize all API routers with the FastAPI app."""
    for router in api_routers:
        app.include_router(router)
