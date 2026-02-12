"""Structured logging configuration for the ETL pipeline."""

import logging
import sys
from typing import Optional

# Try to import structlog, fall back to standard logging
try:
    import structlog

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "structured",
    log_file: Optional[str] = None,
) -> None:
    """
    Configure logging for the ETL pipeline.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Format type ("structured" or "simple")
        log_file: Optional file path for logging output
    """
    # Configure standard library logging
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    log_format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        format=log_format_str,
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
    )

    # Configure structlog if available
    if HAS_STRUCTLOG and log_format == "structured":
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


def get_logger(name: str):
    """Get a configured logger instance."""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)
