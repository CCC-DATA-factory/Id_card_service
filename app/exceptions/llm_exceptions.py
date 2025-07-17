class NoResponseError(Exception):
    """Raised when LLM returns no parsable content."""
    pass

class ValidationRetryError(Exception):
    """Raised after exceeding validation retries for LLM response."""
    pass
