#!/usr/bin/env python3
"""LoomQ submission adapter contract v1.0.

Thin facade over the translation pipeline:

    qasm_L1/parser.py   OpenQASM 2.0 text -> Circuit IR
    qasm_L1/emitter.py  Translator -> target-native text
    qasm_L1/runners.py  SDK execution backends (spinq / braket / originq)

The contract functions below never re-parse or re-implement platform logic;
they only parse once and dispatch to a target.
"""

from typing import Any, Dict, List, Tuple

try:
    from .qasm_L1 import runners
    from .qasm_L1.emitter import Translator
    from .qasm_L1.execution import save_hardware_evidence, save_local_artifacts
    from .qasm_L1.parser import parse_qasm
except ImportError:
    from qasm_L1 import runners
    from qasm_L1.emitter import Translator
    from qasm_L1.execution import save_hardware_evidence, save_local_artifacts
    from qasm_L1.parser import parse_qasm

SUPPORTED_TARGETS = ("spinq", "originq", "braket")

RUNNERS = {
    "spinq": runners.run_spinq,
    "braket": runners.run_braket,
    "originq": runners.run_originq,
}

REAL_RUNNERS = {
    "spinq": runners.run_spinq_real,
    "braket": runners.run_braket_real,
    "originq": runners.run_originq_real,
}

PROGRAM_SUFFIXES = {"spinq": "qasm", "braket": "qasm", "originq": "originir"}


def _normalize_target(target: str) -> str:
    return (target or "").strip().lower()


def transpile(qasm_str: str, target: str) -> str:
    """Translate OpenQASM 2.0 into the target backend's native representation."""
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    circuit = parse_qasm(qasm_str)
    return Translator(circuit).dispatch(target_name)


def run(qasm_str: str, target: str, shots: int) -> Dict[str, Any]:
    """Execute a circuit and return the unified result schema from the rules."""
    if shots <= 0:
        raise ValueError("shots must be positive")
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")

    native_qasm = transpile(qasm_str, target_name)
    execution = RUNNERS[target_name](native_qasm, shots)
    return execution.to_contract_dict()


def run_and_save(
    qasm_str: str,
    target: str,
    shots: int,
    output_directory: str,
) -> Dict[str, Any]:
    """Run a local backend once and export its native program and result JSON."""
    if shots <= 0:
        raise ValueError("shots must be positive")
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")
    if not output_directory:
        raise ValueError("output_directory is required")

    native_program = transpile(qasm_str, target_name)
    execution = RUNNERS[target_name](native_program, shots)
    execution.metadata["artifact_files"] = save_local_artifacts(
        execution,
        native_program,
        output_directory,
        program_suffix=PROGRAM_SUFFIXES[target_name],
    )
    return execution.to_contract_dict()


def run_real(
    qasm_str: str,
    target: str,
    shots: int,
    **backend_options: Any,
) -> Dict[str, Any]:
    """Submit to a physical QPU and return a traceable, evidence-ready result.

    Credentials and device selection are target-specific keyword arguments.
    Pass ``evidence_directory`` to also export the native program, normalized
    result, and sanitized platform response.
    """
    if shots <= 0:
        raise ValueError("shots must be positive")
    target_name = _normalize_target(target)
    if target_name not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target: {target}")

    evidence_directory = backend_options.pop("evidence_directory", None)
    native_program = transpile(qasm_str, target_name)
    execution = REAL_RUNNERS[target_name](native_program, shots, **backend_options)
    if evidence_directory:
        execution.metadata["evidence_files"] = save_hardware_evidence(
            execution,
            native_program,
            evidence_directory,
            program_suffix=PROGRAM_SUFFIXES[target_name],
        )
    return execution.to_contract_dict(include_raw=True)


def agent_chat(prompt: str) -> str:
    """Optional L2 entry point using the documented LOOMQ_LLM_* environment."""
    raise NotImplementedError("L2 is optional; implement agent_chat(prompt) to enter")


def compile_hybrid(hybrid_qasm_str: str) -> Tuple[List[str], str]:
    """Optional L3 entry point. Return quantum operations and RISC-V assembly."""
    raise NotImplementedError(
        "L3 is optional; implement compile_hybrid(hybrid_qasm_str) to enter"
    )
