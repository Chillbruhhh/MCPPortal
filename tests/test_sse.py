"""
Tests for Server-Sent Events.

This module tests the SSE functionality for real-time updates.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import asyncio
import json

from mcp_gateway.ui.sse import SSEManager
from mcp_gateway.models.gateway import ServerEvent, ServerEventType


class TestSSEManager:
    """Test cases for SSE Manager."""
    
    @pytest.fixture
    def sse_manager(self):
        """Create SSE manager for testing."""
        return SSEManager()
    
    @pytest.mark.asyncio
    async def test_add_client(self, sse_manager):
        """Test adding client to event manager."""
        mock_client = Mock()
        
        sse_manager.add_client("client1", mock_client)
        
        assert "client1" in sse_manager._clients
        assert sse_manager._clients["client1"] == mock_client
    
    @pytest.mark.asyncio
    async def test_remove_client(self, sse_manager):
        """Test removing client from event manager."""
        mock_client = Mock()
        sse_manager.add_client("client1", mock_client)
        
        sse_manager.remove_client("client1")
        
        assert "client1" not in sse_manager._clients
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_client(self, sse_manager):
        """Test removing non-existent client."""
        # Should not raise an error
        sse_manager.remove_client("non-existent")
    
    @pytest.mark.asyncio
    async def test_broadcast_event(self, sse_manager):
        """Test broadcasting event to all clients."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        
        sse_manager.add_client("client1", mock_client1)
        sse_manager.add_client("client2", mock_client2)
        
        event = ServerEvent(
            event_type=ServerEventType.CONNECTED,
            server_name="test-server",
            message="Server connected",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        await sse_manager.broadcast_event(event)
        
        # Both clients should receive the event
        mock_client1.send.assert_called_once()
        mock_client2.send.assert_called_once()
        
        # Check the sent data
        sent_data1 = mock_client1.send.call_args[0][0]
        sent_data2 = mock_client2.send.call_args[0][0]
        
        assert "data: " in sent_data1
        assert "test-server" in sent_data1
        assert "data: " in sent_data2
        assert "test-server" in sent_data2
    
    @pytest.mark.asyncio
    async def test_broadcast_event_client_error(self, sse_manager):
        """Test broadcasting when client has error."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        
        # Make one client fail
        mock_client1.send.side_effect = Exception("Client error")
        
        sse_manager.add_client("client1", mock_client1)
        sse_manager.add_client("client2", mock_client2)
        
        event = ServerEvent(
            event_type=ServerEventType.ERROR,
            server_name="test-server",
            message="Test error"
        )
        
        await sse_manager.broadcast_event(event)
        
        # Failing client should be removed
        assert "client1" not in sse_manager._clients
        assert "client2" in sse_manager._clients
        
        # Working client should still receive the event
        mock_client2.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_heartbeat(self, sse_manager):
        """Test sending heartbeat to all clients."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        
        sse_manager.add_client("client1", mock_client1)
        sse_manager.add_client("client2", mock_client2)
        
        await sse_manager.send_heartbeat()
        
        # Both clients should receive heartbeat
        mock_client1.send.assert_called_once()
        mock_client2.send.assert_called_once()
        
        # Check heartbeat format
        sent_data1 = mock_client1.send.call_args[0][0]
        assert "event: heartbeat" in sent_data1
        assert "data: " in sent_data1
    
    @pytest.mark.asyncio
    async def test_get_client_count(self, sse_manager):
        """Test getting client count."""
        assert sse_manager.get_client_count() == 0
        
        mock_client1 = Mock()
        mock_client2 = Mock()
        
        sse_manager.add_client("client1", mock_client1)
        assert sse_manager.get_client_count() == 1
        
        sse_manager.add_client("client2", mock_client2)
        assert sse_manager.get_client_count() == 2
        
        sse_manager.remove_client("client1")
        assert sse_manager.get_client_count() == 1


class TestServerEvent:
    """Test cases for Server Event."""
    
    def test_server_event_creation(self):
        """Test server event creation."""
        event = ServerEvent(
            event_type=ServerEventType.CONNECTED,
            server_name="test-server",
            message="Server connected"
        )
        
        assert event.event_type == ServerEventType.CONNECTED
        assert event.server_name == "test-server"
        assert event.message == "Server connected"
        assert event.timestamp is not None
    
    def test_server_event_serialization(self):
        """Test server event JSON serialization."""
        event = ServerEvent(
            event_type=ServerEventType.DISCONNECTED,
            server_name="test-server",
            message="Server disconnected",
            timestamp="2024-01-01T00:00:00Z"
        )
        
        json_data = event.model_dump()
        
        assert json_data["event_type"] == "disconnected"
        assert json_data["server_name"] == "test-server"
        assert json_data["message"] == "Server disconnected"
        assert json_data["timestamp"] == "2024-01-01T00:00:00Z"
    
    def test_server_event_with_data(self):
        """Test server event with additional data."""
        event = ServerEvent(
            event_type=ServerEventType.TOOL_EXECUTED,
            server_name="test-server",
            message="Tool executed",
            data={"tool_name": "read_file", "execution_time": 0.5}
        )
        
        assert event.data["tool_name"] == "read_file"
        assert event.data["execution_time"] == 0.5
    
    def test_server_event_to_sse_format(self):
        """Test converting server event to SSE format."""
        event = ServerEvent(
            event_type=ServerEventType.ERROR,
            server_name="test-server",
            message="Error occurred",
            data={"error_code": 500}
        )
        
        sse_format = event.to_sse_format()
        
        assert sse_format.startswith("event: server_event\n")
        assert "data: " in sse_format
        assert "test-server" in sse_format
        assert "Error occurred" in sse_format
        assert sse_format.endswith("\n\n")


class TestSSEIntegration:
    """Integration tests for SSE functionality."""
    
    @pytest.mark.asyncio
    async def test_sse_manager_integration_with_gateway(self, gateway, mock_event_callback):
        """Test event manager integration with gateway."""
        from mcp_gateway.ui.sse import SSEManager
        
        sse_manager = SSEManager()
        
        # Register event manager with gateway
        async def sse_callback(event):
            await sse_manager.broadcast_event(event)
        
        gateway.register_event_callback(sse_callback)
        
        # Add mock client to event manager
        mock_client = AsyncMock()
        sse_manager.add_client("test-client", mock_client)
        
        # Emit event from gateway
        await gateway._emit_server_event(
            ServerEventType.CONNECTED,
            "test-server",
            "Server connected successfully"
        )
        
        # Give a moment for event processing
        await asyncio.sleep(0.01)
        
        # Verify client received the event
        mock_client.send.assert_called_once()
        sent_data = mock_client.send.call_args[0][0]
        assert "Connected" in sent_data or "connected" in sent_data
    
    @pytest.mark.asyncio
    async def test_multiple_event_types(self, sse_manager):
        """Test handling multiple event types."""
        mock_client = AsyncMock()
        sse_manager.add_client("client1", mock_client)
        
        # Test different event types
        events = [
            ServerEvent(
                event_type=ServerEventType.CONNECTED,
                server_name="server1",
                message="Connected"
            ),
            ServerEvent(
                event_type=ServerEventType.DISCONNECTED,
                server_name="server2",
                message="Disconnected"
            ),
            ServerEvent(
                event_type=ServerEventType.ERROR,
                server_name="server3",
                message="Error occurred"
            ),
            ServerEvent(
                event_type=ServerEventType.TOOL_EXECUTED,
                server_name="server1",
                message="Tool executed",
                data={"tool_name": "test_tool"}
            )
        ]
        
        for event in events:
            await sse_manager.broadcast_event(event)
        
        # Verify all events were sent
        assert mock_client.send.call_count == 4
    
    @pytest.mark.asyncio
    async def test_client_lifecycle(self, sse_manager):
        """Test complete client lifecycle."""
        # Start with no clients
        assert sse_manager.get_client_count() == 0
        
        # Add clients
        client1 = AsyncMock()
        client2 = AsyncMock()
        sse_manager.add_client("client1", client1)
        sse_manager.add_client("client2", client2)
        
        assert sse_manager.get_client_count() == 2
        
        # Send event to all
        event = ServerEvent(
            event_type=ServerEventType.CONNECTED,
            server_name="test-server",
            message="Test message"
        )
        await sse_manager.broadcast_event(event)
        
        # Both should receive
        client1.send.assert_called_once()
        client2.send.assert_called_once()
        
        # Remove one client
        sse_manager.remove_client("client1")
        assert sse_manager.get_client_count() == 1
        
        # Reset mocks
        client1.reset_mock()
        client2.reset_mock()
        
        # Send another event
        await sse_manager.broadcast_event(event)
        
        # Only remaining client should receive
        client1.send.assert_not_called()
        client2.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_client_operations(self, sse_manager):
        """Test concurrent client operations."""
        clients = []
        
        # Add multiple clients concurrently
        async def add_client(i):
            mock_client = AsyncMock()
            sse_manager.add_client(f"client{i}", mock_client)
            clients.append(mock_client)
        
        # Add 10 clients concurrently
        await asyncio.gather(*[add_client(i) for i in range(10)])
        
        assert sse_manager.get_client_count() == 10
        
        # Broadcast event to all
        event = ServerEvent(
            event_type=ServerEventType.CONNECTED,
            server_name="test-server",
            message="Mass broadcast test"
        )
        await sse_manager.broadcast_event(event)
        
        # All clients should receive the event
        for client in clients:
            client.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_event_data_integrity(self, sse_manager):
        """Test that event data remains intact through transmission."""
        mock_client = AsyncMock()
        sse_manager.add_client("client1", mock_client)
        
        complex_data = {
            "tool_name": "complex_tool",
            "parameters": {"param1": "value1", "param2": 42},
            "result": ["item1", "item2", {"nested": "data"}],
            "execution_time": 1.23456,
            "success": True
        }
        
        event = ServerEvent(
            event_type=ServerEventType.TOOL_EXECUTED,
            server_name="test-server",
            message="Complex tool execution",
            data=complex_data
        )
        
        await sse_manager.broadcast_event(event)
        
        # Verify the sent data contains all the complex data
        mock_client.send.assert_called_once()
        sent_data = mock_client.send.call_args[0][0]
        
        # Parse the SSE data
        lines = sent_data.strip().split('\n')
        data_line = None
        for line in lines:
            if line.startswith('data: '):
                data_line = line[6:]  # Remove 'data: ' prefix
                break
        
        assert data_line is not None
        
        # Parse JSON and verify integrity
        parsed_data = json.loads(data_line)
        assert parsed_data["data"]["tool_name"] == "complex_tool"
        assert parsed_data["data"]["parameters"]["param2"] == 42
        assert parsed_data["data"]["execution_time"] == 1.23456
        assert parsed_data["data"]["success"] is True