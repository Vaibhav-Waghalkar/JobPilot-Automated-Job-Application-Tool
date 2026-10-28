from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.vault.database import init_db
from backend.api.vault_api import router as vault_router
from backend.api.discovery_api import router as discovery_router
from backend.api.workflow_api import router as workflow_router
from backend.api.llm_api import router as llm_router
from backend.api.engine_api import router as engine_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema
    await init_db()
    yield

app = FastAPI(
    title="JobPilot Core API",
    description="Local-first job application agent backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local Vite dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vault_router)
app.include_router(discovery_router)
app.include_router(workflow_router)
app.include_router(llm_router)
app.include_router(engine_router)

# Mount local mock form app for local tests
from backend.mock_form_server import mock_app
app.mount("/mock", mock_app)

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status": "error"}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc), "status": "validation_error"}
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "status": "server_error"}
    )

@app.get("/")
async def root():
    return {"status": "ok", "app": "JobPilot", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok", "app": "JobPilot", "version": "1.0.0"}
