from __future__ import annotations


class AstralJetError(Exception):
    """Bazowy błąd z kodem i bezpiecznym następnym krokiem."""

    code = "ASTRALJET_ERROR"
    exit_code = 4

    def __init__(
        self,
        message: str,
        *,
        blocker: str | None = None,
        owner: str | None = None,
        allowed_next_action: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.blocker = blocker
        self.owner = owner
        self.allowed_next_action = allowed_next_action

    def as_dict(self) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "blocker": self.blocker,
                "owner": self.owner,
                "allowed_next_action": self.allowed_next_action,
            }
        }


class ValidationError(AstralJetError):
    code = "VALIDATION_ERROR"
    exit_code = 2


class DomainBlockedError(AstralJetError):
    code = "DOMAIN_BLOCKED"
    exit_code = 3


class TechnicalError(AstralJetError):
    code = "TECHNICAL_ERROR"
    exit_code = 4
