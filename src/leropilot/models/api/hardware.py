"""API models for hardware endpoints."""

from pydantic import BaseModel


class UpdateRobotBody(BaseModel):
    """Request body model for updating a robot via the hardware API.

    Fields are optional; only provided fields will be applied by the router/service layer.
    """

    name: str | None = None
    labels: dict[str, str] | None = None
    motor_bus_connections: dict[str, dict] | None = None
    custom_protection_settings: dict[str, list[dict]] | None = None
