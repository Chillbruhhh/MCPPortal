"""
Tests for MCP Server Discovery.

This module tests the MCP server discovery and connection management functionality.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from mcp_gateway.core.discovery import MCPDiscovery
from mcp_gateway.config.settings import MCPServerConfig
from mcp_gateway.models.mcp import MCPServerStatus, MCPServer


class TestMCPDiscovery:
    """Test cases for MCP Discovery."""
    
    @pytest.mark.asyncio
    async def test_discover_servers_success(self, discovery, sample_server_config, mock_http_client):
        """Test successful server discovery."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            servers = await discovery.discover_servers([sample_server_config])
            
            assert len(servers) == 1
            assert servers[0].name == "test-server"
            assert servers[0].status == MCPServerStatus.CONNECTED
            assert "tools" in servers[0].capabilities
            assert "resources" in servers[0].capabilities
    
    @pytest.mark.asyncio
    async def test_discover_servers_connection_failure(self, discovery, sample_server_config):
        """Test server discovery with connection failure."""
        with patch('httpx.AsyncClient') as mock_client_class:
            # Mock connection failure
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            servers = await discovery.discover_servers([sample_server_config])
            
            assert len(servers) == 1
            assert servers[0].name == "test-server"
            assert servers[0].status == MCPServerStatus.FAILED
            assert "Connection failed" in servers[0].last_error
    
    @pytest.mark.asyncio
    async def test_discover_servers_disabled_server(self, discovery):
        """Test discovery with disabled server."""
        disabled_config = MCPServerConfig(
            name="disabled-server",
            url="http://localhost:3000",
            enabled=False
        )
        
        servers = await discovery.discover_servers([disabled_config])
        
        # Should return empty list since server is disabled
        assert len(servers) == 0
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, discovery, sample_server_config, mock_http_client):
        """Test successful health check."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            # First discover the server
            await discovery.discover_servers([sample_server_config])
            
            # Then test health check
            is_healthy = await discovery.health_check_server("test-server")
            
            assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_unknown_server(self, discovery):
        """Test health check for unknown server."""
        is_healthy = await discovery.health_check_server("unknown-server")
        
        assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, discovery, sample_server_config, mock_http_client):
        """Test health check failure."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            # First discover the server
            await discovery.discover_servers([sample_server_config])
            
            # Mock health check failure
            mock_http_client.post.side_effect = httpx.RequestError("Health check failed")
            
            is_healthy = await discovery.health_check_server("test-server")
            
            assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_all_servers(self, discovery, sample_server_config, mock_http_client):
        """Test health check for all servers."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            # Discover multiple servers
            server_configs = [
                sample_server_config,
                MCPServerConfig(
                    name="test-server-2",
                    url="http://localhost:3001",
                    enabled=True
                )
            ]
            
            await discovery.discover_servers(server_configs)
            
            health_results = await discovery.health_check_all_servers()
            
            assert len(health_results) == 2
            assert "test-server" in health_results
            assert "test-server-2" in health_results
    
    @pytest.mark.asyncio
    async def test_reconnect_server_success(self, discovery, sample_server_config, mock_http_client):
        """Test successful server reconnection."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            # First discover the server
            await discovery.discover_servers([sample_server_config])
            
            # Mark server as failed
            servers = await discovery.get_all_servers()
            servers[0].status = MCPServerStatus.FAILED
            
            # Test reconnection
            success = await discovery.reconnect_server("test-server")
            
            assert success is True
    
    @pytest.mark.asyncio
    async def test_reconnect_unknown_server(self, discovery):
        """Test reconnection of unknown server."""
        success = await discovery.reconnect_server("unknown-server")
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_get_connected_servers(self, discovery, sample_server_config, mock_http_client):
        """Test getting connected servers."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            await discovery.discover_servers([sample_server_config])
            
            connected_servers = await discovery.get_connected_servers()
            
            assert len(connected_servers) == 1
            assert connected_servers[0].status == MCPServerStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_get_server_client(self, discovery, sample_server_config, mock_http_client):
        """Test getting server client."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            await discovery.discover_servers([sample_server_config])
            
            client = await discovery.get_server_client("test-server")
            
            assert client is not None
    
    @pytest.mark.asyncio
    async def test_get_server_client_unknown(self, discovery):
        """Test getting client for unknown server."""
        client = await discovery.get_server_client("unknown-server")
        
        assert client is None
    
    @pytest.mark.asyncio
    async def test_handshake_error_response(self, discovery, sample_server_config):
        """Test handshake with error response."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            
            # Mock error response
            error_response = Mock()
            error_response.status_code = 200
            error_response.json.return_value = {
                "jsonrpc": "2.0",
                "id": "test-id",
                "error": {
                    "code": -32601,
                    "message": "Method not found"
                }
            }
            mock_client.post.return_value = error_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            servers = await discovery.discover_servers([sample_server_config])
            
            assert len(servers) == 1
            assert servers[0].status == MCPServerStatus.FAILED
            assert "Method not found" in servers[0].last_error
    
    @pytest.mark.asyncio
    async def test_handshake_http_error(self, discovery, sample_server_config):
        """Test handshake with HTTP error."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            
            # Mock HTTP error
            error_response = Mock()
            error_response.status_code = 500
            error_response.text = "Internal Server Error"
            mock_client.post.return_value = error_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            servers = await discovery.discover_servers([sample_server_config])
            
            assert len(servers) == 1
            assert servers[0].status == MCPServerStatus.FAILED
            assert "HTTP 500" in servers[0].last_error
    
    @pytest.mark.asyncio
    async def test_cleanup(self, discovery, sample_server_config, mock_http_client):
        """Test cleanup functionality."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            await discovery.discover_servers([sample_server_config])
            
            # Verify client exists
            client = await discovery.get_server_client("test-server")
            assert client is not None
            
            # Cleanup
            await discovery.cleanup()
            
            # Verify client is cleaned up
            client = await discovery.get_server_client("test-server")
            assert client is None
    
    @pytest.mark.asyncio
    async def test_concurrent_discovery(self, discovery, mock_http_client):
        """Test concurrent server discovery."""
        server_configs = [
            MCPServerConfig(name=f"server-{i}", url=f"http://localhost:300{i}", enabled=True)
            for i in range(5)
        ]
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            servers = await discovery.discover_servers(server_configs)
            
            assert len(servers) == 5
            for i, server in enumerate(servers):
                assert server.name == f"server-{i}"
                assert server.status == MCPServerStatus.CONNECTED