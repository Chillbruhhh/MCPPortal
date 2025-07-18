"""
Server Management API.

This module provides the FastAPI application factory and
server management endpoints for the MCP Gateway.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import json

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .dependencies import get_gateway, set_gateway
from .middleware import setup_middleware
from .routes import router as api_router
from ..config.settings import Settings
from ..core.gateway import MCPGateway
from ..ui.sse import create_event_stream, sse_manager, start_periodic_updates
from ..mcp_server import get_gateway_server

logger = logging.getLogger(__name__)


async def handle_mcp_message(message: dict, gateway_instance=None):
    """Handle MCP message and return response"""
    # For now, handle basic initialize and other common requests
    method = message.get("method", "")
    
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": {
                    "name": "MCP Gateway",
                    "version": "1.0.0"
                }
            }
        }
    elif method == "notifications/initialized":
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {}
        }
    elif method == "tools/list":
        # Get the actual aggregated tools from the gateway
        try:
            if gateway_instance and hasattr(gateway_instance, 'get_aggregated_tools'):
                tools = gateway_instance.get_aggregated_tools()
                # Convert to standard MCP tool format
                tools_data = []
                for tool in tools:
                    # Use the actual input schema stored in the aggregated tool (from original MCP server)
                    input_schema = tool.parameters if tool.parameters else {
                        "type": "object",
                        "properties": {}
                    }
                    
                    mcp_tool = {
                        "name": tool.prefixed_name,  # Use prefixed name as the tool name
                        "description": tool.description,
                        "inputSchema": input_schema  # Use original schema from MCP server
                    }
                    tools_data.append(mcp_tool)
                    logger.debug(f"Tool {tool.prefixed_name} from {tool.server_name} has schema: {input_schema}")
                    
                    # Log if schema is empty
                    if not input_schema or input_schema == {"type": "object", "properties": {}}:
                        logger.warning(f"Tool {tool.prefixed_name} from {tool.server_name} has empty schema! Original parameters: {tool.parameters}")
                    
                logger.info(f"Returning {len(tools_data)} aggregated tools in MCP format")
            else:
                tools_data = []
                logger.warning("No gateway instance or get_aggregated_tools method available")
                
            return {
                "jsonrpc": "2.0", 
                "id": message.get("id"),
                "result": {
                    "tools": tools_data
                }
            }
        except Exception as e:
            logger.error(f"Error getting aggregated tools: {e}")
            return {
                "jsonrpc": "2.0", 
                "id": message.get("id"),
                "result": {
                    "tools": []
                }
            }
    elif method == "tools/call":
        # Handle tool execution
        try:
            params = message.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32602,
                        "message": "Missing required parameter: name"
                    }
                }
            
            if not gateway_instance:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": "Gateway instance not available"
                    }
                }
            
            # Execute tool via gateway
            from ..models.gateway import ToolExecutionRequest
            tool_request = ToolExecutionRequest(
                tool_name=tool_name,
                parameters=arguments
            )
            
            result = await gateway_instance.execute_tool(tool_request)
            
            if result.success:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result.result, indent=2) if result.result else "Tool executed successfully"
                            }
                        ]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Tool execution failed: {result.error}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in tools/call: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    elif method == "resources/list":
        # Get the actual aggregated resources from the gateway
        try:
            if gateway_instance and hasattr(gateway_instance, 'get_aggregated_resources'):
                resources = gateway_instance.get_aggregated_resources()
                resources_data = [resource.model_dump() for resource in resources]
                logger.info(f"Returning {len(resources_data)} aggregated resources")
            else:
                resources_data = []
                logger.warning("No gateway instance or get_aggregated_resources method available")
                
            return {
                "jsonrpc": "2.0", 
                "id": message.get("id"),
                "result": {
                    "resources": resources_data
                }
            }
        except Exception as e:
            logger.error(f"Error getting aggregated resources: {e}")
            return {
                "jsonrpc": "2.0", 
                "id": message.get("id"),
                "result": {
                    "resources": []
                }
            }
    elif method == "resources/read":
        # Handle resource access
        try:
            params = message.get("params", {})
            resource_uri = params.get("uri")
            
            if not resource_uri:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32602,
                        "message": "Missing required parameter: uri"
                    }
                }
            
            if not gateway_instance:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": "Gateway instance not available"
                    }
                }
            
            # Access resource via gateway
            from ..models.gateway import ResourceRequest
            resource_request = ResourceRequest(
                resource_uri=resource_uri,
                parameters=params
            )
            
            result = await gateway_instance.access_resource(resource_request)
            
            if result.success:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "contents": [
                            {
                                "uri": resource_uri,
                                "mimeType": result.mime_type or "text/plain",
                                "text": result.content or ""
                            }
                        ]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Resource access failed: {result.error}"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in resources/read: {e}")
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Args:
        app: FastAPI application instance
    """
    gateway = app.state.gateway
    
    # Startup
    logger.info("Starting MCP Gateway application")

    try:
        # Start gateway
        await gateway.start()

        # Start FastMCP server
        mcp_server = await get_gateway_server()
        app.state.mcp_server = mcp_server

        # Set gateway for SSE manager
        sse_manager.set_gateway(gateway)

        # Start periodic SSE updates
        await start_periodic_updates()

        logger.info("MCP Gateway application started successfully")

        yield

    except Exception as e:
        logger.error(f"Failed to start MCP Gateway: {e}")
        raise

    finally:
        # Shutdown
        logger.info("Shutting down MCP Gateway application")

        if gateway:
            await gateway.stop()

        logger.info("MCP Gateway application shutdown complete")


def create_app(gateway: MCPGateway, settings: Settings) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        gateway: MCP Gateway instance
        settings: Application settings

    Returns:
        Configured FastAPI application
    """
    # Create FastAPI application
    app = FastAPI(
        title="MCP Portal",
        description="Centralized Model Context Protocol Aggregation Service",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan
    )

    # Store gateway in app state
    app.state.gateway = gateway
    set_gateway(gateway)

    # Setup middleware
    setup_middleware(app)

    # Add root-level /sse endpoint (required for FastMCP compatibility)
    @app.get("/sse")
    async def root_sse_endpoint(request: Request):
        """Root-level SSE endpoint for MCP compatibility"""
        logger.info("Root-level SSE endpoint requested")
        
        # Create connection ID
        import uuid
        import asyncio
        connection_id = str(uuid.uuid4())
        logger.info(f"New root-level SSE connection: {connection_id}")
        
        # Create MCP transport and SSE stream
        from ..core.mcp_transport import MCPSSETransport
        transport = MCPSSETransport(gateway)
        
        # Return EventSourceResponse for SSE stream
        return await transport.create_mcp_sse_stream(request)

    @app.post("/sse")
    async def root_sse_post_endpoint(request: Request):
        """Root-level SSE POST endpoint for MCP clients that send initialize directly to SSE endpoint"""
        logger.info("Root-level SSE POST endpoint requested")
        
        # Get the JSON body
        try:
            body = await request.json()
            logger.info(f"Received MCP message at /sse: {body}")
        except Exception as e:
            logger.error(f"Failed to parse JSON body at /sse: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        # Handle MCP message (same as /messages endpoint)
        try:
            response = await handle_mcp_message(body, gateway)
            logger.info(f"MCP response from /sse: {response}")
            return response
        except Exception as e:
            logger.error(f"Error handling MCP message at /sse: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Internal server error")

    # Add root-level /messages endpoint (required for FastMCP compatibility)
    @app.post("/messages")
    async def root_messages_endpoint(request: Request):
        """Root-level MCP messages endpoint with optional Bearer token validation"""
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header and not auth_header.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
        
        if auth_header:
            token = auth_header.replace("Bearer ", "")
            if token != "anonymous-token":
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail="Invalid access token")
        
        logger.info("Root-level MCP messages endpoint requested")
        
        # Get the JSON body
        try:
            body = await request.json()
            logger.info(f"Received MCP message: {body}")
        except Exception as e:
            logger.error(f"Failed to parse JSON body: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Invalid JSON")
        
        # Forward to MCP transport
        try:
            # We can use the mcp_gateway instance to handle the request
            response = await handle_mcp_message(body, gateway)
            logger.info(f"MCP response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error handling MCP message: {e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Internal server error")

    # Add root-level endpoints for MCP compatibility
    @app.get("/.well-known/oauth-protected-resource")
    async def oauth_protected_resource():
        """OAuth Protected Resource Metadata - indicates no auth required"""
        return {
            "resource": "http://host.docker.internal:8020",
            "authorization_servers": []  # Empty array indicates no authorization required
        }

    @app.get("/.well-known/oauth-authorization-server")
    async def oauth_authorization_server():
        """OAuth Authorization Server Metadata - minimal response"""
        return {
            "issuer": "http://host.docker.internal:8020",
            "authorization_endpoint": "http://host.docker.internal:8020/authorize",
            "token_endpoint": "http://host.docker.internal:8020/token",
            "registration_endpoint": "http://host.docker.internal:8020/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"]
        }

    @app.post("/register")
    async def oauth_register(request: Request):
        """OAuth Dynamic Client Registration - return a properly formatted client"""
        try:
            # Parse the registration request
            body = await request.json()
            logger.info(f"OAuth client registration request: {body}")
            
            # Extract redirect URIs from the request or provide defaults
            redirect_uris = body.get("redirect_uris", [
                "http://host.docker.internal:8020/callback",
                "http://localhost:8020/callback"
            ])
            
            # Return proper OAuth client registration response
            response = {
                "client_id": "anonymous-client",
                "client_secret": "not-required",
                "redirect_uris": redirect_uris,
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
                "client_name": body.get("client_name", "Claude Code MCP Client"),
                "client_uri": body.get("client_uri", ""),
                "logo_uri": body.get("logo_uri", ""),
                "scope": body.get("scope", ""),
                "contacts": body.get("contacts", []),
                "tos_uri": body.get("tos_uri", ""),
                "policy_uri": body.get("policy_uri", ""),
                "jwks_uri": body.get("jwks_uri", ""),
                "software_id": body.get("software_id", ""),
                "software_version": body.get("software_version", "")
            }
            
            logger.info(f"OAuth client registration response: {response}")
            return response
            
        except Exception as e:
            logger.error(f"OAuth registration error: {e}")
            # Return minimal response if JSON parsing fails
            return {
                "client_id": "anonymous-client",
                "client_secret": "not-required", 
                "redirect_uris": [
                    "http://host.docker.internal:8020/callback",
                    "http://localhost:8020/callback"
                ],
                "grant_types": ["authorization_code"],
                "response_types": ["code"]
            }

    @app.get("/authorize")
    async def oauth_authorize(request: Request):
        """OAuth Authorization - immediately redirect with dummy code"""
        redirect_uri = request.query_params.get("redirect_uri", "http://host.docker.internal:8020")
        state = request.query_params.get("state", "")
        
        # Immediately redirect with a dummy authorization code
        return RedirectResponse(url=f"{redirect_uri}?code=anonymous-code&state={state}")

    @app.post("/token")
    async def oauth_token(request: Request):
        """OAuth Token Exchange - return anonymous access token"""
        return {
            "access_token": "anonymous-token",
            "token_type": "Bearer",
            "expires_in": 3600
        }

    # Include API routes (FastMCP SSE endpoint is included in these routes)
    app.include_router(api_router, prefix="/api/v1")

    # Static files
    static_dir = Path(__file__).parent.parent / "ui" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    else:
        logger.warning(f"Static directory not found: {static_dir}")

    # Root endpoint
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """
        Serve the management UI.

        Returns:
            HTML response with the management interface
        """
        html_file = static_dir / "index.html"

        if html_file.exists():
            return FileResponse(html_file)
        else:
            return HTMLResponse(
                content="""
                <html>
                        <head><title>MCP Portal</title></head>
    <body>
    <h1>MCP Portal</h1>
                        <p>Management UI not available</p>
                        <p><a href="/api/docs">API Documentation</a></p>
                    </body>
                </html>
                """,
                status_code=200
            )

    # UI endpoint
    @app.get("/ui", response_class=HTMLResponse)
    async def ui():
        """
        Serve the management UI (alternative endpoint).

        Returns:
            HTML response with the management interface
        """
        return await root()

    # Events endpoint
    @app.get("/api/v1/events")
    async def stream_events(request: Request, gateway: MCPGateway = Depends(get_gateway)):
        """
        Server-Sent Events endpoint for real-time updates.

        Args:
            request: FastAPI request object
            gateway: Gateway instance

        Returns:
            EventSourceResponse for SSE streaming
        """
        return await create_event_stream(request, gateway)

    # Favicon endpoint
    @app.get("/favicon.ico")
    async def favicon():
        """
        Serve favicon.

        Returns:
            Favicon response
        """
        # Return a simple SVG favicon
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="40" fill="#2563eb"/>
        <text x="50" y="65" text-anchor="middle" fill="white" font-size="50" font-family="Arial">🌐</text>
        </svg>"""

        return HTMLResponse(content=svg_content, media_type="image/svg+xml")

    # Health check endpoint
    @app.get("/health")
    async def health():
        """
        Simple health check endpoint.

        Returns:
            Health status
        """
        try:
            if gateway:
                status = await gateway.get_status()
                return {
                    "status": "healthy",
                    "active_servers": status.active_servers,
                    "total_servers": status.total_servers,
                    "uptime": status.uptime
                }
            else:
                return {"status": "starting"}
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {"status": "error", "message": str(e)}

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Global exception handler.

        Args:
            request: Request that caused the exception
            exc: Exception that occurred

        Returns:
            Error response
        """
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return HTMLResponse(
            content="""
            <html>
                <head><title>Error</title></head>
                <body>
                    <h1>Internal Server Error</h1>
                    <p>An unexpected error occurred.</p>
                    <p><a href="/">Return to Home</a></p>
                </body>
            </html>
            """,
            status_code=500
        )

    return app 