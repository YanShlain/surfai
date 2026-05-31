from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of structural workflow validation."""

    ok: bool
    errors: list

    @classmethod
    def valid(cls) -> "ValidationResult":
        """Create a successful validation result with no errors."""
        return cls(ok=True, errors=[])

    @classmethod
    def invalid(cls, errors: list) -> "ValidationResult":
        """Create a failed validation result carrying one or more errors.

        Args:
            errors: WorkflowError instances describing validation failures.
        """
        return cls(ok=False, errors=errors)
