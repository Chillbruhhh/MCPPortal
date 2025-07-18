"""
Tests for Tool/Resource Aggregation.

This module tests the tool and resource aggregation functionality
with conflict resolution and prefixing.
"""

import pytest

from mcp_gateway.core.aggregator import MCPAggregator
from mcp_gateway.models.mcp import (
    MCPServer, MCPServerStatus, MCPTool, MCPResource,
    AggregatedTool, AggregatedResource
)


class TestMCPAggregator:
    """Test cases for MCP Aggregator."""
    
    @pytest.fixture
    def servers_with_tools(self):
        """Create servers with tools for testing."""
        return [
            MCPServer(
                name="server1",
                url="http://localhost:3000",
                status=MCPServerStatus.CONNECTED,
                tools=[
                    MCPTool(
                        name="read_file",
                        description="Read file contents",
                        inputSchema={"type": "object", "properties": {"path": {"type": "string"}}}
                    ),
                    MCPTool(
                        name="unique_tool",
                        description="Unique tool",
                        inputSchema={}
                    )
                ]
            ),
            MCPServer(
                name="server2",
                url="http://localhost:3001",
                status=MCPServerStatus.CONNECTED,
                tools=[
                    MCPTool(
                        name="read_file",  # Conflict with server1
                        description="Read file contents (server2)",
                        inputSchema={"type": "object", "properties": {"file": {"type": "string"}}}
                    ),
                    MCPTool(
                        name="write_file",
                        description="Write file contents",
                        inputSchema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}
                    )
                ]
            )
        ]
    
    @pytest.fixture
    def servers_with_resources(self):
        """Create servers with resources for testing."""
        return [
            MCPServer(
                name="server1",
                url="http://localhost:3000",
                status=MCPServerStatus.CONNECTED,
                resources=[
                    MCPResource(
                        uri="file:///test.txt",
                        name="test.txt",
                        description="Test file",
                        mimeType="text/plain"
                    )
                ]
            ),
            MCPServer(
                name="server2",
                url="http://localhost:3001",
                status=MCPServerStatus.CONNECTED,
                resources=[
                    MCPResource(
                        uri="file:///test.txt",  # Conflict with server1
                        name="test.txt",
                        description="Test file (server2)",
                        mimeType="text/plain"
                    ),
                    MCPResource(
                        uri="file:///unique.txt",
                        name="unique.txt",
                        description="Unique file",
                        mimeType="text/plain"
                    )
                ]
            )
        ]
    
    @pytest.mark.asyncio
    async def test_aggregate_tools_with_prefixing(self, aggregator, servers_with_tools):
        """Test tool aggregation with prefixing."""
        tools = await aggregator.aggregate_tools(servers_with_tools)
        
        assert len(tools) == 4
        
        # Check prefixed names
        prefixed_names = [tool.prefixed_name for tool in tools]
        assert "server1.read_file" in prefixed_names
        assert "server2.read_file" in prefixed_names
        assert "server1.unique_tool" in prefixed_names
        assert "server2.write_file" in prefixed_names
    
    @pytest.mark.asyncio
    async def test_aggregate_tools_disconnected_server(self, aggregator):
        """Test tool aggregation skips disconnected servers."""
        servers = [
            MCPServer(
                name="connected-server",
                url="http://localhost:3000",
                status=MCPServerStatus.CONNECTED,
                tools=[
                    MCPTool(name="connected_tool", description="Connected tool", inputSchema={})
                ]
            ),
            MCPServer(
                name="disconnected-server",
                url="http://localhost:3001",
                status=MCPServerStatus.FAILED,
                tools=[
                    MCPTool(name="disconnected_tool", description="Disconnected tool", inputSchema={})
                ]
            )
        ]
        
        tools = await aggregator.aggregate_tools(servers)
        
        assert len(tools) == 1
        assert tools[0].server_name == "connected-server"
    
    @pytest.mark.asyncio
    async def test_aggregate_resources_with_prefixing(self, aggregator, servers_with_resources):
        """Test resource aggregation with prefixing."""
        resources = await aggregator.aggregate_resources(servers_with_resources)
        
        assert len(resources) == 3
        
        # Check prefixed URIs
        prefixed_uris = [resource.prefixed_uri for resource in resources]
        assert "server1://file:///test.txt" in prefixed_uris
        assert "server2://file:///test.txt" in prefixed_uris
        assert "server2://file:///unique.txt" in prefixed_uris
    
    @pytest.mark.asyncio
    async def test_find_tool_by_name(self, aggregator, servers_with_tools):
        """Test finding tool by name."""
        await aggregator.aggregate_tools(servers_with_tools)
        
        # Find by prefixed name
        tool = aggregator.find_tool_by_name("server1.read_file")
        assert tool is not None
        assert tool.server_name == "server1"
        assert tool.original_name == "read_file"
        
        # Find by original name (should return first match)
        tool = aggregator.find_tool_by_name("read_file")
        assert tool is not None
        
        # Find non-existent tool
        tool = aggregator.find_tool_by_name("non_existent_tool")
        assert tool is None
    
    @pytest.mark.asyncio
    async def test_find_resource_by_uri(self, aggregator, servers_with_resources):
        """Test finding resource by URI."""
        await aggregator.aggregate_resources(servers_with_resources)
        
        # Find by prefixed URI
        resource = aggregator.find_resource_by_uri("server1://file:///test.txt")
        assert resource is not None
        assert resource.server_name == "server1"
        assert resource.original_uri == "file:///test.txt"
        
        # Find by original URI (should return first match)
        resource = aggregator.find_resource_by_uri("file:///test.txt")
        assert resource is not None
        
        # Find non-existent resource
        resource = aggregator.find_resource_by_uri("file:///non_existent.txt")
        assert resource is None
    
    @pytest.mark.asyncio
    async def test_get_tools_by_server(self, aggregator, servers_with_tools):
        """Test getting tools by server."""
        await aggregator.aggregate_tools(servers_with_tools)
        
        server1_tools = aggregator.get_tools_by_server("server1")
        assert len(server1_tools) == 2
        assert all(tool.server_name == "server1" for tool in server1_tools)
        
        server2_tools = aggregator.get_tools_by_server("server2")
        assert len(server2_tools) == 2
        assert all(tool.server_name == "server2" for tool in server2_tools)
        
        unknown_tools = aggregator.get_tools_by_server("unknown-server")
        assert len(unknown_tools) == 0
    
    @pytest.mark.asyncio
    async def test_get_resources_by_server(self, aggregator, servers_with_resources):
        """Test getting resources by server."""
        await aggregator.aggregate_resources(servers_with_resources)
        
        server1_resources = aggregator.get_resources_by_server("server1")
        assert len(server1_resources) == 1
        assert all(resource.server_name == "server1" for resource in server1_resources)
        
        server2_resources = aggregator.get_resources_by_server("server2")
        assert len(server2_resources) == 2
        assert all(resource.server_name == "server2" for resource in server2_resources)
    
    @pytest.mark.asyncio
    async def test_conflict_detection(self, aggregator, servers_with_tools, servers_with_resources):
        """Test conflict detection."""
        await aggregator.aggregate_tools(servers_with_tools)
        await aggregator.aggregate_resources(servers_with_resources)
        
        tool_conflicts = aggregator.get_tool_conflicts()
        assert "read_file" in tool_conflicts
        assert len(tool_conflicts["read_file"]) == 2
        assert "server1" in tool_conflicts["read_file"]
        assert "server2" in tool_conflicts["read_file"]
        
        resource_conflicts = aggregator.get_resource_conflicts()
        assert "file:///test.txt" in resource_conflicts
        assert len(resource_conflicts["file:///test.txt"]) == 2
    
    @pytest.mark.asyncio
    async def test_aggregation_stats(self, aggregator, servers_with_tools, servers_with_resources):
        """Test aggregation statistics."""
        await aggregator.aggregate_tools(servers_with_tools)
        await aggregator.aggregate_resources(servers_with_resources)
        
        stats = aggregator.get_aggregation_stats()
        
        assert stats["total_tools"] == 4
        assert stats["total_resources"] == 3
        assert stats["tool_conflicts"] == 1
        assert stats["resource_conflicts"] == 1
        assert stats["servers_with_tools"] == 2
        assert stats["servers_with_resources"] == 2
        assert "server1" in stats["tools_by_server"]
        assert "server2" in stats["tools_by_server"]
    
    @pytest.mark.asyncio
    async def test_refresh_aggregation(self, aggregator, servers_with_tools):
        """Test refreshing aggregation."""
        # Initial aggregation
        await aggregator.aggregate_tools(servers_with_tools)
        initial_count = len(aggregator.get_all_tools())
        
        # Add a new server
        new_server = MCPServer(
            name="server3",
            url="http://localhost:3002",
            status=MCPServerStatus.CONNECTED,
            tools=[
                MCPTool(name="new_tool", description="New tool", inputSchema={})
            ]
        )
        servers_with_tools.append(new_server)
        
        # Refresh aggregation
        await aggregator.refresh_aggregation(servers_with_tools)
        
        # Check updated count
        new_count = len(aggregator.get_all_tools())
        assert new_count == initial_count + 1
        
        # Check new tool exists
        tool = aggregator.find_tool_by_name("server3.new_tool")
        assert tool is not None
    
    @pytest.mark.asyncio
    async def test_validate_tool_name(self, aggregator, servers_with_tools):
        """Test tool name validation."""
        await aggregator.aggregate_tools(servers_with_tools)
        
        assert aggregator.validate_tool_name("server1.read_file") is True
        assert aggregator.validate_tool_name("read_file") is True
        assert aggregator.validate_tool_name("non_existent_tool") is False
    
    @pytest.mark.asyncio
    async def test_validate_resource_uri(self, aggregator, servers_with_resources):
        """Test resource URI validation."""
        await aggregator.aggregate_resources(servers_with_resources)
        
        assert aggregator.validate_resource_uri("server1://file:///test.txt") is True
        assert aggregator.validate_resource_uri("file:///test.txt") is True
        assert aggregator.validate_resource_uri("file:///non_existent.txt") is False
    
    @pytest.mark.asyncio
    async def test_get_available_names(self, aggregator, servers_with_tools, servers_with_resources):
        """Test getting available tool names and resource URIs."""
        await aggregator.aggregate_tools(servers_with_tools)
        await aggregator.aggregate_resources(servers_with_resources)
        
        tool_names = aggregator.get_available_tool_names()
        assert len(tool_names) == 4
        assert "server1.read_file" in tool_names
        assert "server2.read_file" in tool_names
        
        resource_uris = aggregator.get_available_resource_uris()
        assert len(resource_uris) == 3
        assert "server1://file:///test.txt" in resource_uris
        assert "server2://file:///test.txt" in resource_uris
    
    def test_prefix_strategies(self):
        """Test different prefixing strategies."""
        # Test server_name strategy
        aggregator_server_name = MCPAggregator(prefix_strategy="server_name")
        assert aggregator_server_name._generate_prefix("test-server") == "test-server"
        
        # Test short_name strategy
        aggregator_short_name = MCPAggregator(prefix_strategy="short_name")
        assert aggregator_short_name._generate_prefix("test-server") == "test"
        assert aggregator_short_name._generate_prefix("singleword") == "singlewo"  # First 8 chars
        
        # Test none strategy
        aggregator_none = MCPAggregator(prefix_strategy="none")
        assert aggregator_none._generate_prefix("test-server") == ""
    
    @pytest.mark.asyncio
    async def test_no_prefix_strategy(self, servers_with_tools):
        """Test aggregation with no prefixing."""
        aggregator = MCPAggregator(prefix_strategy="none")
        
        # Remove one server to avoid conflicts
        single_server = [servers_with_tools[0]]
        
        tools = await aggregator.aggregate_tools(single_server)
        
        # Without prefixing, tool names should be original
        assert len(tools) == 2
        assert tools[0].prefixed_name == tools[0].original_name
        assert tools[1].prefixed_name == tools[1].original_name