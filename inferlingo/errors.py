"""Public InferLingo exception types."""


class InferLingoError(ValueError):
    """Base class for deterministic InferLingo failures."""


class UnsafeNegationError(InferLingoError):
    """Raised when a negated goal is evaluated before all its variables are bound."""


class RuleSafetyError(InferLingoError):
    """Raised for a rule or fact that violates strict range-restriction rules."""
