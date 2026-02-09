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
        data: object | None = None,
        **params: object,
    ) -> None:
        """
        Initialize the error.

        Args:
            i18n_key: Dot-path in i18n.json (e.g., 'hardware.robot_device.not_found')
            status_code: Recommended HTTP status code
            retriable: Whether the operation can be retried
            data: Optional structured data associated with the error
            **params: Parameters for string formatting in translations
        """
        super().__init__(i18n_key)
        self.i18n_key = i18n_key
        self.status_code = status_code
        self.retriable = retriable
        self.data = data
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

    def __init__(self, i18n_key: str, retriable: bool = False, data: object | None = None, **params: object) -> None:
        super().__init__(i18n_key, status_code=500, retriable=retriable, data=data, **params)


class MotorIdentificationError(AppBaseError):
    """Raised when motor identification fails or the model is unknown."""

    def __init__(
        self,
        i18n_key: str = "hardware.motor_device.identification_failed",
        retriable: bool = False,
        data: object | None = None,
        **params: object,
    ) -> None:
        # Identification errors are client/hardware level issues (400)
        super().__init__(i18n_key, status_code=400, retriable=retriable, data=data, **params)


def reraise_if_expected(exc: BaseException, expected: type | tuple[type, ...]) -> None:
    """Re-raise ``exc`` if it is an instance of any type in ``expected``.

    This helper is intended to be called inside an ``except Exception as e:`` block.
    It preserves the original traceback (when available) so test assertions and
    logs point to the original failure site.

    Args:
        exc: The caught exception instance (``e`` from ``except Exception as e``).
        expected: A type or tuple of exception types that should be re-raised.

    Usage:
        try:
            ...
        except Exception as e:
            reraise_if_expected(e, (SerialException, OperationalError))
            # if not re-raised, continue and maybe translate the error
    """
    if isinstance(exc, expected):
        tb = getattr(exc, "__traceback__", None)
        if tb is not None:
            # Re-raise preserving the original traceback
            raise exc.with_traceback(tb)
        # Fallback: re-raise without explicit traceback
        raise exc
