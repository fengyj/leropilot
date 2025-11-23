import structlog


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    from leropilot.config import get_config

    config = get_config()
    log_dir = config.paths.logs_dir
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    # Map string level to integer
    level_map = {
        "INFO": 20,
        "DEBUG": 10,
        "TRACE": 5,
    }
    log_level = level_map.get(config.advanced.log_level, 20)

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,  # Disable cache to allow level updates
    )

    return structlog.get_logger(name)
