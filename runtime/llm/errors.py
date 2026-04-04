class LLMConfigurationError(RuntimeError):
    """Raised when required LLM configuration is missing."""


class LLMInvocationError(RuntimeError):
    """Raised when an LLM call fails or returns invalid output."""
