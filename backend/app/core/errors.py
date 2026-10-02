from typing import Any

from fastapi import HTTPException, status


def openai_error_payload(
    message: str,
    error_type: str = "invalid_request_error",
    code: str | None = None,
    param: str | None = None,
) -> dict[str, Any]:
    """Format an error matching the standard OpenAI API error structure."""
    error_dict: dict[str, Any] = {
        "message": message,
        "type": error_type,
        "param": param,
        "code": code,
    }
    return {"error": error_dict}


class GatewayAPIException(HTTPException):
    """Custom HTTPException that produces OpenAI-shaped error responses."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_type: str = "invalid_request_error",
        code: str | None = None,
        param: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        detail = openai_error_payload(
            message=message, error_type=error_type, code=code, param=param
        )
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class GatewayAuthException(GatewayAPIException):
    def __init__(self, message: str = "Invalid API key provided.") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            error_type="invalid_request_error",
            code="invalid_api_key",
        )
