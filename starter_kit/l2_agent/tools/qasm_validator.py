"""Validation of model-produced OpenQASM through the existing L1 pipeline."""

from __future__ import annotations

import re

try:
    from ...qasm_L1.emitter import Translator
    from ...qasm_L1.parser import parse_qasm
except ImportError:
    # ``starter_kit`` becomes the import root in the official extracted bundle.
    from qasm_L1.emitter import Translator
    from qasm_L1.parser import parse_qasm

from ..models import ValidationResult


_FENCED_BLOCK = re.compile(
    r"```(?:openqasm|qasm)?[ \t]*\r?\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_VERSION_HEADER = re.compile(r"^\s*OPENQASM\s+2\.0\s*;", re.MULTILINE)
_QELIB_INCLUDE = re.compile(
    r'^\s*include\s+["\']qelib1\.inc["\']\s*;', re.MULTILINE
)


class LoomQQasmValidator:
    """Validate QASM against the grammar and all L1 translation targets.

    The validator performs only safe presentation cleanup (whitespace and a
    surrounding Markdown fence).  It never guesses gates, register sizes, or
    qubit indices because those changes could alter the user's declared goal.
    """

    def validate(self, qasm: str) -> ValidationResult:
        if not isinstance(qasm, str) or not qasm.strip():
            return ValidationResult(False, "", "QASM must be a non-empty string")

        normalized = self._strip_markdown_fence(qasm)
        if not _VERSION_HEADER.search(normalized):
            return ValidationResult(
                False,
                normalized,
                "missing required OPENQASM 2.0 header",
            )
        if not _QELIB_INCLUDE.search(normalized):
            return ValidationResult(
                False,
                normalized,
                'missing required include "qelib1.inc" statement',
            )

        try:
            circuit = parse_qasm(normalized)
            self._validate_registers(circuit)
            # Rendering every official target catches unsupported IR shapes
            # without importing or invoking any backend SDK.
            translator = Translator(circuit)
            for target in ("spinq", "originq", "braket"):
                rendered = translator.dispatch(target)
                if not isinstance(rendered, str) or not rendered.strip():
                    raise ValueError("empty %s translation" % target)
        except (SyntaxError, TypeError, ValueError) as exc:
            return ValidationResult(
                False,
                normalized,
                "%s: %s" % (type(exc).__name__, exc),
            )

        return ValidationResult(True, normalized)

    @staticmethod
    def _strip_markdown_fence(text: str) -> str:
        stripped = text.strip()
        blocks = _FENCED_BLOCK.findall(stripped)
        if not blocks:
            return stripped
        for block in blocks:
            if _VERSION_HEADER.search(block):
                return block.strip()
        return blocks[0].strip()

    @staticmethod
    def _validate_registers(circuit) -> None:
        if not circuit.qregs:
            raise ValueError("circuit declares no quantum register")

        all_names = [name for name, _size in circuit.qregs + circuit.cregs]
        if len(all_names) != len(set(all_names)):
            raise ValueError("register names must be unique")

        for name, size in circuit.qregs + circuit.cregs:
            if size <= 0:
                raise ValueError("register %s must have a positive size" % name)

        creg_sizes = dict(circuit.cregs)
        for measurement in circuit.measurements:
            for cbit in measurement.cbits:
                size = creg_sizes.get(cbit.reg)
                if size is None or cbit.index >= size:
                    raise ValueError("classical bit index out of range: %s" % cbit.token)
