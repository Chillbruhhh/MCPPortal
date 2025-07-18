"""
Tests for Core Gateway Logic.

This module tests the core gateway functionality including
request routing, server management, and tool execution.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

from mcp_gateway.core.gateway import MCPGateway
from mcp_gateway.models.gateway import (
    ToolExecutionRequest, ResourceRequest, ServerEventType
)
from mcp_gateway.models.mcp import MCPServerStatus


class TestMCPGateway:
    """Test cases for MCP Gateway."""
    
    @pytest.mark.asyncio
    async def test_gateway_initialization(self, mock_settings):
        """Test gateway initialization."""
        gateway = MCPGateway(mock_settings)
        
        assert gateway.settings == mock_settings
        assert gateway.discovery is not None
        assert gateway.aggregator is not None
        assert not gateway._running
    
    @pytest.mark.asyncio
    async def test_gateway_start_stop(self, mock_settings):
        """Test gateway start and stop lifecycle."""
        gateway = MCPGateway(mock_settings)
        
        with patch.object(gateway, '_initialize_servers') as mock_init:
            await gateway.start()
            
            assert gateway._running is True
            assert mock_init.called
            assert gateway._health_check_task is not None
            
            await gateway.stop()
            
            assert gateway._running is False
    
    @pytest.mark.asyncio
    async def test_execute_tool_success(self, gateway, sample_mcp_server, mock_http_client):
        """Test successful tool execution."""
        # Mock server setup
        gateway._servers["test-server"] = sample_mcp_server
        
        with patch.object(gateway.discovery, 'get_server_client') as mock_get_client:
            # Mock successful tool execution response
            tool_response = Mock()
            tool_response.status_code = 200
            tool_response.json.return_value = {
                "jsonrpc": "2.0",
                "id": "test-id",
                "result": {
                    "content": "Test file content",
                    "success": True
                }
            }
            mock_http_client.post.return_value = tool_response
            mock_get_client.return_value = mock_http_client
            
            # Mock aggregator to find the tool
            with patch.object(gateway.aggregator, 'find_tool_by_name') as mock_find_tool:
                from mcp_gateway.models.mcp import AggregatedTool
                mock_find_tool.return_value = AggregatedTool(
                    original_name="read_file",
                    prefixed_name="test-server.read_file",
                    server_name="test-server",
                    description="Read file contents",
                    parameters={}
                )
                
                request = ToolExecutionRequest(
                    tool_name="test-server.read_file",
                    parameters={"path": "/test.txt"}
                )
                
                response = await gateway.execute_tool(request)
                
                assert response.success is True
                assert response.tool_name == "test-server.read_file"
                assert response.server_name == "test-server"
                assert response.result is not None
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, gateway):
        """Test tool execution with tool not found."""
        with patch.object(gateway.aggregator, 'find_tool_by_name') as mock_find_tool:
            mock_find_tool.return_value = None
            
            request = ToolExecutionRequest(
                tool_name="non-existent-tool",
                parameters={}
            )
            
            response = await gateway.execute_tool(request)
            
            assert response.success is False
            assert "not found" in response.error
    
    @pytest.mark.asyncio
    async def test_execute_tool_server_unavailable(self, gateway, sample_mcp_server):
        """Test tool execution with server unavailable."""
        # Set server as failed
        sample_mcp_server.status = MCPServerStatus.FAILED
        gateway._servers["test-server"] = sample_mcp_server
        
        with patch.object(gateway.aggregator, 'find_tool_by_name') as mock_find_tool:
            from mcp_gateway.models.mcp import AggregatedTool
            mock_find_tool.return_value = AggregatedTool(
                original_name="read_file",
                prefixed_name="test-server.read_file",
                server_name="test-server",
                description="Read file contents",
                parameters={}
            )
            
            request = ToolExecutionRequest(
                tool_name="test-server.read_file",
                parameters={"path": "/test.txt"}
            )
            
            response = await gateway.execute_tool(request)
            
            assert response.success is False
            assert "not available" in response.error
    
    @pytest.mark.asyncio
    async def test_access_resource_success(self, gateway, sample_mcp_server, mock_http_client):
        """Test successful resource access."""
        gateway._servers["test-server"] = sample_mcp_server
        
        with patch.object(gateway.discovery, 'get_server_client') as mock_get_client:
            # Mock successful resource access response
            resource_response = Mock()
            resource_response.status_code = 200
            resource_response.json.return_value = {
                "jsonrpc": "2.0",
                "id": "test-id",
                "result": {
                    "contents": [{
                        "text": "Test file content",
                        "mimeType": "text/plain"
                    }]
                }
            }
            mock_http_client.post.return_value = resource_response
            mock_get_client.return_value = mock_http_client
            
            # Mock aggregator to find the resource
            with patch.object(gateway.aggregator, 'find_resource_by_uri') as mock_find_resource:
                from mcp_gateway.models.mcp import AggregatedResource
                mock_find_resource.return_value = AggregatedResource(
                    original_uri="file:///test.txt",
                    prefixed_uri="test-server://file:///test.txt",
                    server_name="test-server",
                    name="test.txt",
                    description="Test file",
                    mime_type="text/plain"
                )
                
                request = ResourceRequest(
                    resource_uri="test-server://file:///test.txt"
                )
                
                response = await gateway.access_resource(request)
                
                assert response.success is True
                assert response.resource_uri == "test-server://file:///test.txt"
                assert response.server_name == "test-server"
                assert response.content == "Test file content"
    
    @pytest.mark.asyncio
    async def test_access_resource_not_found(self, gateway):
        """Test resource access with resource not found."""
        with patch.object(gateway.aggregator, 'find_resource_by_uri') as mock_find_resource:
            mock_find_resource.return_value = None
            
            request = ResourceRequest(
                resource_uri="non-existent-resource"
            )
            
            response = await gateway.access_resource(request)
            
            assert response.success is False
            assert "not found" in response.error
    
    @pytest.mark.asyncio
    async def test_get_status(self, gateway, sample_mcp_server):
        """Test getting gateway status."""
        # Add a server
        gateway._servers["test-server"] = sample_mcp_server
        
        status = await gateway.get_status()
        
        assert status.total_servers == 1
        assert status.active_servers == 1  # Connected server
        assert status.failed_servers == 0
        assert status.uptime is not None
    
    @pytest.mark.asyncio
    async def test_get_health_results(self, gateway, sample_mcp_server):
        """Test getting health check results."""
        gateway._servers["test-server"] = sample_mcp_server
        
        health_results = await gateway.get_health_results()
        
        assert len(health_results) == 1
        assert health_results[0].server_name == "test-server"
        assert health_results[0].healthy is True
    
    @pytest.mark.asyncio
    async def test_event_callback_registration(self, gateway, mock_event_callback):
        """Test event callback registration."""
        gateway.register_event_callback(mock_event_callback)
        
        # Emit a test event
        await gateway._emit_server_event(
            ServerEventType.CONNECTED,
            "test-server",
            "Test message"
        )
        
        assert len(mock_event_callback.events) == 1
        assert mock_event_callback.events[0].event_type == ServerEventType.CONNECTED
        assert mock_event_callback.events[0].server_name == "test-server"
    
    @pytest.mark.asyncio
    async def test_server_statistics_update(self, gateway):
        """Test server statistics update."""
        gateway._update_server_stats("test-server", 0.5, True)
        
        assert "test-server" in gateway._server_stats
        stats = gateway._server_stats["test-server"]
        assert stats.total_requests == 1
        assert stats.successful_requests == 1
        assert stats.failed_requests == 0
        assert stats.average_response_time == 0.5
    
    @pytest.mark.asyncio
    async def test_get_metrics(self, gateway):
        """Test getting gateway metrics."""
        # Add some stats
        gateway._update_server_stats("server1", 0.5, True)
        gateway._update_server_stats("server1", 1.0, False)
        gateway._update_server_stats("server2", 0.3, True)
        
        metrics = gateway.get_metrics()
        
        assert metrics.total_requests == 3
        assert metrics.successful_requests == 2
        assert metrics.failed_requests == 1
        assert len(metrics.server_statistics) == 2
    
    @pytest.mark.asyncio
    async def test_health_check_loop_handles_errors(self, gateway):
        """Test that health check loop handles errors gracefully."""
        gateway._running = True
        
        with patch.object(gateway, '_perform_health_checks') as mock_health_check:
            mock_health_check.side_effect = Exception("Health check error")
            
            # Start health check loop
            task = gateway._health_check_loop()
            
            # Let it run briefly
            import asyncio
            try:
                await asyncio.wait_for(task, timeout=0.1)
            except asyncio.TimeoutError:
                pass
            
            # Stop the loop
            gateway._running = False
            
            # The loop should continue despite the error
            assert mock_health_check.called
    
    @pytest.mark.asyncio
    async def test_attempt_reconnection(self, gateway, sample_mcp_server, mock_event_callback):
        """Test server reconnection attempt."""
        gateway._servers["test-server"] = sample_mcp_server
        gateway.register_event_callback(mock_event_callback)
        
        with patch.object(gateway.discovery, 'reconnect_server') as mock_reconnect:
            mock_reconnect.return_value = True
            
            with patch.object(gateway.discovery, 'get_all_servers') as mock_get_servers:
                mock_get_servers.return_value = [sample_mcp_server]
                
                with patch.object(gateway.aggregator, 'refresh_aggregation') as mock_refresh:
                    await gateway._attempt_reconnection("test-server")
                    
                    assert mock_reconnect.called
                    assert mock_refresh.called
                    assert sample_mcp_server.status == MCPServerStatus.CONNECTED
                    
                    # Check events were emitted
                    assert len(mock_event_callback.events) >= 2  # Reconnecting + Connected
    
    @pytest.mark.asyncio
    async def test_server_not_in_gateway(self, gateway):
        """Test operations with server not in gateway."""
        server = gateway.get_server_by_name("non-existent")
        assert server is None
        
        tools = gateway.get_aggregated_tools()
        assert len(tools) == 0
        
        resources = gateway.get_aggregated_resources()
        assert len(resources) == 0