"""Dependency interfaces and per-request context for the L2 agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from .models import AgentIntent, BackendSelection, ValidationResult


class LLMGateway(Protocol):
    """The model capabilities used by the first version of the agent."""

    def understand(self, prompt: str) -> AgentIntent:
        """Turn a user's natural-language request into a structured intent."""

    def repair_qasm(
        self,
        *,
        user_goal: str,
        broken_qasm: str,
        validation_error: str,
        source_qasm: str | None = None,
    ) -> str:
        """Repair one invalid QASM candidate without changing the goal."""


class QasmValidator(Protocol):
    def validate(self, qasm: str) -> ValidationResult:
        """Validate and normalize one OpenQASM 2.0 candidate."""


class BackendSelector(Protocol):
    def select(self, constraints: Dict[str, Any]) -> BackendSelection:
        """Select a backend from the official capability data."""


@dataclass(frozen=True)
class AgentContext:
    """Dependencies available to all handlers for one agent instance."""

    llm: LLMGateway
    qasm_validator: QasmValidator
    backend_selector: BackendSelector
