"""Production construction of the LoomQ L2 agent."""

from .agent import AgentEngine
from .context import AgentContext
from .gateway import OpenAICompatibleLLMGateway
from .registry import default_registry
from .tools import CapabilityBackendSelector, LoomQQasmValidator


def create_agent() -> AgentEngine:
    context = AgentContext(
        llm=OpenAICompatibleLLMGateway(),
        qasm_validator=LoomQQasmValidator(),
        backend_selector=CapabilityBackendSelector(),
    )
    return AgentEngine(context, default_registry())
