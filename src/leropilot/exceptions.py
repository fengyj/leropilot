"""Centralized exception hierarchy for LeRoPilot.

Supports i18n keys for user-facing messages and English for internal logging.
"""



class AppBaseError(Exception):
    """Base exception for all application-specific errors."""

    def __init__(
        self,
        i18n_key: str,
        status_code: int = 500,
        retriable: bool = False,
        **params: object,
    ) -> None:
        """
        Initialize the error.

        Args:
            i18n_key: Dot-path in i18n.json (e.g., 'hardware.robot_device.not_found')
            status_code: Recommended HTTP status code
            retriable: Whether the operation can be retried
            **params: Parameters for string formatting in translations
        """
        super().__init__(i18n_key)
        self.i18n_key = i18n_key
        self.status_code = status_code
        self.retriable = retriable
        self.params = params

    def __str__(self) -> str:
        """Returns the English version of the error message for logging."""
        try:
            # Lazy import to avoid circular dependencies
            from leropilot.services.i18n import get_i18n_service

            i18n = get_i18n_service()

            # Use dot-path as default if translation fails
            translated = i18n.translate(self.i18n_key, lang="en", **self.params)
            return str(translated) if translated else self.i18n_key
        except Exception:
            # Fallback if i18n service is not available or fails
            params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
            return f"[{self.i18n_key}] {params_str} (retriable: {self.retriable})"


class ResourceNotFoundError(AppBaseError):
    """Raised when a requested resource (robot, environment, etc.) is not found."""

    def __init__(self, i18n_key: str, **params: object) -> None:
        super().__init__(i18n_key, status_code=404, **params)


class ResourceConflictError(AppBaseError):
    """Raised when an operation conflicts with the current state (e.g., duplicate ID)."""

    def __init__(self, i18n_key: str, **params: object) -> None:
        super().__init__(i18n_key, status_code=409, **params)


class ValidationError(AppBaseError):
    """Raised when input validation fails."""

    def __init__(self, i18n_key: str, **params: object) -> None:
        super().__init__(i18n_key, status_code=400, **params)


class OperationalError(AppBaseError):
    """Raised when an operational failure occurs (hardware connection, git command, etc.)."""

    def __init__(self, i18n_key: str, retriable: bool = False, **params: object) -> None:
        super().__init__(i18n_key, status_code=500, retriable=retriable, **params)


