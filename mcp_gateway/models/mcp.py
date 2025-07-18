"""
MCP Protocol Models.

This module defines Pydantic models for the Model Context Protocol (MCP)
following the JSON-RPC 2.0 specification.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class MCPMessageType(str, Enum):
    """MCP message types."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class MCPServerStatus(str, Enum):
    """MCP server connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"
    RECONNECTING = "reconnecting"


class MCPRequest(BaseModel):
    """MCP JSON-RPC 2.0 request."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Union[str, int] = Field(..., description="Request ID")
    method: str = Field(..., description="Method name")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")

    @field_validator("jsonrpc")
    @classmethod
    def validate_jsonrpc(cls, v):
        """Validate JSON-RPC version."""
        if v != "2.0":
            raise ValueError("JSON-RPC version must be 2.0")
        return v


class MCPResponse(BaseModel):
    """MCP JSON-RPC 2.0 response."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    id: Union[str, int] = Field(..., description="Request ID")
    result: Optional[Dict[str, Any]] = Field(None, description="Result data")
    error: Optional[Dict[str, Any]] = Field(None, description="Error information")

    @field_validator("jsonrpc")
    @classmethod
    def validate_jsonrpc(cls, v):
        """Validate JSON-RPC version."""
        if v != "2.0":
            raise ValueError("JSON-RPC version must be 2.0")
        return v

    @field_validator("error")
    @classmethod
    def validate_error_or_result(cls, v, info):
        """Validate that response has either result or error, not both."""
        if v is not None and info.data.get("result") is not None:
            raise ValueError("Response cannot have both result and error")
        return v


class MCPNotification(BaseModel):
    """MCP JSON-RPC 2.0 notification."""

    jsonrpc: str = Field(default="2.0", description="JSON-RPC version")
    method: str = Field(..., description="Method name")
    params: Optional[Dict[str, Any]] = Field(None, description="Method parameters")

    @field_validator("jsonrpc")
    @classmethod
    def validate_jsonrpc(cls, v):
        """Validate JSON-RPC version."""
        if v != "2.0":
            raise ValueError("JSON-RPC version must be 2.0")
        return v


class MCPTool(BaseModel):
    """MCP tool definition."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema for tool input"
    )


class MCPResource(BaseModel):
    """MCP resource definition."""

    uri: str = Field(..., description="Resource URI")
    name: str = Field(..., description="Resource name")
    description: Optional[str] = Field(None, description="Resource description")
    mimeType: Optional[str] = Field(None, description="MIME type")


class MCPServer(BaseModel):
    """MCP server configuration and status."""

    name: str = Field(..., description="Server identifier")
    url: str = Field(..., description="Server connection URL")
    status: MCPServerStatus = Field(
        default=MCPServerStatus.DISCONNECTED,
        description="Connection status"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="Server capabilities"
    )
    tools: List[MCPTool] = Field(
        default_factory=list,
        description="Available tools"
    )
    resources: List[MCPResource] = Field(
        default_factory=list,
        description="Available resources"
    )
    last_ping: Optional[datetime] = Field(None, description="Last successful ping")
    last_error: Optional[str] = Field(None, description="Last error message")
    retry_count: int = Field(default=0, description="Current retry count")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    source: Optional[str] = Field(None, description="Source IDE or configuration")
    enabled: bool = Field(default=False, description="Whether the server is enabled by user")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        """Validate server URL format."""
        if not v.startswith(("http://", "https://", "ws://", "wss://", "process://")):
            raise ValueError("Server URL must start with http://, https://, ws://, wss://, or process://")
        return v


class AggregatedTool(BaseModel):
    """Aggregated tool with prefixing."""

    original_name: str = Field(..., description="Original tool name")
    prefixed_name: str = Field(..., description="Prefixed tool name")
    server_name: str = Field(..., description="Source server name")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool parameters schema"
    )

    @field_validator("prefixed_name")
    @classmethod
    def validate_prefixed_name(cls, v, info):
        """Validate that prefixed name follows server-name.tool-name pattern."""
        server_name = info.data.get("server_name")
        original_name = info.data.get("original_name")

        if server_name and original_name:
            expected_prefix = f"{server_name}.{original_name}"
            if v != expected_prefix:
                raise ValueError(f"Prefixed name must be '{expected_prefix}', got '{v}'")

        return v


class AggregatedResource(BaseModel):
    """Aggregated resource with prefixing."""

    original_uri: str = Field(..., description="Original resource URI")
    prefixed_uri: str = Field(..., description="Prefixed resource URI")
    server_name: str = Field(..., description="Source server name")
    name: str = Field(..., description="Resource name")
    description: Optional[str] = Field(None, description="Resource description")
    mime_type: Optional[str] = Field(None, description="MIME type")


class MCPCapabilities(BaseModel):
    """MCP server capabilities."""

    experimental: Dict[str, Any] = Field(default_factory=dict)
    logging: Dict[str, Any] = Field(default_factory=dict)
    prompts: Dict[str, Any] = Field(default_factory=dict)
    resources: Dict[str, Any] = Field(default_factory=dict)
    tools: Dict[str, Any] = Field(default_factory=dict)
