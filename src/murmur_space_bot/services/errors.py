class ServiceError(Exception):
    """A user-facing application error."""


class UserNotFoundError(ServiceError):
    pass


class InsufficientTierError(ServiceError):
    pass


class TodoNotFoundError(ServiceError):
    pass


class InvalidTodoStateError(ServiceError):
    pass

