"""
Pytest Configuration and Fixtures.

This module provides common fixtures and configuration for the test suite.
"""

import asyncio
import pytest
import pytest_asyncio
from typing import Dict, Any, List
from unittest.mock import AsyncMock, Mock, patch
import httpx

from mcp_gateway.config.settings import Settings, MCPServerConfig
from mcp_gateway.core.discovery import MCPDiscovery
from mcp_gateway.core.aggregator import MCPAggregator
from mcp_gateway.core.gateway import MCPGateway
from mcp_gateway.models.mcp import (
    MCPServer, MCPServerStatus, MCPTool, MCPResource,
    MCPRequest, MCPResponse
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        gateway_host="127.0.0.1",
        gateway_port=8000,
        log_level="DEBUG",
        mcp_servers='[{"name": "test-server", "url": "http://localhost:3000"}]',
        api_key_header="X-API-Key",
        allowed_origins='["http://localhost:3000"]',
        health_check_interval=10,
        connection_timeout=5,
        max_retries=2
    )


@pytest.fixture
def sample_mcp_server():
    """Create a sample MCP server for testing."""
    return MCPServer(
        name="test-server",
        url="http://localhost:3000",
        status=MCPServerStatus.CONNECTED,
        capabilities=["tools", "resources"],
        tools=[
            MCPTool(
                name="read_file",
                description="Read file contents",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"]
                }
            ),
            MCPTool(
                name="write_file",
                description="Write file contents",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            )
        ],
        resources=[
            MCPResource(
                uri="file:///test.txt",
                name="test.txt",
                description="Test file",
                mimeType="text/plain"
            )
        ]
    )


@pytest.fixture
def sample_server_config():
    """Create a sample server configuration."""
    return MCPServerConfig(
        name="test-server",
        url="http://localhost:3000",
        enabled=True,
        timeout=30,
        max_retries=3
    )


@pytest.fixture
def mock_http_client():
    """Create a mock HTTP client."""
    client_mock = AsyncMock(spec=httpx.AsyncClient)
    
    # Mock successful handshake response
    handshake_response = Mock()
    handshake_response.status_code = 200
    handshake_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "test-id",
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "serverInfo": {
                "name": "test-server",
                "version": "1.0.0"
            }
        }
    }
    
    # Mock tools list response
    tools_response = Mock()
    tools_response.status_code = 200
    tools_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "tools-id",
        "result": {
            "tools": [
                {
                    "name": "read_file",
                    "description": "Read file contents",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            ]
        }
    }
    
    # Mock resources list response
    resources_response = Mock()
    resources_response.status_code = 200
    resources_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": "resources-id",
        "result": {
            "resources": [
                {
                    "uri": "file:///test.txt",
                    "name": "test.txt",
                    "description": "Test file",
                    "mimeType": "text/plain"
                }
            ]
        }
    }
    
    # Set up response mapping based on request content
    def mock_post(*args, **kwargs):
        json_data = kwargs.get("json", {})
        method = json_data.get("method", "")
        
        if method == "initialize":
            return handshake_response
        elif method == "tools/list":
            return tools_response
        elif method == "resources/list":
            return resources_response
        else:
            # Default response
            default_response = Mock()
            default_response.status_code = 200
            default_response.json.return_value = {
                "jsonrpc": "2.0",
                "id": json_data.get("id"),
                "result": {}
            }
            return default_response
    
    client_mock.post.side_effect = mock_post
    client_mock.aclose = AsyncMock()
    
    return client_mock


@pytest.fixture
async def discovery(mock_settings):
    """Create discovery instance for testing."""
    discovery = MCPDiscovery(
        connection_timeout=mock_settings.connection_timeout,
        max_retries=mock_settings.max_retries
    )
    yield discovery
    await discovery.cleanup()


@pytest.fixture
def aggregator():
    """Create aggregator instance for testing."""
    return MCPAggregator(prefix_strategy="server_name")


@pytest.fixture
async def gateway(mock_settings):
    """Create gateway instance for testing."""
    gateway = MCPGateway(mock_settings)
    yield gateway
    await gateway.stop()


@pytest.fixture
def mock_mcp_request():
    """Create a mock MCP request."""
    return MCPRequest(
        id="test-request-id",
        method="tools/call",
        params={
            "name": "read_file",
            "arguments": {"path": "/test.txt"}
        }
    )


@pytest.fixture
def mock_mcp_response():
    """Create a mock MCP response."""
    return MCPResponse(
        id="test-request-id",
        result={
            "content": "Test file content",
            "success": True
        }
    )


@pytest.fixture
def mock_error_response():
    """Create a mock error response."""
    return MCPResponse(
        id="test-request-id",
        error={
            "code": -32601,
            "message": "Method not found"
        }
    )


@pytest.fixture
async def app_client(gateway):
    """Create FastAPI test client."""
    from fastapi.testclient import TestClient
    from mcp_gateway.main import app
    from mcp_gateway.api.dependencies import set_gateway
    
    # Set the gateway for the test app
    set_gateway(gateway)
    
    with TestClient(app) as client:
        yield client


class MockEventCallback:
    """Mock event callback for testing."""
    
    def __init__(self):
        self.events = []
    
    async def __call__(self, event):
        self.events.append(event)


@pytest.fixture
def mock_event_callback():
    """Create mock event callback."""
    return MockEventCallback()


# Pytest configuration
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Set up logging for tests."""
    import logging
    
    # Reduce log level for tests
    logging.getLogger("mcp_gateway").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)