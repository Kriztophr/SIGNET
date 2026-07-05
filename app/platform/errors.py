class DomainError(Exception):
    """Base for errors raised by services; translated to HTTP by the API layer."""


class NotFoundError(DomainError):
    """Entity does not exist or is outside the caller's tenant scope."""


class InvalidStateError(DomainError):
    """Operation is not valid for the entity's current state."""


class DomainValidationError(DomainError):
    """Input is structurally valid but violates a domain rule or contract."""
