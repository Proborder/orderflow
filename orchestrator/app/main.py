from contextlib import asynccontextmanager

from fastapi import FastAPI

@asynccontextmanager
def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Orchestrator",
    lifespan=lifespan
)
