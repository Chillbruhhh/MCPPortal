"""
API Response Models.

This module defines Pydantic models for API responses,
providing consistent response formats across all endpoints.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

from .gateway import GatewayMetrics, GatewayStatus, HealthCheckResult
from .mcp import AggregatedResource, AggregatedTool, MCPServer

T = TypeVar('T')


class APIResponse(GenericModel, Generic[T]):
    """Generic API response wrapper."""

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[T] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Health check timestamp"
    )
    gateway: GatewayStatus = Field(..., description="Gateway status")
    servers: List[HealthCheckResult] = Field(
        default_factory=list,
        description="Server health results"
    )


class ServersListResponse(BaseModel):
    """Response for listing servers."""

    servers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of configured servers"
    )
    total: int = Field(0, description="Total number of servers")
    active: int = Field(0, description="Number of active servers")
    failed: int = Field(0, description="Number of failed servers")


class ToolsListResponse(BaseModel):
    """Response for listing tools."""

    tools: List[AggregatedTool] = Field(
        default_factory=list,
        description="List of aggregated tools"
    )
    total: int = Field(0, description="Total number of tools")
    by_server: Dict[str, int] = Field(
        default_factory=dict,
        description="Tools count by server"
    )


class ResourcesListResponse(BaseModel):
    """Response for listing resources."""

    resources: List[AggregatedResource] = Field(
        default_factory=list,
        description="List of aggregated resources"
    )
    total: int = Field(0, description="Total number of resources")
    by_server: Dict[str, int] = Field(
        default_factory=dict,
        description="Resources count by server"
    )


class ServerDetailResponse(BaseModel):
    """Response for server details."""

    server: MCPServer = Field(..., description="Server information")
    tools: List[AggregatedTool] = Field(
        default_factory=list,
        description="Tools provided by this server"
    )
    resources: List[AggregatedResource] = Field(
        default_factory=list,
        description="Resources provided by this server"
    )


class ToolExecutionResponse(BaseModel):
    """Response for tool execution."""

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


class ResourceAccessResponse(BaseModel):
    """Response for resource access."""

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


class MetricsResponse(BaseModel):
    """Response for gateway metrics."""

    metrics: GatewayMetrics = Field(..., description="Gateway metrics")
    collection_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="Metrics collection time"
    )


class EventStreamResponse(BaseModel):
    """Response for SSE events."""

    event_type: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event timestamp"
    )


class ServerActionResponse(BaseModel):
    """Response for server actions (connect, disconnect, etc.)."""

    server_name: str = Field(..., description="Server name")
    action: str = Field(..., description="Action performed")
    success: bool = Field(..., description="Whether action was successful")
    message: str = Field(..., description="Action result message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Action timestamp"
    )


class ValidationResponse(BaseModel):
    """Response for validation operations."""

    valid: bool = Field(..., description="Whether validation passed")
    errors: List[str] = Field(
        default_factory=list,
        description="Validation errors"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Validation warnings"
    )


# Common response type aliases
SuccessResponse = APIResponse[Dict[str, Any]]
ListResponse = APIResponse[List[Dict[str, Any]]]
StringResponse = APIResponse[str]
BoolResponse = APIResponse[bool]
