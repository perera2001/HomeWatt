"""Internal service authentication for Node.js to Python calls."""

from fastapi import Header, HTTPException

from app.config import settings


def verify_internal_token(authorization: str | None = Header(default=None)) -> None:
    """Validate the shared internal bearer token when one is configured."""
    expected_token = settings.ai_service_internal_token

    # Local development only: allow direct calls when no internal token is configured.
    if not expected_token:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized internal service request",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if token != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized internal service request",
        )
