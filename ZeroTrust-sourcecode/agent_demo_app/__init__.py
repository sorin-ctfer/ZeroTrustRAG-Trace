"""Agent zero-trust demo package."""

__all__ = ["create_app"]


def create_app():
    from .app import app
    return app
