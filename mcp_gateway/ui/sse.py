"""
Server-Sent Events Implementation.

This module implements Server-Sent Events (SSE) for real-time
updates to the management UI.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Set

from fastapi import Request
from sse_starlette.sse import EventSourceResponse
from ..core.gateway import MCPGateway
from ..models.gateway import ServerEvent

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages Server-Sent Events connections and broadcasting."""

    def __init__(self):
        """Initialize SSE manager."""
        self._connections: Set[asyncio.Queue] = set()
        self._gateway: MCPGateway = None

    def set_gateway(self, gateway: MCPGateway):
        """Set the gateway instance."""
        self._gateway = gateway
        # Register for server events
        gateway.register_event_callback(self._handle_server_event)

    async def add_connection(self, queue: asyncio.Queue):
        """Add a new SSE connection."""
        self._connections.add(queue)
        logger.info(f"New SSE connection added. Total connections: {len(self._connections)}")

    async def remove_connection(self, queue: asyncio.Queue):
        """Remove an SSE connection."""
        self._connections.discard(queue)
        logger.info(f"SSE connection removed. Total connections: {len(self._connections)}")

    async def _handle_server_event(self, event: ServerEvent):
        """Handle server events and broadcast to clients."""
        event_data = {
            "type": "server_event",
            "data": event.model_dump(),
            "timestamp": datetime.utcnow().isoformat()
        }

        await self._broadcast_event(event_data)

    async def _broadcast_event(self, event_data: Dict[str, Any]):
        """Broadcast event to all connected clients."""
        if not self._connections:
            return

        # Create list of connections to avoid modification during iteration
        connections = list(self._connections)

        for queue in connections:
            try:
                # Non-blocking put with timeout
                await asyncio.wait_for(queue.put(event_data), timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("SSE client queue full, removing connection")
                await self.remove_connection(queue)
            except Exception as e:
                logger.error(f"Error broadcasting to SSE client: {e}")
                await self.remove_connection(queue)

    async def broadcast_status_update(self):
        """Broadcast current gateway status."""
        if not self._gateway:
            return

        try:
            status = await self._gateway.get_status()
            servers = self._gateway.get_servers()

            event_data = {
                "type": "status_update",
                "data": {
                    "gateway": status.model_dump(),
                    "servers": [server.model_dump() for server in servers],
                    "aggregation": self._gateway.aggregator.get_aggregation_stats()
                },
                "timestamp": datetime.utcnow().isoformat()
            }

            await self._broadcast_event(event_data)

        except Exception as e:
            logger.error(f"Error broadcasting status update: {e}")

    async def broadcast_metrics_update(self):
        """Broadcast current metrics."""
        if not self._gateway:
            return

        try:
            metrics = self._gateway.get_metrics()

            event_data = {
                "type": "metrics_update",
                "data": metrics.model_dump(),
                "timestamp": datetime.utcnow().isoformat()
            }

            await self._broadcast_event(event_data)

        except Exception as e:
            logger.error(f"Error broadcasting metrics update: {e}")


# Global SSE manager instance
sse_manager = SSEManager()


def get_sse_manager() -> SSEManager:
    """Get the global SSE manager."""
    return sse_manager


async def create_event_stream(request: Request, gateway: MCPGateway) -> EventSourceResponse:
    """
    Create Server-Sent Events stream for real-time updates.

    Args:
        request: FastAPI request object
        gateway: Gateway instance

    Returns:
        EventSourceResponse for SSE streaming
    """

    def serialize_datetime(obj):
        """Convert datetime objects to ISO format strings for JSON serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        # Create queue for this connection
        queue = asyncio.Queue(maxsize=100)

        try:
            await sse_manager.add_connection(queue)

            # Send initial status
            try:
                status = await gateway.get_status()
                servers = gateway.get_servers()

                initial_data = {
                    "type": "initial_status",
                    "data": {
                        "gateway": status.model_dump(),
                        "servers": [server.model_dump() for server in servers],
                        "aggregation": gateway.aggregator.get_aggregation_stats()
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }

                yield f"data: {json.dumps(initial_data, default=serialize_datetime)}\n\n"

            except Exception as e:
                logger.error(f"Error sending initial status: {e}")

            # Process events from queue
            while True:
                try:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        logger.info("SSE client disconnected")
                        break

                    # Wait for event with timeout
                    try:
                        event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {json.dumps(event_data, default=serialize_datetime)}\n\n"
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat = {
                            "type": "heartbeat",
                            "data": {"message": "ping"},
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        yield f"data: {json.dumps(heartbeat, default=serialize_datetime)}\n\n"

                except asyncio.CancelledError:
                    logger.info("SSE event generator cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in SSE event generator: {e}")
                    break

        finally:
            await sse_manager.remove_connection(queue)

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


async def start_periodic_updates():
    """Start periodic status and metrics updates."""

    async def update_loop():
        """Periodic update loop."""
        while True:
            try:
                await asyncio.sleep(5)  # Update every 5 seconds
                await sse_manager.broadcast_status_update()

                await asyncio.sleep(10)  # Metrics every 15 seconds total
                await sse_manager.broadcast_metrics_update()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic update loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying on error

    # Start the update loop as a background task
    asyncio.create_task(update_loop(), name="sse-periodic-updates")


# Custom event broadcasting functions
async def broadcast_tool_execution(tool_name: str, server_name: str, success: bool, execution_time: float):
    """Broadcast tool execution event."""
    event_data = {
        "type": "tool_execution",
        "data": {
            "tool_name": tool_name,
            "server_name": server_name,
            "success": success,
            "execution_time": execution_time
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    await sse_manager._broadcast_event(event_data)


async def broadcast_resource_access(resource_uri: str, server_name: str, success: bool):
    """Broadcast resource access event."""
    event_data = {
        "type": "resource_access",
        "data": {
            "resource_uri": resource_uri,
            "server_name": server_name,
            "success": success
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    await sse_manager._broadcast_event(event_data)


async def broadcast_server_reconnection(server_name: str, success: bool):
    """Broadcast server reconnection event."""
    event_data = {
        "type": "server_reconnection",
        "data": {
            "server_name": server_name,
            "success": success,
            "message": "Reconnection successful" if success else "Reconnection failed"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    await sse_manager._broadcast_event(event_data)


async def broadcast_custom_event(event_type: str, data: Dict[str, Any]):
    """Broadcast custom event."""
    event_data = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat()
    }

    await sse_manager._broadcast_event(event_data)
