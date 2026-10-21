"""Vercel ASGI entrypoint for the canonical Allpha FastAPI application."""

from allpha_api.main import app

__all__ = ["app"]
