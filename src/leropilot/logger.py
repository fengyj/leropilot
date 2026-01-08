import logging
import logging.handlers
from collections.abc import Callable, Mapping, MutableMapping
from pathlib import Path
from typing import Any, cast

import structlog


class FileWriterProcessor:
    """Processor that writes structured logs to file with rotation support."""

    def __init__(
        self, log_file_path: Path | None = None, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5
    ) -> None:
        """Initialize file writer with rotation.

        Args:
            log_file_path: Path to the log file
            max_bytes: Maximum size of log file before rotation (default: 10MB)
            backup_count: Number of backup files to keep (default: 5)
        """
        self.log_file_path = log_file_path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.handler = None

        if log_file_path:
            # Create rotating file handler
            self.handler = logging.handlers.RotatingFileHandler(
                filename=str(log_file_path), maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
            )
            # Set formatter to write plain text (no extra formatting)
            self.handler.setFormatter(logging.Formatter("%(message)s"))

    def __call__(self, logger: logging.Logger, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        """Write the log event to file with rotation."""
        if self.handler:
            # Create a JSON line for the file
            import json

            try:
                json_line = json.dumps(event_dict, default=str, ensure_ascii=False)
                # Create a log record and emit it directly to the handler
                record = logging.LogRecord(
                    name="leropilot", level=logging.INFO, pathname="", lineno=0, msg=json_line, args=(), exc_info=None
                )
                self.handler.emit(record)
            except Exception:
                # If JSON serialization fails, write a simple message
                record = logging.LogRecord(
                    name="leropilot",
                    level=logging.ERROR,
                    pathname="",
                    lineno=0,
                    msg=str(event_dict),
                    args=(),
                    exc_info=None,
                )
                self.handler.emit(record)

        return event_dict

    def __del__(self) -> None:
        """Close the handler when the processor is destroyed."""
        if self.handler:
            self.handler.close()


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    # Use a global variable to cache the configuration
    if not hasattr(get_logger, "_configured"):
        try:
            from leropilot.services.config import get_config
            config = get_config()
        except (ImportError, AttributeError):
            # Fallback during circular imports at bootstrap
            return cast(structlog.BoundLogger, structlog.get_logger(name))

        log_dir = config.paths.logs_dir
        log_file_path = None

        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            # Use a fixed log file name
            log_file_path = log_dir / "leropilot.log"

        # Map string level to integer
        level_map = {
            "INFO": 20,
            "DEBUG": 10,
            "TRACE": 5,
        }
        log_level = level_map.get(config.advanced.log_level, 20)

        # Create processors
        ProcessorCallable = Callable[
            [Any, str, MutableMapping[str, Any]],
            Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...],
        ]

        processors: list[ProcessorCallable] = [
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
        ]

        # Add file writer processor if log file is configured
        if log_file_path:
            max_bytes = config.advanced.log_max_size_mb * 1024 * 1024  # Convert MB to bytes
            backup_count = config.advanced.log_backup_count
            processors.append(cast(ProcessorCallable, FileWriterProcessor(log_file_path, max_bytes, backup_count)))

        # Add console output (JSON format for consistency)
        processors.append(structlog.processors.JSONRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,  # Disable cache to allow level updates
        )

        # Mark as configured
        get_logger._configured = True  # type: ignore[attr-defined]

    return cast(structlog.BoundLogger, structlog.get_logger(name))
