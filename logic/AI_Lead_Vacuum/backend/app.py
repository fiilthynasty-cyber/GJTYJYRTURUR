import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import auth, leads, payments, pipeline, analytics, audit, outreach_routes
from backend.utils.db import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    create_tables()
    yield
    # Shutdown logic (if needed) goes here


app = FastAPI(
    title="AI Lead Vacuum API",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(leads.router, prefix="/leads", tags=["leads"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(outreach_routes.router, prefix="/outreach", tags=["outreach"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
