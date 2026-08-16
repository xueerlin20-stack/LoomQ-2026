"""Top-level orchestration for the LoomQ L2 agent."""

from __future__ import annotations

from .context import AgentContext
from .registry import HandlerRegistry
from .renderer import render_result


class AgentEngine:
    """Understand, dispatch, execute, and render one user request."""

    def __init__(self, context: AgentContext, registry: HandlerRegistry) -> None:
        self._context = context
        self._registry = registry

    def respond(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("L2 prompt must be a non-empty string")

        intent = self._context.llm.understand(prompt)
        intent.validate()

        handler = self._registry.get(intent.task_type)
        if handler is None:
            raise ValueError("no handler registered for task: %s" % intent.task_type)

        return render_result(handler.execute(intent, self._context))
