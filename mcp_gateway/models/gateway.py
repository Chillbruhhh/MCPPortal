"""
Gateway-specific Models.

This module defines Pydantic models specific to the MCP Gateway
functionality, including status tracking and event handling.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GatewayStatus(BaseModel):
    """Overall gateway status and metrics."""

    total_servers: int = Field(0, description="Total configured servers")
    active_servers: int = Field(0, description="Currently active servers")
    failed_servers: int = Field(0, description="Currently failed servers")
    total_tools: int = Field(0, description="Total aggregated tools")
    total_resources: int = Field(0, description="Total aggregated resources")
    uptime: str = Field("0s", description="Gateway uptime")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last status update"
    )
    version: str = Field("1.0.0", description="Gateway version")


class ServerEventType(str, Enum):
    """Types of server events."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    RECONNECTING = "reconnecting"
    TOOLS_UPDATED = "tools_updated"
    RESOURCES_UPDATED = "resources_updated"
    HEALTH_CHECK = "health_check"
    ERROR = "error"


class ServerEvent(BaseModel):
    """Server event for real-time updates."""

    event_type: ServerEventType = Field(..., description="Event type")
    server_name: str = Field(..., description="Server name")
    message: str = Field(..., description="Event message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp"
    )
    data: Optional[Dict[str, Any]] = Field(None, description="Additional event data")


class GatewayConfig(BaseModel):
    """Gateway configuration."""

    host: str = Field("0.0.0.0", description="Gateway host")
    port: int = Field(8000, description="Gateway port")
    log_level: str = Field("INFO", description="Logging level")
    health_check_interval: int = Field(30, description="Health check interval in seconds")
    connection_timeout: int = Field(30, description="Connection timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")
    api_key: Optional[str] = Field(None, description="API key for authentication")


class ToolExecutionRequest(BaseModel):
    """Request to execute a tool."""

    tool_name: str = Field(..., description="Tool name (prefixed or original)")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool parameters"
    )
    timeout: Optional[int] = Field(30, description="Execution timeout in seconds")


class ToolExecutionResponse(BaseModel):
    """Response from tool execution."""

    tool_name: str = Field(..., description="Tool name")
    server_name: str = Field(..., description="Server that executed the tool")
    success: bool = Field(..., description="Whether execution was successful")
    result: Optional[Dict[str, Any]] = Field(None, description="Execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time: float = Field(..., description="Execution time in seconds")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Execution timestamp"
    )


class ResourceRequest(BaseModel):
    """Request to access a resource."""

    resource_uri: str = Field(..., description="Resource URI (prefixed or original)")
    parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Resource parameters"
    )


class ResourceResponse(BaseModel):
    """Response from resource access."""

    resource_uri: str = Field(..., description="Resource URI")
    server_name: str = Field(..., description="Server that provided the resource")
    success: bool = Field(..., description="Whether access was successful")
    content: Optional[str] = Field(None, description="Resource content")
    mime_type: Optional[str] = Field(None, description="Content MIME type")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Access timestamp"
    )


class HealthCheckResult(BaseModel):
    """Result of server health check."""

    server_name: str = Field(..., description="Server name")
    healthy: bool = Field(..., description="Whether server is healthy")
    response_time: float = Field(..., description="Response time in seconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )


class ServerStatistics(BaseModel):
    """Server usage statistics."""

    server_name: str = Field(..., description="Server name")
    total_requests: int = Field(0, description="Total requests made")
    successful_requests: int = Field(0, description="Successful requests")
    failed_requests: int = Field(0, description="Failed requests")
    average_response_time: float = Field(0.0, description="Average response time")
    last_request: Optional[datetime] = Field(None, description="Last request timestamp")
    uptime: str = Field("0s", description="Server uptime")


class GatewayMetrics(BaseModel):
    """Gateway performance metrics."""

    total_requests: int = Field(0, description="Total requests processed")
    successful_requests: int = Field(0, description="Successful requests")
    failed_requests: int = Field(0, description="Failed requests")
    average_response_time: float = Field(0.0, description="Average response time")
    active_connections: int = Field(0, description="Active SSE connections")
    server_statistics: List[ServerStatistics] = Field(
        default_factory=list,
        description="Per-server statistics"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
