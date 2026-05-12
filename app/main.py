"""FastAPI app entry point.

Routers and middleware are wired in later tasks. This skeleton starts a
healthy service that returns a placeholder.
"""
from fastapi import FastAPI

app = FastAPI(title="TNA Service", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "version": "0.1.0"}
