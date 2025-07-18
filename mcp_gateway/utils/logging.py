"""
Logging Configuration.

This module sets up logging for the MCP Gateway application.
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict


def setup_logging(log_level: str = "INFO", log_file: str = None) -> None:
    """
    Set up logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
    """

    # Create logs directory if using file logging
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Define logging configuration
    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s - %(name)s - %(message)s"
            },
            "json": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "simple",
                "stream": sys.stdout
            }
        },
        "loggers": {
            "mcp_gateway": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["console"]
        }
    }

    # Add file handler if log file specified
    if log_file:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "detailed",
            "filename": log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }

        # Add file handler to loggers
        config["loggers"]["mcp_gateway"]["handlers"].append("file")
        config["root"]["handlers"].append("file")

    # Apply configuration
    logging.config.dictConfig(config)

    # Set specific library log levels
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(f"mcp_gateway.{name}")


# Convenience function for getting module logger
def get_module_logger(module_file: str) -> logging.Logger:
    """
    Get logger for a module.

    Args:
        module_file: Module __file__ attribute

    Returns:
        Logger instance
    """
    module_name = Path(module_file).stem
    return get_logger(module_name)
