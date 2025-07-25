"""
Unified Stdio Transport Handler for MCP Portal.

This module provides a framework-agnostic stdio transport handler that can work
with both 'mcp' and 'fastmcp' frameworks, ensuring compatibility across the
entire MCP ecosystem.
"""

import asyncio
import json
import logging
import subprocess
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp

from ..config.settings import MCPServerConfig
from ..models.mcp import (
    MCPRequest,
    MCPResponse,
    MCPTool,
    MCPResource,
    MCPServerStatus,
)

logger = logging.getLogger(__name__)


class MCPFramework(str, Enum):
    """Detected MCP framework types."""
    MCP = "mcp"
    FASTMCP = "fastmcp"
    UNKNOWN = "unknown"


class TransportType(str, Enum):
    """Transport types for MCP communication."""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


class FrameworkDetector:
    """Detects which MCP framework a server is using based on responses."""
    
    @staticmethod
    def detect_transport_type(config: MCPServerConfig) -> TransportType:
        """
        Detect transport type based on server configuration.
        
        Args:
            config: MCP server configuration
            
        Returns:
            Detected transport type
        """
        if config.url:
            # URL-based servers use SSE or HTTP transport
            if config.transport and config.transport.lower() == "http":
                return TransportType.HTTP
            return TransportType.SSE
        elif config.command:
            # Command-based servers use stdio transport
            return TransportType.STDIO
        else:
            # Default to stdio for backward compatibility
            return TransportType.STDIO
    
    @staticmethod
    def detect_framework(server_info: Dict[str, Any], capabilities: Dict[str, Any]) -> MCPFramework:
        """
        Detect framework type based on server info and capabilities.
        
        FastMCP tends to have:
        - More flexible capability structures
        - Different server info patterns
        - Enhanced protocol extensions
        
        Standard MCP tends to have:
        - Stricter capability structures
        - Standard protocol conformance
        """
        # Check server info patterns
        if server_info:
            name = server_info.get("name", "").lower()
            version = server_info.get("version", "")
            
            # FastMCP typically includes framework identifiers
            if "fastmcp" in name or "fast-mcp" in name:
                return MCPFramework.FASTMCP
            
            # Check for FastMCP version patterns
            if "fastmcp" in version.lower():
                return MCPFramework.FASTMCP
        
        # Check capability patterns
        if capabilities:
            # FastMCP often includes extended capabilities
            if "experimental" in capabilities:
                return MCPFramework.FASTMCP
            
            # FastMCP may have more flexible resource/tool structures
            resources_cap = capabilities.get("resources", {})
            tools_cap = capabilities.get("tools", {})
            
            # FastMCP tends to have richer capability descriptions
            if isinstance(resources_cap, dict) and len(resources_cap) > 2:
                return MCPFramework.FASTMCP
            if isinstance(tools_cap, dict) and len(tools_cap) > 2:
                return MCPFramework.FASTMCP
        
        # Default to standard MCP
        return MCPFramework.MCP


class SchemaEnhancer:
    """Enhances and normalizes tool schemas for cross-framework compatibility."""
    
    @staticmethod
    def normalize_tool_schema(tool_data: Dict[str, Any], framework: MCPFramework) -> Dict[str, Any]:
        """
        Normalize tool schema to ensure compatibility across frameworks.
        
        Args:
            tool_data: Raw tool data from the server
            framework: Detected framework type
            
        Returns:
            Normalized tool schema
        """
        input_schema = tool_data.get("inputSchema", {})
        
        # Handle empty or minimal schemas
        if not input_schema or input_schema == {}:
            logger.warning(f"Tool '{tool_data.get('name')}' has empty schema, generating default")
            input_schema = SchemaEnhancer._generate_default_schema(tool_data, framework)
        
        # Normalize schema structure for consistency
        input_schema = SchemaEnhancer._normalize_schema_structure(input_schema, framework)
        
        # Ensure required fields exist
        if "type" not in input_schema:
            input_schema["type"] = "object"
        
        if "properties" not in input_schema and input_schema["type"] == "object":
            input_schema["properties"] = {}
        
        return input_schema
    
    @staticmethod
    def _generate_default_schema(tool_data: Dict[str, Any], framework: MCPFramework) -> Dict[str, Any]:
        """Generate a default schema for tools without proper schemas."""
        tool_name = tool_data.get("name", "unknown")
        description = tool_data.get("description", "")
        
        # Create a basic object schema that accepts any parameters
        default_schema = {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
            "description": f"Schema for {tool_name}: {description}"
        }
        
        # Add common parameter patterns based on tool name
        common_params = SchemaEnhancer._infer_common_parameters(tool_name, description)
        if common_params:
            default_schema["properties"].update(common_params)
        
        return default_schema
    
    @staticmethod
    def _infer_common_parameters(tool_name: str, description: str) -> Dict[str, Any]:
        """Infer common parameters based on tool name and description."""
        params = {}
        
        # Common patterns for different tool types
        if any(keyword in tool_name.lower() for keyword in ["search", "query", "find"]):
            params["query"] = {
                "type": "string",
                "description": "Search query or terms"
            }
        
        if any(keyword in tool_name.lower() for keyword in ["read", "get", "fetch"]):
            params["path"] = {
                "type": "string",
                "description": "Path or identifier to read"
            }
            params["uri"] = {
                "type": "string", 
                "description": "URI to fetch"
            }
        
        if any(keyword in tool_name.lower() for keyword in ["write", "create", "update"]):
            params["content"] = {
                "type": "string",
                "description": "Content to write or update"
            }
        
        if any(keyword in tool_name.lower() for keyword in ["file", "path"]):
            params["file_path"] = {
                "type": "string",
                "description": "File system path"
            }
        
        return params
    
    @staticmethod
    def _normalize_schema_structure(schema: Dict[str, Any], framework: MCPFramework) -> Dict[str, Any]:
        """Normalize schema structure based on framework differences."""
        if framework == MCPFramework.FASTMCP:
            # FastMCP may use different schema patterns
            # Normalize any FastMCP-specific schema extensions
            if "arguments" in schema and "properties" not in schema:
                # Convert FastMCP argument format to standard JSON schema
                properties = {}
                required = []
                
                for arg in schema.get("arguments", []):
                    if isinstance(arg, dict) and "name" in arg:
                        prop_name = arg["name"]
                        properties[prop_name] = {
                            "type": arg.get("type", "string"),
                            "description": arg.get("description", "")
                        }
                        if arg.get("required", False):
                            required.append(prop_name)
                
                schema = {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
        
        return schema


class UnifiedTransportBase(ABC):
    """
    Abstract base class for unified MCP transport handlers.
    
    Provides common interface for both stdio and SSE/HTTP transport types.
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.server_info: Optional[Dict[str, Any]] = None
        self.capabilities: Dict[str, Any] = {}
        self.tools: List[MCPTool] = []
        self.resources: List[MCPResource] = []
        self.initialized = False
        self.framework = MCPFramework.UNKNOWN
        self.transport_type = FrameworkDetector.detect_transport_type(config)
        self.request_id_counter = 0
    
    def generate_request_id(self) -> str:
        """Generate unique request ID."""
        self.request_id_counter += 1
        return f"{self.config.name}_{self.request_id_counter}_{uuid.uuid4().hex[:8]}"
    
    @abstractmethod
    async def start(self) -> bool:
        """Start the transport connection."""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the transport connection."""
        pass
    
    @abstractmethod
    async def send_request(self, request: MCPRequest, timeout: float = 60.0) -> MCPResponse:
        """Send a request to the server."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if the transport is running."""
        pass
    
    async def list_tools(self) -> List[MCPTool]:
        """List available tools with enhanced schema processing."""
        if not self.initialized:
            return []
        
        try:
            request = MCPRequest(
                id=self.generate_request_id(),
                method="tools/list",
                params={}
            )
            
            response = await self.send_request(request)
            
            if response.error:
                logger.error(f"List tools failed for {self.config.name}: {response.error}")
                return []
            
            if response.result and "tools" in response.result:
                tools = []
                for tool_data in response.result["tools"]:
                    # Enhance and normalize the tool schema
                    enhanced_schema = SchemaEnhancer.normalize_tool_schema(
                        tool_data, self.framework
                    )
                    
                    tool = MCPTool(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        inputSchema=enhanced_schema
                    )
                    tools.append(tool)
                    
                    logger.debug(f"Enhanced tool '{tool_data['name']}' from {self.config.name} "
                               f"({self.framework.value}) with schema: {enhanced_schema}")
                
                self.tools = tools
                logger.info(f"Listed {len(tools)} tools from {self.framework.value} server {self.config.name}")
                return tools
            
            return []
            
        except Exception as e:
            logger.error(f"Error listing tools from {self.config.name}: {e}")
            return []
    
    async def list_resources(self) -> List[MCPResource]:
        """List available resources with framework-specific handling."""
        if not self.initialized:
            return []
        
        try:
            request = MCPRequest(
                id=self.generate_request_id(),
                method="resources/list",
                params={}
            )
            
            response = await self.send_request(request)
            
            if response.error:
                logger.error(f"List resources failed for {self.config.name}: {response.error}")
                return []
            
            if response.result and "resources" in response.result:
                resources = []
                for resource_data in response.result["resources"]:
                    resource = MCPResource(
                        uri=resource_data["uri"],
                        name=resource_data.get("name", ""),
                        description=resource_data.get("description", ""),
                        mimeType=resource_data.get("mimeType", "text/plain")
                    )
                    resources.append(resource)
                
                self.resources = resources
                logger.info(f"Listed {len(resources)} resources from {self.framework.value} server {self.config.name}")
                return resources
            
            return []
            
        except Exception as e:
            logger.error(f"Error listing resources from {self.config.name}: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool with framework-aware argument processing."""
        if not self.initialized:
            raise RuntimeError(f"MCP server {self.config.name} not initialized")
        
        try:
            # Get appropriate timeout based on tool type
            timeout = self._get_tool_timeout(tool_name)
            
            # Process arguments based on detected framework
            processed_args = self._process_tool_arguments(tool_name, arguments)
            
            request = MCPRequest(
                id=self.generate_request_id(),
                method="tools/call",
                params={
                    "name": tool_name,
                    "arguments": processed_args
                }
            )
            
            response = await self.send_request(request, timeout=timeout)
            
            if response.error:
                error_msg = response.error
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                raise RuntimeError(f"Tool call failed: {error_msg}")
            
            # Process response based on framework
            return self._process_tool_response(response.result or {})
            
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {self.config.name}: {e}")
            raise
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource with framework-specific handling."""
        if not self.initialized:
            raise RuntimeError(f"MCP server {self.config.name} not initialized")
        
        try:
            request = MCPRequest(
                id=self.generate_request_id(),
                method="resources/read",
                params={"uri": uri}
            )
            
            response = await self.send_request(request)
            
            if response.error:
                error_msg = response.error
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                raise RuntimeError(f"Resource read failed: {error_msg}")
            
            return response.result or {}
            
        except Exception as e:
            logger.error(f"Error reading resource {uri} from {self.config.name}: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Perform health check on the server."""
        if not self.is_running() or not self.initialized:
            return False
        
        try:
            # Try to list tools as a simple health check
            await self.list_tools()
            return True
        except Exception as e:
            logger.debug(f"Health check failed for {self.config.name}: {e}")
            return False
    
    def _process_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Process tool arguments based on detected framework."""
        if self.framework == MCPFramework.FASTMCP:
            # FastMCP may require different argument formats
            # Convert any complex types to strings if needed
            processed = {}
            for key, value in arguments.items():
                if isinstance(value, (dict, list)):
                    # FastMCP might expect JSON strings for complex types
                    processed[key] = json.dumps(value)
                else:
                    processed[key] = value
            return processed
        else:
            # Standard MCP processing
            return arguments
    
    def _process_tool_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process tool response based on detected framework."""
        if self.framework == MCPFramework.FASTMCP:
            # FastMCP might have different response formats
            # Handle any FastMCP-specific response processing
            if "content" in result and isinstance(result["content"], list):
                # FastMCP might return content as a list of content blocks
                content_blocks = result["content"]
                if content_blocks and isinstance(content_blocks[0], dict):
                    if "text" in content_blocks[0]:
                        result["text"] = content_blocks[0]["text"]
        
        return result
    
    def _get_tool_timeout(self, tool_name: str) -> float:
        """Get appropriate timeout for tool based on its type and framework."""
        # Network-based tools that need more time
        network_tools = {
            'brave_web_search', 'web_search', 'search', 'fetch', 'crawl', 
            'scrape', 'api_call', 'http_request', 'download'
        }
        
        # AI/LLM tools that need more time
        ai_tools = {
            'generate', 'completion', 'embedding', 'analyze', 'summarize'
        }
        
        tool_lower = tool_name.lower()
        
        if any(keyword in tool_lower for keyword in network_tools):
            return 120.0  # 2 minutes for network tools
        elif any(keyword in tool_lower for keyword in ai_tools):
            return 90.0   # 1.5 minutes for AI tools
        elif self.framework == MCPFramework.FASTMCP:
            # FastMCP tools might need slightly more time due to additional processing
            return 75.0
        else:
            return 60.0   # 1 minute default


class UnifiedStdioTransport(UnifiedTransportBase):
    """
    Framework-agnostic stdio transport handler that works with both mcp and fastmcp.
    
    This class handles the differences between MCP frameworks by:
    1. Detecting the framework type during initialization
    2. Adapting message formats and schemas accordingly  
    3. Providing unified error handling and response processing
    4. Normalizing tool and resource definitions
    """
    
    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self.process: Optional[subprocess.Popen] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.stdout_task: Optional[asyncio.Task] = None
        self.stderr_task: Optional[asyncio.Task] = None
    
    async def start(self) -> bool:
        """Start the stdio transport connection."""
        if not self.config.command:
            logger.error(f"No command specified for stdio server {self.config.name}")
            return False
        
        command_parts = [self.config.command]
        if self.config.args:
            command_parts.extend(self.config.args)
        
        env = dict(self.config.env or {})
        return await self.start_process(command_parts, env)
    
    async def start_process(self, command_parts: List[str], env: Dict[str, str]) -> bool:
        """
        Start the MCP server process.
        
        Args:
            command_parts: Command and arguments to start the server
            env: Environment variables for the process
            
        Returns:
            True if process started successfully
        """
        try:
            logger.info(f"Starting MCP server {self.config.name} with command: {' '.join(command_parts)}")
            
            # Start process with explicit UTF-8 encoding for cross-platform compatibility
            self.process = subprocess.Popen(
                command_parts,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace invalid characters instead of crashing
                env=env,
                bufsize=1,  # Line buffered
                universal_newlines=True,
            )
            
            # Start communication tasks
            await self.start_communication()
            
            # Initialize with framework detection
            success = await self.initialize_with_detection()
            
            if success:
                # Discover capabilities after successful initialization
                await self.discover_capabilities()
                logger.info(f"Successfully started {self.framework.value} server: {self.config.name}")
                return True
            else:
                await self.stop()
                return False
                
        except Exception as e:
            logger.error(f"Error starting MCP server {self.config.name}: {e}")
            await self.stop()
            return False
    
    async def start_communication(self):
        """Start reading from stdout and stderr."""
        if self.process and self.process.stdout:
            self.stdout_task = asyncio.create_task(self._read_stdout())
        if self.process and self.process.stderr:
            self.stderr_task = asyncio.create_task(self._read_stderr())
    
    async def _read_stdout(self):
        """Read and process stdout from the MCP server."""
        try:
            while self.process and self.process.poll() is None:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdout.readline
                )
                if not line:
                    break
                
                line = line.strip()
                if line:
                    try:
                        response_data = json.loads(line)
                        await self._handle_response(response_data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON from {self.config.name}: {line}")
                    except Exception as e:
                        logger.error(f"Error processing response from {self.config.name}: {e}")
        except Exception as e:
            logger.error(f"Error reading stdout from {self.config.name}: {e}")
    
    async def _read_stderr(self):
        """Read and log stderr from the MCP server."""
        try:
            while self.process and self.process.poll() is None:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stderr.readline
                )
                if not line:
                    break
                
                line = line.strip()
                if line:
                    logger.debug(f"[{self.config.name}] stderr: {line}")
        except Exception as e:
            logger.error(f"Error reading stderr from {self.config.name}: {e}")
    
    async def _handle_response(self, response_data: Dict[str, Any]):
        """Handle a response from the MCP server with framework-specific processing."""
        try:
            # Handle both standard MCP and FastMCP response formats
            response = self._normalize_response(response_data)
            
            # Handle response to a specific request
            if response.id and response.id in self.pending_requests:
                future = self.pending_requests.pop(response.id)
                if not future.done():
                    future.set_result(response)
            else:
                # Handle notifications or unexpected responses
                await self._handle_notification(response_data)
                
        except Exception as e:
            logger.error(f"Error handling response from {self.config.name}: {e}")
    
    def _normalize_response(self, response_data: Dict[str, Any]) -> MCPResponse:
        """Normalize response data to standard MCPResponse format."""
        # Handle different response formats between frameworks
        if "jsonrpc" not in response_data:
            response_data["jsonrpc"] = "2.0"
        
        # Ensure proper error format
        if "error" in response_data and isinstance(response_data["error"], str):
            response_data["error"] = {
                "code": -1,
                "message": response_data["error"]
            }
        
        return MCPResponse(**response_data)
    
    async def _handle_notification(self, response_data: Dict[str, Any]):
        """Handle notifications from the server."""
        method = response_data.get("method")
        
        if method == "notifications/tools/list_changed":
            logger.debug(f"Tools list changed notification from {self.config.name}")
            # Refresh tools list
            await self.list_tools()
        elif method == "notifications/resources/list_changed":
            logger.debug(f"Resources list changed notification from {self.config.name}")
            # Refresh resources list
            await self.list_resources()
        else:
            logger.debug(f"Received notification from {self.config.name}: {method}")
    
    async def initialize_with_detection(self) -> bool:
        """Initialize the server and detect which framework it's using."""
        try:
            # Send initialize request
            init_request = MCPRequest(
                id=self.generate_request_id(),
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {},
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "mcp-gateway-unified",
                        "version": "1.0.0"
                    }
                }
            )
            
            response = await self.send_request(init_request, timeout=30.0)
            
            if response.error:
                logger.error(f"Initialize failed for {self.config.name}: {response.error}")
                return False
            
            if response.result:
                self.server_info = response.result.get("serverInfo", {})
                self.capabilities = response.result.get("capabilities", {})
                
                # Detect framework based on initialization response
                self.framework = FrameworkDetector.detect_framework(
                    self.server_info, self.capabilities
                )
                
                logger.info(f"Detected {self.framework.value} framework for server {self.config.name}")
                
                # Send initialized notification (required by protocol)
                await self._send_initialized_notification()
                
                self.initialized = True
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error initializing {self.config.name}: {e}")
            return False
    
    async def _send_initialized_notification(self):
        """Send the initialized notification with framework-specific handling."""
        try:
            # Both FastMCP and standard MCP use the same notification format
            # Notifications don't have IDs - they're fire-and-forget
            notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            # Send as fire-and-forget notification
            await self._send_raw_message(notification)
            
        except Exception as e:
            logger.error(f"Error sending initialized notification to {self.config.name}: {e}")
    
    async def discover_capabilities(self):
        """Discover server capabilities after initialization."""
        try:
            # Try to list tools and resources
            self.tools = await self.list_tools()
            self.resources = await self.list_resources()
            
            logger.info(f"Discovered {len(self.tools)} tools and {len(self.resources)} resources from {self.config.name}")
            
        except Exception as e:
            logger.warning(f"Error discovering capabilities for {self.config.name}: {e}")
    
    async def send_request(self, request: MCPRequest, timeout: float = 60.0) -> MCPResponse:
        """Send a request to the server with framework-aware processing."""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError(f"MCP server {self.config.name} is not running")
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request.id] = future
        
        try:
            # Send request
            await self._send_raw_message(request.model_dump())
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request.id, None)
            raise TimeoutError(f"Request to {self.config.name} timed out after {timeout}s")
        except Exception as e:
            self.pending_requests.pop(request.id, None)
            raise RuntimeError(f"Error sending request to {self.config.name}: {e}")
    
    async def _send_raw_message(self, message: Union[Dict[str, Any], MCPRequest]):
        """Send a raw message to the server process."""
        if not self.process or not self.process.stdin:
            raise RuntimeError(f"Process stdin not available for {self.config.name}")
        
        # Convert to dict if it's a Pydantic model
        if hasattr(message, 'model_dump'):
            message = message.model_dump()
        
        message_json = json.dumps(message) + "\n"
        
        try:
            # Write message to stdin
            self.process.stdin.write(message_json)
            self.process.stdin.flush()
            
        except Exception as e:
            logger.error(f"Error sending message to {self.config.name}: {e}")
            raise
    
    async def stop(self):
        """Stop the MCP server process and clean up resources."""
        try:
            # Cancel communication tasks
            if self.stdout_task and not self.stdout_task.done():
                self.stdout_task.cancel()
                try:
                    await self.stdout_task
                except asyncio.CancelledError:
                    pass
            
            if self.stderr_task and not self.stderr_task.done():
                self.stderr_task.cancel()
                try:
                    await self.stderr_task
                except asyncio.CancelledError:
                    pass
            
            # Terminate process
            if self.process and self.process.poll() is None:
                self.process.terminate()
                
                # Wait for process to terminate gracefully
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, self.process.wait),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Process {self.config.name} did not terminate gracefully, killing")
                    self.process.kill()
                    await asyncio.get_event_loop().run_in_executor(None, self.process.wait)
            
            # Clear pending requests
            for future in self.pending_requests.values():
                if not future.done():
                    future.cancel()
            self.pending_requests.clear()
            
            logger.info(f"Stopped {self.framework.value} server {self.config.name}")
            
        except Exception as e:
            logger.error(f"Error stopping MCP server {self.config.name}: {e}")
    
    def is_running(self) -> bool:
        """Check if the server process is running."""
        return self.process is not None and self.process.poll() is None


class UnifiedSSETransport(UnifiedTransportBase):
    """
    Unified SSE transport handler for MCP servers that communicate over HTTP/SSE.
    
    This class handles SSE-based MCP servers by:
    1. Establishing HTTP connections to SSE endpoints
    2. Managing session-based communication
    3. Handling MCP protocol over HTTP POST requests
    4. Providing unified error handling and reconnection logic
    """
    
    def __init__(self, config: MCPServerConfig):
        super().__init__(config)
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_url = config.url
        self.session_id: Optional[str] = None
        self.sse_task: Optional[asyncio.Task] = None
        self.pending_requests: Dict[str, asyncio.Future] = {}
        
        # Allow custom SSE and messages endpoints from config
        # Handle empty strings properly (empty string is valid and different from None)
        sse_val = getattr(config, 'sse_endpoint', '/sse')
        messages_val = getattr(config, 'messages_endpoint', '/messages')
        
        self.sse_endpoint = sse_val if sse_val is not None else '/sse'
        self.messages_endpoint = messages_val if messages_val is not None else '/messages'
        
        logger.info(f"SSE server {config.name} using endpoints: SSE='{self.sse_endpoint}' Messages='{self.messages_endpoint}'")
    
    async def start(self) -> bool:
        """Start the SSE transport connection."""
        if not self.config.url:
            logger.error(f"No URL specified for SSE server {self.config.name}")
            return False
        
        try:
            # Create HTTP session
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Start SSE connection
            success = await self._establish_sse_connection()
            
            if success:
                # Initialize with framework detection
                success = await self.initialize_with_detection()
                
                if success:
                    # Discover capabilities after successful initialization
                    await self.discover_capabilities()
                    logger.info(f"Successfully started SSE server: {self.config.name}")
                    return True
            
            await self.stop()
            return False
            
        except Exception as e:
            logger.error(f"Error starting SSE server {self.config.name}: {e}")
            await self.stop()
            return False
    
    async def _establish_sse_connection(self) -> bool:
        """Establish SSE connection to the server."""
        try:
            sse_url = f"{self.base_url}{self.sse_endpoint}"
            logger.info(f"SSE connection URL construction: base_url='{self.base_url}' + sse_endpoint='{self.sse_endpoint}' = '{sse_url}'")
            logger.info(f"Attempting to establish SSE connection to: {sse_url}")
            
            # Start SSE connection
            self.sse_task = asyncio.create_task(
                self._handle_sse_stream(sse_url),
                name=f"sse-stream-{self.config.name}"
            )
            
            # Wait a moment for connection to establish
            await asyncio.sleep(0.1)
            
            return not self.sse_task.done()
            
        except Exception as e:
            logger.error(f"Error establishing SSE connection for {self.config.name}: {e}")
            return False
    
    async def _handle_sse_stream(self, sse_url: str):
        """Handle SSE stream from the server."""
        retry_count = 0
        max_retries = self.config.max_retries
        
        while retry_count < max_retries:
            try:
                logger.info(f"Connecting to SSE stream: {sse_url} (attempt {retry_count + 1})")
                
                async with self.session.get(sse_url) as response:
                    if response.status != 200:
                        raise aiohttp.ClientError(f"SSE connection failed with status {response.status}")
                    
                    # Reset retry count on successful connection
                    retry_count = 0
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            try:
                                event_data = json.loads(data)
                                await self._handle_sse_message(event_data)
                            except json.JSONDecodeError:
                                logger.debug(f"Non-JSON SSE data from {self.config.name}: {data}")
                        elif line.startswith('event: '):
                            event_type = line[7:]  # Remove 'event: ' prefix
                            logger.debug(f"SSE event type from {self.config.name}: {event_type}")
                
            except asyncio.CancelledError:
                logger.info(f"SSE stream cancelled for {self.config.name}")
                break
            except Exception as e:
                retry_count += 1
                logger.warning(f"SSE connection error for {self.config.name} (attempt {retry_count}): {e}")
                
                if retry_count < max_retries:
                    # Exponential backoff
                    wait_time = min(2 ** retry_count, 30)
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries exceeded for SSE connection to {self.config.name}")
                    break
    
    async def _handle_sse_message(self, message: Dict[str, Any]):
        """Handle a message received via SSE."""
        try:
            # Check for endpoint notification (MCP protocol requirement)
            if message.get("type") == "endpoint":
                endpoint = message.get("endpoint")
                if endpoint:
                    logger.info(f"Received endpoint from {self.config.name}: {endpoint}")
                return
            
            # Handle regular MCP responses
            if "jsonrpc" in message:
                response = self._normalize_response(message)
                
                # Handle response to a specific request
                if response.id and response.id in self.pending_requests:
                    future = self.pending_requests.pop(response.id)
                    if not future.done():
                        future.set_result(response)
                else:
                    # Handle notifications
                    await self._handle_notification(message)
                    
        except Exception as e:
            logger.error(f"Error handling SSE message from {self.config.name}: {e}")
    
    def _normalize_response(self, response_data: Dict[str, Any]) -> MCPResponse:
        """Normalize response data to standard MCPResponse format."""
        # Handle different response formats between frameworks
        if "jsonrpc" not in response_data:
            response_data["jsonrpc"] = "2.0"
        
        # Ensure proper error format
        if "error" in response_data and isinstance(response_data["error"], str):
            response_data["error"] = {
                "code": -1,
                "message": response_data["error"]
            }
        
        return MCPResponse(**response_data)
    
    async def _handle_notification(self, message: Dict[str, Any]):
        """Handle notifications from the server."""
        method = message.get("method")
        
        if method == "notifications/tools/list_changed":
            logger.debug(f"Tools list changed notification from {self.config.name}")
            # Refresh tools list
            await self.list_tools()
        elif method == "notifications/resources/list_changed":
            logger.debug(f"Resources list changed notification from {self.config.name}")
            # Refresh resources list
            await self.list_resources()
        elif method == "notifications/ping":
            # Heartbeat/keepalive - no action needed
            logger.debug(f"Received ping from {self.config.name}")
        else:
            logger.debug(f"Received notification from {self.config.name}: {method}")
    
    async def send_request(self, request: MCPRequest, timeout: float = 60.0) -> MCPResponse:
        """Send a request to the SSE server via HTTP POST."""
        if not self.session or self.session.closed:
            raise RuntimeError(f"SSE server {self.config.name} session not available")
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request.id] = future
        
        try:
            # Send request via HTTP POST
            request_url = f"{self.base_url}{self.messages_endpoint}"
            if self.session_id:
                request_url += f"?sessionId={self.session_id}"
            
            logger.info(f"Messages URL construction: base_url='{self.base_url}' + messages_endpoint='{self.messages_endpoint}' = '{request_url}'")
            logger.debug(f"Sending MCP request to: {request_url}")
            
            headers = {
                "Content-Type": "application/json"
            }
            
            request_data = request.model_dump()
            
            async with self.session.post(request_url, json=request_data, headers=headers) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"HTTP request failed with status {response.status}")
            
            # Wait for response via SSE
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request.id, None)
            raise TimeoutError(f"Request to {self.config.name} timed out after {timeout}s")
        except Exception as e:
            self.pending_requests.pop(request.id, None)
            raise RuntimeError(f"Error sending request to {self.config.name}: {e}")
    
    async def initialize_with_detection(self) -> bool:
        """Initialize the server and detect which framework it's using."""
        try:
            # Send initialize request
            init_request = MCPRequest(
                id=self.generate_request_id(),
                method="initialize",
                params={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {},
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "mcp-gateway-unified-sse",
                        "version": "1.0.0"
                    }
                }
            )
            
            response = await self.send_request(init_request, timeout=30.0)
            
            if response.error:
                logger.error(f"Initialize failed for {self.config.name}: {response.error}")
                return False
            
            if response.result:
                self.server_info = response.result.get("serverInfo", {})
                self.capabilities = response.result.get("capabilities", {})
                
                # Detect framework based on initialization response
                self.framework = FrameworkDetector.detect_framework(
                    self.server_info, self.capabilities
                )
                
                logger.info(f"Detected {self.framework.value} framework for SSE server {self.config.name}")
                
                # Send initialized notification (required by protocol)
                await self._send_initialized_notification()
                
                self.initialized = True
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error initializing SSE server {self.config.name}: {e}")
            return False
    
    async def _send_initialized_notification(self):
        """Send the initialized notification."""
        try:
            notification = MCPRequest(
                id=self.generate_request_id(),
                method="notifications/initialized",
                params={}
            )
            
            # Send as fire-and-forget notification (no response expected)
            request_url = f"{self.base_url}{self.messages_endpoint}"
            if self.session_id:
                request_url += f"?sessionId={self.session_id}"
            
            headers = {"Content-Type": "application/json"}
            request_data = notification.model_dump()
            
            async with self.session.post(request_url, json=request_data, headers=headers) as response:
                if response.status != 200:
                    logger.warning(f"Initialized notification failed for {self.config.name}: status {response.status}")
            
        except Exception as e:
            logger.error(f"Error sending initialized notification to {self.config.name}: {e}")
    
    async def discover_capabilities(self):
        """Discover server capabilities after initialization."""
        try:
            # Try to list tools and resources
            self.tools = await self.list_tools()
            self.resources = await self.list_resources()
            
            logger.info(f"Discovered {len(self.tools)} tools and {len(self.resources)} resources from SSE server {self.config.name}")
            
        except Exception as e:
            logger.warning(f"Error discovering capabilities for SSE server {self.config.name}: {e}")
    
    async def stop(self):
        """Stop the SSE transport connection."""
        try:
            # Cancel SSE stream task
            if self.sse_task and not self.sse_task.done():
                self.sse_task.cancel()
                try:
                    await self.sse_task
                except asyncio.CancelledError:
                    pass
            
            # Close HTTP session
            if self.session and not self.session.closed:
                await self.session.close()
            
            # Clear pending requests
            for future in self.pending_requests.values():
                if not future.done():
                    future.cancel()
            self.pending_requests.clear()
            
            logger.info(f"Stopped SSE server {self.config.name}")
            
        except Exception as e:
            logger.error(f"Error stopping SSE server {self.config.name}: {e}")
    
    def is_running(self) -> bool:
        """Check if the SSE transport is running."""
        return (
            self.session is not None and 
            not self.session.closed and
            self.sse_task is not None and 
            not self.sse_task.done()
        )


def create_transport(config: MCPServerConfig) -> UnifiedTransportBase:
    """
    Create appropriate transport based on server configuration.
    
    Args:
        config: MCP server configuration
        
    Returns:
        Appropriate transport instance
    """
    transport_type = FrameworkDetector.detect_transport_type(config)
    
    if transport_type == TransportType.SSE or transport_type == TransportType.HTTP:
        return UnifiedSSETransport(config)
    else:
        return UnifiedStdioTransport(config)