import unittest

from starter_kit.l2_agent import AgentContext, AgentEngine, AgentIntent, default_registry
from starter_kit.l2_agent.tools import CapabilityBackendSelector, LoomQQasmValidator


BELL_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;"""


class RealQasmValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = LoomQQasmValidator()

    def test_valid_qasm_passes_the_existing_l1_pipeline(self):
        result = self.validator.validate(BELL_QASM)

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.qasm, BELL_QASM)

    def test_markdown_fence_is_safely_removed(self):
        result = self.validator.validate("说明文字\n```qasm\n%s\n```" % BELL_QASM)

        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.qasm, BELL_QASM)

    def test_missing_version_header_is_rejected(self):
        result = self.validator.validate(
            'include "qelib1.inc";\nqreg q[1];\nh q[0];'
        )

        self.assertFalse(result.ok)
        self.assertIn("OPENQASM 2.0", result.error)

    def test_missing_standard_library_is_rejected(self):
        result = self.validator.validate("OPENQASM 2.0;\nqreg q[1];\nh q[0];")

        self.assertFalse(result.ok)
        self.assertIn("qelib1.inc", result.error)

    def test_unsupported_gate_is_rejected_by_l1_parser(self):
        result = self.validator.validate(
            """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
u3(0,0,0) q[0];"""
        )

        self.assertFalse(result.ok)
        self.assertIn("unsupported gate", result.error)

    def test_classical_bit_out_of_range_is_rejected(self):
        result = self.validator.validate(
            """OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];
measure q[0] -> c[2];"""
        )

        self.assertFalse(result.ok)
        self.assertIn("classical bit index out of range", result.error)

    def test_no_quantum_register_is_rejected(self):
        result = self.validator.validate(
            """OPENQASM 2.0;
include "qelib1.inc";
creg c[1];"""
        )

        self.assertFalse(result.ok)
        self.assertIn("no quantum register", result.error)


class RealBackendSelectorTests(unittest.TestCase):
    def setUp(self):
        self.selector = CapabilityBackendSelector()

    def test_fifteen_qubits_without_queue_returns_all_local_options(self):
        selection = self.selector.select({"min_qubits": 15, "queue": "none"})

        self.assertEqual(selection.selected_id, "spinq_taurus_simulator")
        self.assertEqual(
            set([selection.selected_id] + selection.alternatives),
            {
                "spinq_taurus_simulator",
                "originq_local_simulator",
                "braket_local_simulator",
            },
        )

    def test_twenty_six_qubits_free_without_queue_selects_originq_local(self):
        selection = self.selector.select(
            {"min_qubits": 26, "queue": "none", "cost": "free"}
        )

        self.assertEqual(selection.selected_id, "originq_local_simulator")
        self.assertEqual(selection.alternatives, [])

    def test_real_hardware_with_no_paid_cost_returns_free_quota_qpus(self):
        selection = self.selector.select(
            {"min_qubits": 5, "kind": "qpu", "cost": "not_paid"}
        )

        self.assertEqual(selection.selected_id, "spinq_cloud_qpu")
        self.assertEqual(selection.alternatives, ["originq_wukong"])

    def test_paid_constraint_selects_braket_cloud(self):
        selection = self.selector.select({"cost": "paid"})

        self.assertEqual(selection.selected_id, "braket_cloud")

    def test_impossible_qubit_count_reports_no_match(self):
        selection = self.selector.select({"min_qubits": 73})

        self.assertIsNone(selection.selected_id)
        self.assertIn("没有满足", selection.explanation)
        self.assertTrue(selection.alternatives)

    def test_unknown_constraint_is_rejected_instead_of_ignored(self):
        with self.assertRaisesRegex(ValueError, "unsupported backend constraint"):
            self.selector.select({"fastest": True})

    def test_invalid_constraint_type_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self.selector.select({"min_qubits": "20"})


class MockLLMWithRealTools:
    def __init__(self, intent):
        self.intent = intent
        self.understand_count = 0

    def understand(self, _prompt):
        self.understand_count += 1
        return self.intent

    def repair_qasm(self, **_arguments):
        raise AssertionError("valid test QASM must not trigger model repair")


class AgentWithRealToolsTests(unittest.TestCase):
    def test_mock_model_and_real_qasm_validator_complete_the_agent_flow(self):
        llm = MockLLMWithRealTools(
            AgentIntent(
                task_type="generate_qasm",
                user_goal="生成贝尔态",
                candidate_qasm=BELL_QASM,
            )
        )
        context = AgentContext(
            llm=llm,
            qasm_validator=LoomQQasmValidator(),
            backend_selector=CapabilityBackendSelector(),
        )

        reply = AgentEngine(context, default_registry()).respond("生成贝尔态")

        self.assertEqual(llm.understand_count, 1)
        self.assertIn(BELL_QASM, reply)

    def test_mock_model_and_real_selector_complete_the_agent_flow(self):
        llm = MockLLMWithRealTools(
            AgentIntent(
                task_type="recommend_backend",
                user_goal="26 比特、免费、无排队",
                backend_constraints={
                    "min_qubits": 26,
                    "queue": "none",
                    "cost": "free",
                },
            )
        )
        context = AgentContext(
            llm=llm,
            qasm_validator=LoomQQasmValidator(),
            backend_selector=CapabilityBackendSelector(),
        )

        reply = AgentEngine(context, default_registry()).respond(
            "运行 26 比特电路，必须免费且不能排队"
        )

        self.assertEqual(llm.understand_count, 1)
        self.assertIn("originq_local_simulator", reply)


if __name__ == "__main__":
    unittest.main()
