"""Handler for deterministic backend recommendations."""

from ..context import AgentContext
from ..models import AgentIntent, AgentResult
from .base import TaskHandler


class RecommendBackendHandler(TaskHandler):
    task_type = "recommend_backend"

    def execute(self, intent: AgentIntent, context: AgentContext) -> AgentResult:
        selection = context.backend_selector.select(intent.backend_constraints)
        if not selection.selected_id:
            return AgentResult.failure(self.task_type, selection.explanation)
        return AgentResult(
            ok=True,
            task_type=self.task_type,
            backend_id=selection.selected_id,
            explanation=selection.explanation,
            alternatives=selection.alternatives,
        )
