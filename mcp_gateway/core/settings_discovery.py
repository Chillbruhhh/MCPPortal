"""
MCP Settings Discovery.

This module discovers MCP server configurations from various IDEs
and development environments to enable seamless integration.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..config.settings import MCPServerConfig

logger = logging.getLogger(__name__)


class IDESettingsDiscovery:
    """Discovers MCP settings from various IDEs and environments."""

    def __init__(self):
        """Initialize settings discovery."""
        self.discovered_servers: Dict[str, MCPServerConfig] = {}
        self.ide_configs: Dict[str, Dict] = {}

    def discover_all_settings(self) -> List[MCPServerConfig]:
        """
        Discover MCP settings from all supported IDEs.

        Returns:
            List of discovered MCP server configurations
        """
        discovered = []
        
        # Discovery methods for different IDEs
        discovery_methods = [
            self._discover_cursor_settings,
            self._discover_windsurf_settings,
            self._discover_vscode_settings,
            self._discover_claude_desktop_settings,
            self._discover_continue_settings,
            self._discover_aider_settings,
            self._discover_codeium_settings,
        ]

        for method in discovery_methods:
            try:
                configs = method()
                if configs:
                    discovered.extend(configs)
                    logger.info(f"Discovered {len(configs)} MCP servers from {method.__name__}")
            except Exception as e:
                logger.warning(f"Failed to discover settings from {method.__name__}: {e}")

        # Deduplicate servers by name
        unique_servers = {}
        for config in discovered:
            if config.name not in unique_servers:
                unique_servers[config.name] = config
            else:
                logger.debug(f"Duplicate server '{config.name}' found, keeping first instance")

        result = list(unique_servers.values())
        logger.info(f"Total discovered MCP servers: {len(result)}")
        return result

    def _discover_cursor_settings(self) -> List[MCPServerConfig]:
        """Discover MCP settings from Cursor IDE."""
        configs = []
        
        # Common Cursor config locations
        cursor_paths = [
            Path.home() / ".cursor" / "mcp.json",  # Primary Cursor MCP config
            Path.home() / ".cursor" / "config" / "mcp.json",
            Path.home() / "Library" / "Application Support" / "Cursor" / "mcp.json",  # macOS
            Path.home() / "AppData" / "Roaming" / "Cursor" / "mcp.json",  # Windows
            # Legacy paths for backward compatibility
            Path.home() / ".cursor" / "mcp_servers.json",
            Path.home() / ".cursor" / "config" / "mcp_servers.json",
            # Docker mounted paths
            Path("/root/.cursor/mcp.json"),
            Path("/root/.cursor/config/mcp.json"),
            Path("/root/.cursor/mcp_servers.json"),
            Path("/root/.cursor/config/mcp_servers.json"),
        ]

        for config_path in cursor_paths:
            if config_path.exists():
                try:
                    configs.extend(self._parse_cursor_config(config_path))
                    logger.info(f"Found Cursor MCP config at: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to parse Cursor config at {config_path}: {e}")

        return configs

    def _discover_windsurf_settings(self) -> List[MCPServerConfig]:
        """Discover MCP settings from Windsurf IDE."""
        configs = []
        
        # Common Windsurf config locations
        windsurf_paths = [
            Path.home() / ".windsurf" / "mcp_servers.json",
            Path.home() / ".windsurf" / "config" / "mcp_servers.json",
            Path.home() / "Library" / "Application Support" / "Windsurf" / "mcp_servers.json",  # macOS
            Path.home() / "AppData" / "Roaming" / "Windsurf" / "mcp_servers.json",  # Windows
        ]

        for config_path in windsurf_paths:
            if config_path.exists():
                try:
                    configs.extend(self._parse_windsurf_config(config_path))
                    logger.info(f"Found Windsurf MCP config at: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to parse Windsurf config at {config_path}: {e}")

        return configs

    def _discover_vscode_settings(self) -> List[MCPServerConfig]:
        """Discover MCP settings from VS Code."""
        configs = []
        
        # VS Code settings.json locations
        vscode_paths = [
            Path.home() / ".vscode" / "settings.json",
            Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json",  # macOS
            Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json",  # Windows
            # Docker mounted paths
            Path("/root/.vscode/settings.json"),
        ]

        for config_path in vscode_paths:
            if config_path.exists():
                try:
                    configs.extend(self._parse_vscode_settings(config_path))
                    logger.info(f"Found VS Code MCP config at: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to parse VS Code config at {config_path}: {e}")

        return configs

    def _discover_claude_desktop_settings(self) -> List[MCPServerConfig]:
        """Discover MCP settings from Claude Desktop."""
        configs = []
        
        # Claude Desktop config locations
        claude_paths = [
            Path.home() / ".claude" / "claude_desktop_config.json",
            Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
            Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",  # Windows
            # Docker mounted paths
            Path("/root/.claude/claude_desktop_config.json"),
        ]

        for config_path in claude_paths:
            if config_path.exists():
                try:
                    configs.extend(self._parse_claude_desktop_config(config_path))
                    logger.info(f"Found Claude Desktop MCP config at: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to parse Claude Desktop config at {config_path}: {e}")

        return configs

    def _discover_continue_settings(self) -> List[MCPServerConfig]:
        """Discover MCP settings from Continue.dev."""
        configs = []
        
        # Continue.dev config locations
        continue_paths = [
            Path.home() / ".continue" / "config.json",
            Path.home() / ".continue" / "config" / "config.json",
        ]

        for config_path in continue_paths:
            if config_path.exists():
                try:
                    configs.extend(self._parse_continue_config(config_path))
                    logger.info(f"Found Continue.dev MCP config at: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to parse Continue.dev config at {config_path}: {e}")

        return configs

    def _discover_aider_settings(self) -> List[MCPServerConfig]:
        """Discover MCP settings from Aider."""
        configs = []
        
        # Aider config locations
        aider_paths = [
            Path.home() / ".aider" / "aider.conf.yml",
            Path.home() / ".aider" / "config.yml",
        ]

        for config_path in aider_paths:
            if config_path.exists():
                try:
                    configs.extend(self._parse_aider_config(config_path))
                    logger.info(f"Found Aider MCP config at: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to parse Aider config at {config_path}: {e}")

        return configs

    def _discover_codeium_settings(self) -> List[MCPServerConfig]:
        """Discover MCP settings from Codeium."""
        configs = []
        
        # Codeium config locations
        codeium_paths = [
            Path.home() / ".codeium" / "config.json",
            Path.home() / "Library" / "Application Support" / "Codeium" / "config.json",  # macOS
            Path.home() / "AppData" / "Roaming" / "Codeium" / "config.json",  # Windows
        ]

        for config_path in codeium_paths:
            if config_path.exists():
                try:
                    configs.extend(self._parse_codeium_config(config_path))
                    logger.info(f"Found Codeium MCP config at: {config_path}")
                except Exception as e:
                    logger.warning(f"Failed to parse Codeium config at {config_path}: {e}")

        return configs

    def _parse_cursor_config(self, config_path: Path) -> List[MCPServerConfig]:
        """Parse Cursor MCP configuration."""
        with open(config_path, 'r') as f:
            data = json.load(f)

        configs = []
        mcp_servers = data.get("mcpServers", {})

        for server_name, server_config in mcp_servers.items():
            try:
                # Convert from Cursor format to our format
                configs.append(self._convert_cursor_server_config(server_name, server_config))
            except Exception as e:
                logger.warning(f"Failed to parse Cursor server '{server_name}': {e}")

        return configs

    def _parse_windsurf_config(self, config_path: Path) -> List[MCPServerConfig]:
        """Parse Windsurf MCP configuration."""
        with open(config_path, 'r') as f:
            data = json.load(f)

        configs = []
        mcp_servers = data.get("mcpServers", {})

        for server_name, server_config in mcp_servers.items():
            try:
                configs.append(self._convert_windsurf_server_config(server_name, server_config))
            except Exception as e:
                logger.warning(f"Failed to parse Windsurf server '{server_name}': {e}")

        return configs

    def _parse_vscode_settings(self, config_path: Path) -> List[MCPServerConfig]:
        """Parse VS Code settings.json for MCP configuration."""
        with open(config_path, 'r') as f:
            data = json.load(f)

        configs = []
        # Look for MCP-related settings in VS Code
        mcp_settings = data.get("mcp", {}).get("servers", {})

        for server_name, server_config in mcp_settings.items():
            try:
                configs.append(self._convert_vscode_server_config(server_name, server_config))
            except Exception as e:
                logger.warning(f"Failed to parse VS Code server '{server_name}': {e}")

        return configs

    def _parse_claude_desktop_config(self, config_path: Path) -> List[MCPServerConfig]:
        """Parse Claude Desktop configuration."""
        with open(config_path, 'r') as f:
            data = json.load(f)

        configs = []
        mcp_servers = data.get("mcpServers", {})

        for server_name, server_config in mcp_servers.items():
            try:
                configs.append(self._convert_claude_desktop_server_config(server_name, server_config))
            except Exception as e:
                logger.warning(f"Failed to parse Claude Desktop server '{server_name}': {e}")

        return configs

    def _parse_continue_config(self, config_path: Path) -> List[MCPServerConfig]:
        """Parse Continue.dev configuration."""
        with open(config_path, 'r') as f:
            data = json.load(f)

        configs = []
        mcp_servers = data.get("mcp", {}).get("servers", {})

        for server_name, server_config in mcp_servers.items():
            try:
                configs.append(self._convert_continue_server_config(server_name, server_config))
            except Exception as e:
                logger.warning(f"Failed to parse Continue.dev server '{server_name}': {e}")

        return configs

    def _parse_aider_config(self, config_path: Path) -> List[MCPServerConfig]:
        """Parse Aider configuration."""
        import yaml
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        configs = []
        mcp_servers = data.get("mcp", {}).get("servers", {})

        for server_name, server_config in mcp_servers.items():
            try:
                configs.append(self._convert_aider_server_config(server_name, server_config))
            except Exception as e:
                logger.warning(f"Failed to parse Aider server '{server_name}': {e}")

        return configs

    def _parse_codeium_config(self, config_path: Path) -> List[MCPServerConfig]:
        """Parse Codeium configuration."""
        with open(config_path, 'r') as f:
            data = json.load(f)

        configs = []
        mcp_servers = data.get("mcp", {}).get("servers", {})

        for server_name, server_config in mcp_servers.items():
            try:
                configs.append(self._convert_codeium_server_config(server_name, server_config))
            except Exception as e:
                logger.warning(f"Failed to parse Codeium server '{server_name}': {e}")

        return configs

    def _convert_cursor_server_config(self, name: str, config: Dict) -> MCPServerConfig:
        """Convert Cursor server config to our format."""
        # Check if this is a command-based server
        if "command" in config:
            return MCPServerConfig(
                name=name,
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Cursor IDE"
            )
        # Check if this is a URL-based server
        elif "url" in config:
            return MCPServerConfig(
                name=name,
                url=config["url"],
                transport=config.get("transport", "http"),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Cursor IDE"
            )
        else:
            # Fallback to default URL format
            return MCPServerConfig(
                name=name,
                url=f"http://localhost:3000/{name}",
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Cursor IDE"
            )

    def _convert_windsurf_server_config(self, name: str, config: Dict) -> MCPServerConfig:
        """Convert Windsurf server config to our format."""
        if "command" in config:
            return MCPServerConfig(
                name=name,
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Windsurf IDE"
            )
        elif "url" in config:
            return MCPServerConfig(
                name=name,
                url=config["url"],
                transport=config.get("transport", "http"),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Windsurf IDE"
            )
        else:
            return MCPServerConfig(
                name=name,
                url=f"http://localhost:3000/{name}",
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Windsurf IDE"
            )

    def _convert_vscode_server_config(self, name: str, config: Dict) -> MCPServerConfig:
        """Convert VS Code server config to our format."""
        if "command" in config:
            return MCPServerConfig(
                name=name,
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="VS Code"
            )
        elif "url" in config:
            return MCPServerConfig(
                name=name,
                url=config["url"],
                transport=config.get("transport", "http"),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="VS Code"
            )
        else:
            return MCPServerConfig(
                name=name,
                url=f"http://localhost:3000/{name}",
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="VS Code"
            )

    def _convert_claude_desktop_server_config(self, name: str, config: Dict) -> MCPServerConfig:
        """Convert Claude Desktop server config to our format."""
        if "command" in config:
            return MCPServerConfig(
                name=name,
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Claude Desktop"
            )
        elif "url" in config:
            return MCPServerConfig(
                name=name,
                url=config["url"],
                transport=config.get("transport", "http"),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Claude Desktop"
            )
        else:
            return MCPServerConfig(
                name=name,
                url=f"http://localhost:3000/{name}",
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Claude Desktop"
            )

    def _convert_continue_server_config(self, name: str, config: Dict) -> MCPServerConfig:
        """Convert Continue.dev server config to our format."""
        # Check if this is a command-based server
        if "command" in config:
            return MCPServerConfig(
                name=name,
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Continue.dev"
            )
        else:
            url = config.get("url", f"http://localhost:3000/{name}")
            return MCPServerConfig(
                name=name,
                url=url,
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Continue.dev"
            )

    def _convert_aider_server_config(self, name: str, config: Dict) -> MCPServerConfig:
        """Convert Aider server config to our format."""
        # Check if this is a command-based server
        if "command" in config:
            return MCPServerConfig(
                name=name,
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Aider"
            )
        else:
            url = config.get("url", f"http://localhost:3000/{name}")
            return MCPServerConfig(
                name=name,
                url=url,
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Aider"
            )

    def _convert_codeium_server_config(self, name: str, config: Dict) -> MCPServerConfig:
        """Convert Codeium server config to our format."""
        # Check if this is a command-based server
        if "command" in config:
            return MCPServerConfig(
                name=name,
                command=config["command"],
                args=config.get("args", []),
                env=config.get("env", {}),
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Codeium"
            )
        else:
            url = config.get("url", f"http://localhost:3000/{name}")
            return MCPServerConfig(
                name=name,
                url=url,
                enabled=config.get("enabled", True),
                timeout=config.get("timeout", 30),
                max_retries=config.get("max_retries", 3),
                source="Codeium"
            )

    def _command_to_url(self, command: str, args: List[str]) -> str:
        """
        Convert command/args format to URL format.
        
        This is a simplified conversion. In reality, you'd need to:
        1. Start the MCP server process
        2. Discover its listening port
        3. Create the appropriate URL
        
        For now, we'll use default ports based on common patterns.
        """
        # Common MCP server port assignments
        port_mappings = {
            "filesystem": 3001,
            "database": 3002,
            "git": 3003,
            "web-search": 3004,
            "crawl4ai": 3005,
            "cursor-ide": 3006,
            "default": 3000
        }

        # Extract server type from command/args
        server_type = "default"
        if args:
            for arg in args:
                if any(keyword in arg.lower() for keyword in ["filesystem", "database", "git", "web", "crawl", "cursor"]):
                    for keyword in ["filesystem", "database", "git", "web", "crawl", "cursor"]:
                        if keyword in arg.lower():
                            server_type = keyword
                            break
                    break

        port = port_mappings.get(server_type, port_mappings["default"])
        return f"http://localhost:{port}"

    def get_discovery_summary(self) -> Dict[str, any]:
        """Get a summary of discovery results."""
        return {
            "total_servers": len(self.discovered_servers),
            "ide_configs": list(self.ide_configs.keys()),
            "servers": list(self.discovered_servers.keys())
        }


# Global instance
settings_discovery = IDESettingsDiscovery()


def discover_mcp_settings() -> List[MCPServerConfig]:
    """
    Discover MCP settings from all supported IDEs.
    
    Returns:
        List of discovered MCP server configurations
    """
    return settings_discovery.discover_all_settings() 