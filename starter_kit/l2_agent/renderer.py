"""Stable text rendering for the automatic L2 evaluator."""

from .models import AgentResult


def render_result(result: AgentResult) -> str:
    if not result.ok:
        return "LoomQ Agent 无法完成该任务：%s" % result.message

    if result.qasm:
        explanation = (
            "\n\n说明：%s" % result.explanation if result.explanation else ""
        )
        return "已生成并通过 LoomQ 验证。\n\n```qasm\n%s\n```%s" % (
            result.qasm.strip(),
            explanation,
        )

    if result.backend_id:
        explanation = result.explanation or "满足用户声明的约束。"
        alternatives = ""
        if result.alternatives:
            alternatives = "\n备选：" + "、".join(result.alternatives)
        return "推荐后端：%s\n\n理由：%s%s" % (
            result.backend_id,
            explanation,
            alternatives,
        )

    return "LoomQ Agent 已完成任务。"
