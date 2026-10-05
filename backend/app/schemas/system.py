"""Responses for the foundation endpoints."""

from pydantic import BaseModel


class RootResponse(BaseModel):
    service: str
    version: str
    environment: str
    health: str
    docs: str
    reader: str


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    database: str
