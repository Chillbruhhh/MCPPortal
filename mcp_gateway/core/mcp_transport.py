"""
MCP Protocol Transport over SSE.

This module implements the Model Context Protocol (MCP) transport layer
over Server-Sent Events (SSE) for use with Claude Code and other CLI agents.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from fastapi import Request
from sse_starlette.sse import EventSourceResponse

from ..core.gateway import MCPGateway
from ..models.mcp import MCPRequest, MCPResponse
from ..models.gateway import ToolExecutionRequest, ResourceRequest

logger = logging.getLogger(__name__)


class MCPSSETransport:
    """MCP Protocol transport over Server-Sent Events."""

    def __init__(self, gateway: MCPGateway):
        """
        Initialize MCP SSE transport.

        Args:
            gateway: MCP Gateway instance
        """
        self.gateway = gateway
        self._active_connections: Dict[str, asyncio.Queue] = {}
        self._request_handlers: Dict[str, asyncio.Queue] = {}
        self._initialized_connections: set = set()

    async def create_mcp_sse_stream(self, request: Request) -> EventSourceResponse:
        """
        Create MCP protocol SSE stream for Claude Code.

        Args:
            request: FastAPI request object

        Returns:
            EventSourceResponse with MCP protocol support
        """
        connection_id = str(uuid.uuid4())
        logger.info(f"New MCP SSE connection: {connection_id}")

        async def mcp_event_generator() -> AsyncGenerator[str, None]:
            """Generate MCP protocol events over SSE."""
            # Create message queues for this connection
            incoming_queue = asyncio.Queue(maxsize=100)
            outgoing_queue = asyncio.Queue(maxsize=100)
            
            self._active_connections[connection_id] = outgoing_queue
            self._request_handlers[connection_id] = incoming_queue

            try:
                # Send MCP initialization
                await self._send_mcp_initialization(outgoing_queue)

                # Start request processing task
                process_task = asyncio.create_task(
                    self._process_mcp_requests(connection_id, incoming_queue, outgoing_queue),
                    name=f"mcp-processor-{connection_id}"
                )

                # Main event loop
                while True:
                    try:
                        # Check if client disconnected
                        if await request.is_disconnected():
                            logger.info(f"MCP SSE client disconnected: {connection_id}")
                            break

                        # Wait for outgoing message
                        try:
                            message = await asyncio.wait_for(outgoing_queue.get(), timeout=30.0)
                            
                            # Format message based on type
                            if isinstance(message, dict) and message.get("type") == "endpoint":
                                # Send endpoint event with specific event type
                                yield f"event: endpoint\ndata: {json.dumps({'endpoint': message['endpoint']})}\n\n"
                            else:
                                # Send regular data event
                                yield f"data: {json.dumps(message)}\n\n"
                                
                        except asyncio.TimeoutError:
                            # Send keepalive
                            keepalive = {
                                "jsonrpc": "2.0",
                                "method": "notifications/ping",
                                "params": {"timestamp": datetime.utcnow().isoformat()}
                            }
                            yield f"data: {json.dumps(keepalive)}\n\n"

                    except asyncio.CancelledError:
                        logger.info(f"MCP SSE generator cancelled: {connection_id}")
                        break
                    except Exception as e:
                        logger.error(f"Error in MCP SSE generator {connection_id}: {e}")
                        break

            finally:
                # Cleanup
                process_task.cancel()
                try:
                    await process_task
                except asyncio.CancelledError:
                    pass
                
                self._active_connections.pop(connection_id, None)
                self._request_handlers.pop(connection_id, None)
                logger.info(f"MCP SSE connection cleaned up: {connection_id}")

        return EventSourceResponse(
            mcp_event_generator(),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST",
                "Access-Control-Allow-Headers": "Content-Type, Cache-Control"
            }
        )

    async def handle_mcp_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming MCP request via HTTP POST.

        Args:
            request_data: MCP request data

        Returns:
            MCP response data
        """
        try:
            # Parse MCP request
            mcp_request = MCPRequest(**request_data)
            logger.info(f"Handling MCP request: {mcp_request.method}")
            
            # Route request based on method
            response = None
            if mcp_request.method == "initialize":
                response = await self._handle_initialize(mcp_request)
                # After successful initialization, send initialized notification via SSE
                if response and not response.get("error"):
                    await self._send_to_all_connections({
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {}
                    })
            elif mcp_request.method == "tools/list":
                response = await self._handle_tools_list(mcp_request)
            elif mcp_request.method == "tools/call":
                response = await self._handle_tools_call(mcp_request)
            elif mcp_request.method == "resources/list":
                response = await self._handle_resources_list(mcp_request)
            elif mcp_request.method == "resources/read":
                response = await self._handle_resources_read(mcp_request)
            elif mcp_request.method == "completion/complete":
                response = await self._handle_completion_complete(mcp_request)
            elif mcp_request.method == "logging/setLevel":
                response = await self._handle_logging_set_level(mcp_request)
            else:
                response = MCPResponse(
                    id=mcp_request.id,
                    error={
                        "code": -32601,
                        "message": f"Method not found: {mcp_request.method}"
                    }
                ).model_dump()
            
            # Send response via SSE to all active connections
            if response:
                await self._send_to_all_connections(response)
            
            return {"status": "sent via SSE"}

        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            return MCPResponse(
                id=request_data.get("id", "unknown"),
                error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            ).model_dump()

    async def _send_mcp_initialization(self, outgoing_queue: asyncio.Queue):
        """Send required MCP endpoint event to signal where client should send requests."""
        # Based on official MCP specification, server MUST send 'endpoint' event
        # immediately when SSE connection is established to tell client where to send requests
        logger.info("Sending MCP endpoint event to client")
        
        # Send required endpoint event (per MCP specification)
        # Point to /sse since some clients expect to POST directly to the SSE endpoint
        endpoint_event = {
            "type": "endpoint",
            "endpoint": "/sse"  # Tell client to send requests to /sse (same endpoint)
        }
        
        await outgoing_queue.put(endpoint_event)
        logger.info("MCP endpoint event sent - client can now send initialize request to /sse")

    async def _send_to_all_connections(self, message: Dict[str, Any]):
        """Send message to all active SSE connections."""
        if not self._active_connections:
            logger.warning("No active SSE connections to send message to")
            return
            
        for connection_id, queue in self._active_connections.items():
            try:
                await queue.put(message)
                logger.debug(f"Sent message to connection {connection_id}")
            except Exception as e:
                logger.error(f"Failed to send message to connection {connection_id}: {e}")

    async def _process_mcp_requests(self, connection_id: str, incoming_queue: asyncio.Queue, outgoing_queue: asyncio.Queue):
        """Process MCP requests for a connection."""
        while True:
            try:
                # This would normally receive requests via WebSocket or similar
                # For SSE, we'll handle requests via separate HTTP endpoint
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing MCP requests for {connection_id}: {e}")
                break

    async def _handle_initialize(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP initialize request."""
        logger.info("Handling MCP initialize request")
        
        # Store that this connection is initialized
        self._initialized_connections.add(request.id if hasattr(self, '_initialized_connections') else None)
        
        return MCPResponse(
            id=request.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": True
                    },
                    "resources": {
                        "listChanged": True
                    },
                    "logging": {}
                },
                "serverInfo": {
                    "name": "mcp-gateway",
                    "version": "1.0.0"
                },
                "instructions": "MCP Gateway - Unified access to multiple MCP servers"
            }
        ).model_dump()

    async def _handle_tools_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP tools/list request."""
        logger.info("Handling MCP tools/list request")
        
        # Get all aggregated tools
        tools = self.gateway.aggregator.get_all_tools()
        
        # Convert to MCP format
        mcp_tools = []
        for tool in tools:
            mcp_tool = {
                "name": tool.prefixed_name,
                "description": tool.description,
                "inputSchema": tool.parameters or {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            mcp_tools.append(mcp_tool)
        
        return MCPResponse(
            id=request.id,
            result={
                "tools": mcp_tools
            }
        ).model_dump()

    async def _handle_tools_call(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP tools/call request."""
        logger.info(f"Handling MCP tools/call request: {request.params}")
        
        try:
            params = request.params or {}
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32602,
                        "message": "Missing required parameter: name"
                    }
                ).model_dump()
            
            # Execute tool via gateway
            tool_request = ToolExecutionRequest(
                tool_name=tool_name,
                parameters=arguments
            )
            
            result = await self.gateway.execute_tool(tool_request)
            
            if result.success:
                return MCPResponse(
                    id=request.id,
                    result={
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result.result, indent=2) if result.result else "Tool executed successfully"
                            }
                        ]
                    }
                ).model_dump()
            else:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32603,
                        "message": f"Tool execution failed: {result.error}"
                    }
                ).model_dump()
                
        except Exception as e:
            logger.error(f"Error in tools/call: {e}")
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            ).model_dump()

    async def _handle_resources_list(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP resources/list request."""
        logger.info("Handling MCP resources/list request")
        
        # Get all aggregated resources
        resources = self.gateway.aggregator.get_all_resources()
        
        # Convert to MCP format
        mcp_resources = []
        for resource in resources:
            mcp_resource = {
                "uri": resource.prefixed_uri,
                "name": resource.name,
                "description": resource.description,
                "mimeType": resource.mime_type
            }
            mcp_resources.append(mcp_resource)
        
        return MCPResponse(
            id=request.id,
            result={
                "resources": mcp_resources
            }
        ).model_dump()

    async def _handle_resources_read(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP resources/read request."""
        logger.info(f"Handling MCP resources/read request: {request.params}")
        
        try:
            params = request.params or {}
            resource_uri = params.get("uri")
            
            if not resource_uri:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32602,
                        "message": "Missing required parameter: uri"
                    }
                ).model_dump()
            
            # Access resource via gateway
            resource_request = ResourceRequest(
                resource_uri=resource_uri,
                parameters=params
            )
            
            result = await self.gateway.access_resource(resource_request)
            
            if result.success:
                return MCPResponse(
                    id=request.id,
                    result={
                        "contents": [
                            {
                                "uri": resource_uri,
                                "mimeType": result.mime_type or "text/plain",
                                "text": result.content or ""
                            }
                        ]
                    }
                ).model_dump()
            else:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32603,
                        "message": f"Resource access failed: {result.error}"
                    }
                ).model_dump()
                
        except Exception as e:
            logger.error(f"Error in resources/read: {e}")
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            ).model_dump()

    async def _handle_completion_complete(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP completion/complete request."""
        logger.info("Handling MCP completion/complete request")
        
        # For now, return empty completions
        return MCPResponse(
            id=request.id,
            result={
                "completion": {
                    "values": [],
                    "total": 0,
                    "hasMore": False
                }
            }
        ).model_dump()

    async def _handle_logging_set_level(self, request: MCPRequest) -> Dict[str, Any]:
        """Handle MCP logging/setLevel request."""
        logger.info(f"Handling MCP logging/setLevel request: {request.params}")
        
        params = request.params or {}
        level = params.get("level", "info")
        
        # Update logging level
        log_level = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger("mcp_gateway").setLevel(log_level)
        
        return MCPResponse(
            id=request.id,
            result={}
        ).model_dump()

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "active_connections": len(self._active_connections),
            "connection_ids": list(self._active_connections.keys())
        }


# Global transport instance
_global_transport: Optional[MCPSSETransport] = None

def create_mcp_transport(gateway: MCPGateway) -> MCPSSETransport:
    """Create or get existing MCP SSE transport instance."""
    global _global_transport
    if _global_transport is None:
        _global_transport = MCPSSETransport(gateway)
    return _global_transport

def get_mcp_transport() -> Optional[MCPSSETransport]:
    """Get the global MCP transport instance."""
    return _global_transport 