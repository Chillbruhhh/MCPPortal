"""
Official MCP Server using FastMCP SDK.

This module implements a proper MCP server using the official FastMCP SDK
that aggregates tools from multiple discovered MCP servers.
"""

import asyncio
import logging
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

from .config.settings import Settings
from .core.gateway import MCPGateway
from .models.mcp import MCPTool, AggregatedTool
from .models.gateway import ToolExecutionRequest

logger = logging.getLogger(__name__)


class MCPGatewayServer:
    """Official MCP Server implementation using FastMCP SDK."""
    
    def __init__(self):
        """Initialize the MCP Gateway Server."""
        self.settings = Settings()
        self.gateway = MCPGateway(self.settings)
        self.mcp = FastMCP("MCP Gateway Server")
        self._registered_tools = set()  # Track registered tools
        self._setup_tools()
    
    def _setup_tools(self):
        """Setup the MCP server with aggregated tools."""
        # Add a server info tool
        @self.mcp.tool(description="Get information about the MCP Gateway and available servers")
        def gateway_info() -> str:
            """Get information about the MCP Gateway."""
            servers = self.gateway.get_servers()
            enabled_servers = [s for s in servers if getattr(s, 'enabled', False)]
            return f"MCP Gateway Server - {len(enabled_servers)} enabled servers out of {len(servers)} total"
        
        # Add a list servers tool
        @self.mcp.tool(description="List all discovered MCP servers")
        def list_servers() -> str:
            """List all discovered MCP servers."""
            servers = self.gateway.get_servers()
            server_list = []
            for server in servers:
                status = "enabled" if getattr(server, 'enabled', False) else "disabled"
                server_list.append(f"- {server.name} ({server.source or 'configured'}) - {status}")
            return "\n".join(server_list)
        
        # Add a refresh tools command
        @self.mcp.tool(description="Refresh and reload all tools from enabled MCP servers")
        def refresh_tools() -> str:
            """Refresh tools from all enabled MCP servers."""
            try:
                # This will trigger a refresh of tools
                asyncio.create_task(self._refresh_dynamic_tools())
                return "Tools refresh initiated"
            except Exception as e:
                return f"Error refreshing tools: {str(e)}"
    
    async def start(self):
        """Start the MCP Gateway and discover servers."""
        logger.info("Starting MCP Gateway Server with FastMCP SDK")
        await self.gateway.start()
        
        # Initial load of dynamic tools
        await self._refresh_dynamic_tools()
        
        logger.info("MCP Gateway Server ready with FastMCP SDK")
    
    async def _refresh_dynamic_tools(self):
        """Refresh tools dynamically from aggregated MCP servers."""
        try:
            # Get all aggregated tools
            tools = self.gateway.aggregator.get_all_tools()
            logger.info(f"Refreshing MCP server with {len(tools)} aggregated tools")
            
            # Remove old tools that are no longer available
            current_tool_names = {tool.prefixed_name for tool in tools}
            tools_to_remove = self._registered_tools - current_tool_names
            
            for tool_name in tools_to_remove:
                try:
                    # Remove tool from FastMCP (if this functionality exists)
                    logger.debug(f"Would remove tool: {tool_name}")
                except Exception as e:
                    logger.warning(f"Could not remove tool {tool_name}: {e}")
            
            # Add new tools
            for tool in tools:
                if tool.prefixed_name not in self._registered_tools:
                    self._add_aggregated_tool(tool)
                    self._registered_tools.add(tool.prefixed_name)
                    
            logger.info(f"MCP server now has {len(self._registered_tools)} registered tools")
                
        except Exception as e:
            logger.error(f"Error refreshing dynamic tools: {e}")
    
    def _add_aggregated_tool(self, tool: AggregatedTool):
        """Add a single aggregated tool to the FastMCP server."""
        try:
            # Log the input schema for debugging
            logger.info(f"Registering tool '{tool.prefixed_name}' with schema: {tool.parameters}")
            
            # Create a dynamic tool function with closure to capture the tool
            def create_dynamic_tool(captured_tool):
                async def dynamic_tool(**kwargs: Any) -> str:
                    """Dynamic tool that forwards to the aggregated MCP server."""
                    try:
                        # Create proper ToolExecutionRequest
                        request = ToolExecutionRequest(
                            tool_name=captured_tool.prefixed_name,  # Use prefixed name
                            parameters=kwargs,
                            timeout=30
                        )
                        
                        # Execute the tool via the gateway
                        result = await self.gateway.execute_tool(request)
                        
                        if result.success:
                            if result.result:
                                # Handle different result types
                                if isinstance(result.result, dict):
                                    import json
                                    return json.dumps(result.result, indent=2)
                                else:
                                    return str(result.result)
                            else:
                                return "Tool executed successfully"
                        else:
                            return f"Error: {result.error}"
                            
                    except Exception as e:
                        logger.error(f"Error executing tool {captured_tool.prefixed_name}: {e}")
                        return f"Error executing tool: {str(e)}"
                
                return dynamic_tool
            
            # Create the tool function
            tool_func = create_dynamic_tool(tool)
            
            # Set the function name and description
            tool_func.__name__ = tool.prefixed_name.replace(".", "_").replace("-", "_")
            tool_func.__doc__ = tool.description or f"Tool from {tool.server_name}"
            
            # Try to add type annotations from the input schema
            if tool.parameters and isinstance(tool.parameters, dict):
                # Convert JSON schema to Python type annotations (basic implementation)
                annotations = {}
                properties = tool.parameters.get("properties", {})
                
                for param_name, param_schema in properties.items():
                    param_type = param_schema.get("type", "string")
                    if param_type == "string":
                        annotations[param_name] = str
                    elif param_type == "integer":
                        annotations[param_name] = int
                    elif param_type == "number":
                        annotations[param_name] = float
                    elif param_type == "boolean":
                        annotations[param_name] = bool
                    elif param_type == "array":
                        annotations[param_name] = list
                    elif param_type == "object":
                        annotations[param_name] = dict
                    else:
                        annotations[param_name] = str
                
                # Set annotations on the function
                tool_func.__annotations__ = annotations
            
            # Add the tool to FastMCP with proper description and annotations
            self.mcp.add_tool(
                tool_func,
                name=tool.prefixed_name,
                description=tool.description or f"Tool from {tool.server_name} server",
                annotations=tool.parameters  # Pass the input schema as annotations
            )
            
            logger.info(f"Successfully registered tool: {tool.prefixed_name} with schema: {tool.parameters}")
            
        except Exception as e:
            logger.error(f"Error adding tool {tool.prefixed_name}: {e}")
            logger.error(f"Tool parameters: {tool.parameters}")
    
    def run_sse(self, host: str = "0.0.0.0", port: int = 8020):
        """Run the MCP server with SSE transport on specified host and port."""
        logger.info(f"Starting MCP Gateway Server with SSE transport on {host}:{port}")
        
        # Use FastMCP's built-in SSE support with custom mount path
        self.mcp.run(transport="sse", mount_path=f"http://{host}:{port}/api/v1/mcp")

    async def run_sse_async(self, mount_path: str = None):
        """Run the MCP server with SSE transport asynchronously."""
        logger.info("Starting MCP Gateway Server with SSE transport (async)")
        await self.mcp.run_sse_async(mount_path=mount_path)


# Global MCP Gateway Server instance
_gateway_server = None


async def get_gateway_server() -> MCPGatewayServer:
    """Get or create the global MCP Gateway Server instance."""
    global _gateway_server
    if _gateway_server is None:
        _gateway_server = MCPGatewayServer()
        await _gateway_server.start()
    return _gateway_server


async def refresh_mcp_tools():
    """Refresh MCP server tools (called when servers are enabled/disabled)."""
    global _gateway_server
    if _gateway_server is not None:
        await _gateway_server._refresh_dynamic_tools()


async def run_mcp_server():
    """Main entry point for running the MCP server."""
    try:
        server = await get_gateway_server()
        await server.run_sse_async()
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        raise


if __name__ == "__main__":
    # Run the MCP server directly
    asyncio.run(run_mcp_server()) 