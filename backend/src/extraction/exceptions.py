class RetryableExtractionError(Exception):
    """Exception raised for transient provider errors that should be retried."""
    pass

class NonRetryableExtractionError(Exception):
    """Exception raised for fatal provider errors like malformed JSON, schema failure, auth error."""
    pass
