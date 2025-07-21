"""
MCP Process Manager.

This module handles starting, managing, and communicating with
command-line MCP servers via stdin/stdout.
"""

import asyncio
import json
import logging
import os
import platform
import subprocess
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..config.settings import MCPServerConfig
from ..models.mcp import (
    MCPRequest,
    MCPResponse,
    MCPServer,
    MCPServerStatus,
    MCPTool,
    MCPResource,
)

logger = logging.getLogger(__name__)


class MCPProcess:
    """Represents a running MCP server process."""
    
    def __init__(self, config: MCPServerConfig, process: subprocess.Popen):
        self.config = config
        self.process = process
        self.server_info: Optional[Dict[str, Any]] = None
        self.capabilities: List[str] = []
        self.tools: List[MCPTool] = []
        self.resources: List[MCPResource] = []
        self.initialized = False
        self.request_id_counter = 0
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.stdout_task: Optional[asyncio.Task] = None
        self.stderr_task: Optional[asyncio.Task] = None
        
    def generate_request_id(self) -> str:
        """Generate unique request ID."""
        self.request_id_counter += 1
        return f"{self.config.name}_{self.request_id_counter}"
    
    async def start_communication(self):
        """Start reading from stdout and stderr."""
        if self.process.stdout:
            self.stdout_task = asyncio.create_task(self._read_stdout())
        if self.process.stderr:
            self.stderr_task = asyncio.create_task(self._read_stderr())
    
    async def _read_stdout(self):
        """Read and process stdout from the MCP server."""
        try:
            while True:
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
            while True:
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
        """Handle a response from the MCP server."""
        try:
            response = MCPResponse(**response_data)
            
            # Handle response to a specific request
            if response.id and response.id in self.pending_requests:
                future = self.pending_requests.pop(response.id)
                if not future.done():
                    future.set_result(response)
            else:
                # Handle notifications or unexpected responses
                logger.debug(f"Received unexpected response from {self.config.name}: {response_data}")
                
        except Exception as e:
            logger.error(f"Error handling response from {self.config.name}: {e}")
    
    async def send_request(self, request: MCPRequest, timeout: float = 60.0) -> MCPResponse:
        """Send a request to the MCP server and wait for response."""
        if not self.process or self.process.poll() is not None:
            raise RuntimeError(f"MCP server {self.config.name} is not running")
        
        request_json = json.dumps(request.model_dump()) + "\n"
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request.id] = future
        
        try:
            # Send request - ensure it's properly encoded as string for text mode
            if hasattr(self.process.stdin, 'write'):
                # Debug: Check what type request_json is
                logger.debug(f"Request JSON type: {type(request_json)}, value: {request_json[:100]}...")
                
                # Ensure we're writing a string, not bytes
                if isinstance(request_json, bytes):
                    logger.debug("Converting bytes to string")
                    request_json = request_json.decode('utf-8')
                elif not isinstance(request_json, str):
                    logger.debug(f"Converting {type(request_json)} to string")
                    request_json = str(request_json)
                
                # Try to write the request
                try:
                    self.process.stdin.write(request_json)
                    self.process.stdin.flush()
                except Exception as write_error:
                    logger.error(f"Write error details: {write_error}")
                    logger.error(f"stdin type: {type(self.process.stdin)}")
                    logger.error(f"stdin mode: {getattr(self.process.stdin, 'mode', 'unknown')}")
                    raise
            else:
                raise RuntimeError(f"Process stdin not available for {self.config.name}")
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request.id, None)
            raise TimeoutError(f"Request to {self.config.name} timed out")
        except Exception as e:
            self.pending_requests.pop(request.id, None)
            raise RuntimeError(f"Error sending request to {self.config.name}: {e}")
    
    async def initialize(self) -> bool:
        """Initialize the MCP server with handshake."""
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
                        "name": "mcp-gateway",
                        "version": "1.0.0"
                    }
                }
            )
            
            response = await self.send_request(init_request)
            
            if response.error:
                logger.error(f"Initialize failed for {self.config.name}: {response.error}")
                return False
            
            if response.result:
                self.server_info = response.result.get("serverInfo", {})
                capabilities = response.result.get("capabilities", {})
                self.capabilities = list(capabilities.keys())
                
                # Send initialized notification
                initialized_notification = MCPRequest(
                    id=self.generate_request_id(),
                    method="initialized",
                    params={}
                )
                await self.send_request(initialized_notification)
                
                self.initialized = True
                logger.info(f"Successfully initialized MCP server: {self.config.name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error initializing {self.config.name}: {e}")
            return False
    
    async def list_tools(self) -> List[MCPTool]:
        """List available tools from the MCP server."""
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
                    input_schema = tool_data.get("inputSchema", {})
                    tool = MCPTool(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        inputSchema=input_schema
                    )
                    tools.append(tool)
                    
                    # Log schema extraction for debugging
                    logger.debug(f"Extracted tool '{tool_data['name']}' from {self.config.name} with schema: {input_schema}")
                    
                    # Log if schema is empty
                    if not input_schema or input_schema == {}:
                        logger.warning(f"Tool '{tool_data['name']}' from {self.config.name} has empty schema! Raw tool data: {tool_data}")
                
                self.tools = tools
                logger.info(f"Extracted {len(tools)} tools from {self.config.name}")
                return tools
            
            return []
            
        except Exception as e:
            logger.error(f"Error listing tools from {self.config.name}: {e}")
            return []
    
    async def list_resources(self) -> List[MCPResource]:
        """List available resources from the MCP server."""
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
                return resources
            
            return []
            
        except Exception as e:
            logger.error(f"Error listing resources from {self.config.name}: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self.initialized:
            raise RuntimeError(f"MCP server {self.config.name} not initialized")
        
        try:
            # Determine timeout based on tool type
            timeout = self._get_tool_timeout(tool_name)
            
            request = MCPRequest(
                id=self.generate_request_id(),
                method="tools/call",
                params={
                    "name": tool_name,
                    "arguments": arguments
                }
            )
            
            response = await self.send_request(request, timeout=timeout)
            
            if response.error:
                raise RuntimeError(f"Tool call failed: {response.error}")
            
            return response.result or {}
            
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {self.config.name}: {e}")
            raise
    
    def _get_tool_timeout(self, tool_name: str) -> float:
        """Get appropriate timeout for tool based on its type."""
        # Network-based tools that need more time
        network_tools = {
            'brave_web_search', 'web_search', 'search', 'fetch', 'crawl', 
            'scrape', 'api_call', 'http_request', 'download'
        }
        
        # AI/LLM tools that need more time
        ai_tools = {
            'generate', 'completion', 'embedding', 'analyze', 'summarize'
        }
        
        # Check if tool name contains network-related keywords
        tool_lower = tool_name.lower()
        
        if any(keyword in tool_lower for keyword in network_tools):
            return 120.0  # 2 minutes for network tools
        elif any(keyword in tool_lower for keyword in ai_tools):
            return 90.0   # 1.5 minutes for AI tools  
        else:
            return 60.0   # 1 minute default
    
    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource from the MCP server."""
        if not self.initialized:
            raise RuntimeError(f"MCP server {self.config.name} not initialized")
        
        try:
            request = MCPRequest(
                id=self.generate_request_id(),
                method="resources/read",
                params={
                    "uri": uri
                }
            )
            
            response = await self.send_request(request)
            
            if response.error:
                raise RuntimeError(f"Resource read failed: {response.error}")
            
            return response.result or {}
            
        except Exception as e:
            logger.error(f"Error reading resource {uri} from {self.config.name}: {e}")
            raise
    
    async def stop(self):
        """Stop the MCP server process."""
        try:
            # Cancel tasks
            if self.stdout_task and not self.stdout_task.done():
                self.stdout_task.cancel()
            if self.stderr_task and not self.stderr_task.done():
                self.stderr_task.cancel()
            
            # Terminate process
            if self.process and self.process.poll() is None:
                self.process.terminate()
                
                # Wait for process to terminate
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
            
            logger.info(f"MCP server {self.config.name} stopped")
            
        except Exception as e:
            logger.error(f"Error stopping MCP server {self.config.name}: {e}")


class MCPProcessManager:
    """Manages MCP server processes."""
    
    def __init__(self):
        self.processes: Dict[str, MCPProcess] = {}
        self.cleanup_tasks: List[asyncio.Task] = []
    
    def _translate_command(self, command: str, args: List[str]) -> Tuple[str, List[str]]:
        """Translate Windows commands to Linux equivalents when running in Docker."""
        # Check if we're running in a Docker container
        is_docker = os.path.exists('/.dockerenv') or os.path.exists('/proc/1/cgroup')
        
        if not is_docker:
            return command, args
        
        # Translate common Windows commands
        if command == "cmd" and args and args[0] == "/c":
            # cmd /c npx ... -> npx ...
            if len(args) > 1:
                return args[1], args[2:]
            return "sh", ["-c", " ".join(args[1:])]
        
        elif command == "powershell" or command == "pwsh":
            # powershell -Command ... -> sh -c ...
            if "-Command" in args:
                cmd_idx = args.index("-Command")
                if cmd_idx + 1 < len(args):
                    return "sh", ["-c", args[cmd_idx + 1]]
            return "sh", ["-c", " ".join(args)]
        
        elif command.endswith(".exe"):
            # Remove .exe extension
            command = command[:-4]
        
        # For npx commands, ensure they work in Docker
        if command == "npx":
            # Add --yes flag to avoid prompts
            new_args = ["--yes"] + args
            return command, new_args
        
        # For Docker commands, update host references
        if command == "docker":
            # Replace host.docker.internal with host.docker.internal for Docker-in-Docker
            updated_args = []
            for arg in args:
                if isinstance(arg, str):
                    # Replace localhost with host.docker.internal for container communication
                    arg = arg.replace("localhost:", "host.docker.internal:")
                    # Keep host.docker.internal as is
                updated_args.append(arg)
            return command, updated_args
        
        return command, args
    
    async def start_server(self, config: MCPServerConfig) -> Optional[MCPServer]:
        """Start an MCP server process."""
        if config.name in self.processes:
            await self.stop_server(config.name)
        
        try:
            # Validate command exists
            if not hasattr(config, 'command') or not config.command:
                logger.warning(f"Server {config.name} has no command specified")
                return None
            
            # Prepare environment
            env = os.environ.copy()
            if hasattr(config, 'env') and config.env:
                env.update(config.env)
            
            # Add Docker socket path for Docker-in-Docker
            is_docker = os.path.exists('/.dockerenv') or os.path.exists('/proc/1/cgroup')
            if is_docker:
                env['DOCKER_HOST'] = 'unix:///var/run/docker.sock'
            
            # Translate command for Docker compatibility
            translated_command, translated_args = self._translate_command(
                config.command, config.args or []
            )
            command_parts = [translated_command] + translated_args
            
            # On Windows (non-Docker), try to resolve command path
            if os.name == 'nt' and not (os.path.exists('/.dockerenv') or os.path.exists('/proc/1/cgroup')):
                # Try to find the command in PATH or use full path
                import shutil
                resolved_command = shutil.which(translated_command)
                if resolved_command:
                    command_parts[0] = resolved_command
                else:
                    # Log warning but try anyway
                    logger.warning(f"Command '{translated_command}' not found in PATH for server {config.name}")
            
            logger.info(f"Starting MCP server {config.name} with command: {' '.join(command_parts)}")
            
            # Start process with explicit UTF-8 encoding (fixes Windows charmap issues)
            process = subprocess.Popen(
                command_parts,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',  # Explicit UTF-8 encoding for cross-platform compatibility
                errors='replace',  # Replace invalid characters instead of crashing
                env=env,
                bufsize=1,  # Line buffered
                universal_newlines=True,  # Ensure text mode
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Create MCP process wrapper
            mcp_process = MCPProcess(config, process)
            self.processes[config.name] = mcp_process
            
            # Start communication
            await mcp_process.start_communication()
            
            # Initialize the server
            initialized = await mcp_process.initialize()
            
            if not initialized:
                await self.stop_server(config.name)
                return None
            
            # Discover capabilities
            tools = await mcp_process.list_tools()
            resources = await mcp_process.list_resources()
            
            # Create MCPServer object
            server = MCPServer(
                name=config.name,
                url=f"process://{config.name}",  # Use process:// scheme for stdio servers
                status=MCPServerStatus.CONNECTED,
                capabilities=mcp_process.capabilities,
                tools=tools,
                resources=resources,
                last_ping=datetime.utcnow(),
                last_error=None,
                retry_count=0,
                max_retries=config.max_retries,
                source=config.source
            )
            
            logger.info(f"Started MCP server: {config.name}")
            return server
            
        except Exception as e:
            logger.error(f"Error starting MCP server {config.name}: {e}")
            await self.stop_server(config.name)
            return None
    
    async def stop_server(self, server_name: str):
        """Stop an MCP server process."""
        if server_name in self.processes:
            mcp_process = self.processes.pop(server_name)
            await mcp_process.stop()
    
    async def stop_all_servers(self):
        """Stop all MCP server processes."""
        tasks = []
        for server_name in list(self.processes.keys()):
            tasks.append(self.stop_server(server_name))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_process(self, server_name: str) -> Optional[MCPProcess]:
        """Get an MCP process by name."""
        return self.processes.get(server_name)
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on a specific MCP server."""
        process = self.get_process(server_name)
        if not process:
            raise RuntimeError(f"MCP server {server_name} not found")
        
        return await process.call_tool(tool_name, arguments)
    
    async def read_resource(self, server_name: str, uri: str) -> Dict[str, Any]:
        """Read a resource from a specific MCP server."""
        process = self.get_process(server_name)
        if not process:
            raise RuntimeError(f"MCP server {server_name} not found")
        
        return await process.read_resource(uri)
    
    def is_running(self, server_name: str) -> bool:
        """Check if an MCP server is running."""
        process = self.get_process(server_name)
        return process is not None and process.process.poll() is None
    
    async def health_check(self, server_name: str) -> bool:
        """Perform health check on an MCP server."""
        process = self.get_process(server_name)
        if not process:
            return False
        
        if process.process.poll() is not None:
            return False
        
        try:
            # Try to list tools as a health check
            await process.list_tools()
            return True
        except Exception:
            return False 