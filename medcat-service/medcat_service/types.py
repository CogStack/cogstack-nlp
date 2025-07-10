from typing import Literal, TypedDict


class HealthCheckResponse(TypedDict):
    """
    Using Eclipse MicroProfile health response schema
    """
    name: str
    status: Literal["UP", "DOWN"]
