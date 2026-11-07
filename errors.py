class ServiceError(Exception):
    """Base class for failures the CLI and API should show to the user."""

class NotFound(ServiceError):
    pass

class InvalidRequest(ServiceError):
    pass

class ModelUnavailable(ServiceError):
    pass

class EmptyReply(ServiceError):
    pass