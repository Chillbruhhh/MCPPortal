"""
Input Validation Utilities.

This module provides utilities for validating requests
and data throughout the MCP Gateway application.
"""

import re
from typing import Any, Dict, List
from urllib.parse import urlparse


def validate_server_name(name: str) -> bool:
    """
    Validate server name format.

    Args:
        name: Server name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or not isinstance(name, str):
        return False

    # Allow alphanumeric, hyphens, underscores
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, name)) and len(name) <= 50


def validate_server_url(url: str) -> bool:
    """
    Validate server URL format.

    Args:
        url: URL to validate

    Returns:
        True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
        return parsed.scheme in ['http', 'https', 'ws', 'wss'] and bool(parsed.netloc)
    except Exception:
        return False


def validate_tool_name(name: str) -> bool:
    """
    Validate tool name format.

    Args:
        name: Tool name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or not isinstance(name, str):
        return False

    # Allow alphanumeric, dots, hyphens, underscores
    pattern = r'^[a-zA-Z0-9._-]+$'
    return bool(re.match(pattern, name)) and len(name) <= 100


def validate_resource_uri(uri: str) -> bool:
    """
    Validate resource URI format.

    Args:
        uri: URI to validate

    Returns:
        True if valid, False otherwise
    """
    if not uri or not isinstance(uri, str):
        return False

    # Basic URI validation - allow most characters
    return len(uri) <= 500 and not any(char in uri for char in ['\n', '\r', '\t'])


def validate_json_parameters(params: Any) -> bool:
    """
    Validate JSON parameters.

    Args:
        params: Parameters to validate

    Returns:
        True if valid, False otherwise
    """
    if params is None:
        return True

    # Must be a dictionary
    if not isinstance(params, dict):
        return False

    # Check for reasonable size
    return len(str(params)) <= 10000  # 10KB limit


def validate_timeout(timeout: Any) -> bool:
    """
    Validate timeout value.

    Args:
        timeout: Timeout to validate

    Returns:
        True if valid, False otherwise
    """
    if timeout is None:
        return True

    if not isinstance(timeout, (int, float)):
        return False

    # Reasonable timeout range: 1 second to 5 minutes
    return 1 <= timeout <= 300


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize string input.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return ""

    # Remove control characters except newlines and tabs
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized.strip()


def validate_search_query(query: str) -> bool:
    """
    Validate search query.

    Args:
        query: Search query to validate

    Returns:
        True if valid, False otherwise
    """
    if not query or not isinstance(query, str):
        return True  # Empty queries are allowed

    # Reasonable length limit
    return len(query.strip()) <= 200


def validate_log_level(level: str) -> bool:
    """
    Validate log level.

    Args:
        level: Log level to validate

    Returns:
        True if valid, False otherwise
    """
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    return level.upper() in valid_levels


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key format.

    Args:
        api_key: API key to validate

    Returns:
        True if valid, False otherwise
    """
    if not api_key or not isinstance(api_key, str):
        return False

    # Basic API key validation - should be reasonable length
    return 16 <= len(api_key) <= 128


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field: str = None):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field that failed validation
        """
        self.message = message
        self.field = field
        super().__init__(message)


def validate_server_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate server configuration.

    Args:
        config: Server configuration to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Required fields
    if 'name' not in config:
        errors.append("Server name is required")
    elif not validate_server_name(config['name']):
        errors.append("Invalid server name format")

    if 'url' not in config:
        errors.append("Server URL is required")
    elif not validate_server_url(config['url']):
        errors.append("Invalid server URL format")

    # Optional fields
    if 'timeout' in config and not validate_timeout(config['timeout']):
        errors.append("Invalid timeout value")

    if 'max_retries' in config:
        max_retries = config['max_retries']
        if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 10:
            errors.append("Max retries must be between 0 and 10")

    return errors


def validate_tool_execution_request(request: Dict[str, Any]) -> List[str]:
    """
    Validate tool execution request.

    Args:
        request: Request to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if 'tool_name' not in request:
        errors.append("Tool name is required")
    elif not validate_tool_name(request['tool_name']):
        errors.append("Invalid tool name format")

    if 'parameters' in request and not validate_json_parameters(request['parameters']):
        errors.append("Invalid parameters format")

    if 'timeout' in request and not validate_timeout(request['timeout']):
        errors.append("Invalid timeout value")

    return errors


def validate_resource_request(request: Dict[str, Any]) -> List[str]:
    """
    Validate resource access request.

    Args:
        request: Request to validate

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if 'resource_uri' not in request:
        errors.append("Resource URI is required")
    elif not validate_resource_uri(request['resource_uri']):
        errors.append("Invalid resource URI format")

    if 'parameters' in request and not validate_json_parameters(request['parameters']):
        errors.append("Invalid parameters format")

    return errors
