from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.services import data_store
from backend.routers import portfolio, client, agents, stress, network


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_store.initialize()
    yield


app = FastAPI(
    title="CreditMind API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router, prefix="/api")
app.include_router(client.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(stress.router, prefix="/api")
app.include_router(network.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "CreditMind API"}
