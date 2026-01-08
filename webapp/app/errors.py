from .config import *

class AppError(Exception):
    """Base class for all application errors."""
    log_level = "error"   # default

class NotFoundError(AppError):
    log_level = "info"    # or "warning"
    pass

class ValidationError(AppError):
    log_level = "warning"
    pass

class CriticalError(AppError):
    log_level = "critical"
    pass

def handle_exception(method, firstname, lastname, e: Exception):
    if isinstance(e, AppError):
        if (e.log_level == "info"):
            log(f"Failed to execute {method} for user {firstname} {lastname} with: {str(e)}.")
        else:
            log(f"Failed to execute {method} for user {firstname} {lastname} with exception: {str(e)}.")
    else:
        log("Unhandled exception")