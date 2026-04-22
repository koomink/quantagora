from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

ADMIN_TOKEN_HEADER = "X-Admin-Token"
admin_token_header = APIKeyHeader(name=ADMIN_TOKEN_HEADER, auto_error=False)


def require_admin(
    token: Annotated[str | None, Security(admin_token_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not token or not compare_digest(token, settings.admin_api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )
