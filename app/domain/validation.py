from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list

    @classmethod
    def valid(cls) -> "ValidationResult":
        return cls(ok=True, errors=[])

    @classmethod
    def invalid(cls, errors: list) -> "ValidationResult":
        return cls(ok=False, errors=errors)
