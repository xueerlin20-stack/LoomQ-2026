"""Shared one-repair validation flow for QASM handlers."""

from __future__ import annotations

from ..context import AgentContext
from ..models import AgentIntent, AgentResult


def validate_with_one_repair(
    intent: AgentIntent,
    context: AgentContext,
) -> AgentResult:
    candidate = intent.candidate_qasm
    if not isinstance(candidate, str) or not candidate.strip():
        return AgentResult.failure(intent.task_type, "模型没有提供 QASM 候选。")

    validation = context.qasm_validator.validate(candidate)
    repaired = False
    if not validation.ok:
        candidate = context.llm.repair_qasm(
            user_goal=intent.user_goal,
            broken_qasm=validation.qasm,
            validation_error=validation.error or "unknown validation error",
            source_qasm=intent.source_qasm,
        )
        repaired = True
        validation = context.qasm_validator.validate(candidate)

    if not validation.ok:
        return AgentResult.failure(
            intent.task_type,
            "QASM 在一次修复后仍未通过验证：%s"
            % (validation.error or "unknown validation error"),
        )

    return AgentResult(
        ok=True,
        task_type=intent.task_type,
        qasm=validation.qasm,
        explanation=intent.explanation,
        validation={"syntax": "passed", "repaired": repaired},
    )
