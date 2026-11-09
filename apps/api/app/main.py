from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import settings
from app.db import check_database_schema
from app.llm.check_models import check_configured_models, should_skip_model_check
from app.logger import logger
from app.routers import (
    agent_runs_router,
    campus_hiring_router,
    chat_router,
    contacts_router,
    demo_auth_router,
    health_router,
    outreach_router,
    scores_router,
    student_records_router,
    students_router,
    voice_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify configured LLM models on server startup (skipped in CI/tests)
    if not should_skip_model_check():
        logger.info("Executing startup check: verifying configured LLM models...")
        check_configured_models(raise_on_error=True)
    # Verify database schema on startup
    check_database_schema(raise_on_error=True)
    yield


app = FastAPI(
    title="Recruiting Platform API",
    version="0.1.0",
    description="Day 1 walking skeleton for the recruiting platform.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(students_router)
app.include_router(voice_router)
app.include_router(outreach_router)
app.include_router(contacts_router)
app.include_router(agent_runs_router)
app.include_router(scores_router)
app.include_router(demo_auth_router)
app.include_router(student_records_router)
app.include_router(campus_hiring_router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Recruiting Platform API",
        version="0.1.0",
        description="Day 1 walking skeleton for the recruiting platform.",
        routes=app.routes,
    )
    # Define bearerAuth matching the OpenAPI design spec
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Supabase Access Token JWT",
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
