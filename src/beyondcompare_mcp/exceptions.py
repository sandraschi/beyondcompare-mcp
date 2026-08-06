"""Exceptions for the Beyond Compare MCP server."""


class BeyondCompareError(Exception):
    """Base exception for all Beyond Compare MCP errors."""

    pass


class BeyondCompareNotInstalledError(BeyondCompareError):
    """Raised when Beyond Compare is not installed or not found."""

    def __init__(self, path: str | None = None):
        message = "Beyond Compare is not installed or not found in PATH"
        if path:
            message = f"Beyond Compare not found at: {path}"
        super().__init__(message)


class BeyondCompareCommandError(BeyondCompareError):
    """Raised when a Beyond Compare command fails."""

    def __init__(self, command: str, returncode: int, stderr: str | None = None):
        message = f"Command '{command}' failed with return code {returncode}"
        if stderr:
            message += f": {stderr.strip()}"
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stderr = stderr


class BeyondCompareTimeoutError(BeyondCompareError):
    """Raised when a Beyond Compare command times out."""

    def __init__(self, command: str, timeout: int):
        super().__init__(f"Command '{command}' timed out after {timeout} seconds")
        self.command = command
        self.timeout = timeout


class BeyondCompareScriptError(BeyondCompareError):
    """Raised when there's an error with a Beyond Compare script."""

    def __init__(self, script_path: str, error: str):
        super().__init__(f"Script error in {script_path}: {error}")
        self.script_path = script_path
        self.error = error


class BeyondCompareValidationError(BeyondCompareError):
    """Raised when input validation fails."""

    pass
