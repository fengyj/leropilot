import structlog
from pathlib import Path


def get_logger(name: str) -> structlog.BoundLogger:
    log_dir = Path.home() / ".leropilot" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger(name)
