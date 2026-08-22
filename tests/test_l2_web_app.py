import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from starter_kit.l2_agent import AgentResult
from starter_kit.web_app import WEB_ROOT, WebApplication
from starter_kit.web_backend.backend_presentation import BackendPresenter
from starter_kit.web_backend.chat import ChatService
from starter_kit.web_backend.conversations import ConversationStore


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.prompts = []

    def execute(self, prompt):
        self.prompts.append(prompt)
        return self.result


class SequenceAgent:
    def __init__(self, results):
        self.results = list(results)
        self.prompts = []

    def execute(self, prompt):
        self.prompts.append(prompt)
        return self.results.pop(0)


class WebApplicationTests(unittest.TestCase):
    def test_qasm_result_is_returned_as_structured_json_ready_data(self):
        result = AgentResult(
            ok=True,
            task_type="generate_qasm",
            response_language="zh",
            qasm="OPENQASM 2.0;",
            explanation="三比特 GHZ 电路。",
            validation={
                "status": "verified",
                "shots": 4096,
                "counts": {"000": 2048, "111": 2048},
                "fidelity": 1.0,
                "explanation": "SpinQit 运行验证通过。",
            },
        )
        agent = FakeAgent(result)

        with mock.patch("starter_kit.web_backend.chat.create_agent", return_value=agent):
            response = WebApplication().handle_chat({"prompt": "  生成 GHZ  "})

        self.assertEqual(agent.prompts, ["生成 GHZ"])
        self.assertEqual(response["qasm"], "OPENQASM 2.0;")
        self.assertEqual(response["validation"]["counts"]["111"], 2048)
        self.assertEqual(response["display_text"], "三比特 GHZ 电路。")

    def test_backend_result_is_supported(self):
        result = AgentResult(
            ok=True,
            task_type="recommend_backend",
            response_language="en",
            backend_id="originq_local_simulator",
            explanation="It satisfies every constraint.",
        )

        with mock.patch(
            "starter_kit.web_backend.chat.create_agent", return_value=FakeAgent(result)
        ):
            response = WebApplication().handle_chat({"prompt": "Choose a backend"})

        self.assertEqual(response["backend_id"], "originq_local_simulator")
        self.assertEqual(response["response_language"], "en")
        self.assertEqual(response["backend"]["queue"], "No queue")
        self.assertEqual(response["backend"]["cost"], "Free")
        self.assertEqual(response["backend"]["max_qubits"], 30)

    def test_backend_facts_are_localized_for_plain_chinese_display(self):
        backend = BackendPresenter().describe("originq_local_simulator", "zh")

        self.assertEqual(backend["kind"], "本地模拟器")
        self.assertEqual(backend["queue"], "无需排队")
        self.assertEqual(backend["cost"], "免费")
        self.assertEqual(backend["account"], "无需注册账号")

    def test_empty_prompt_is_rejected_before_agent_creation(self):
        with mock.patch("starter_kit.web_backend.chat.create_agent") as create:
            with self.assertRaisesRegex(ValueError, "non-empty"):
                WebApplication().handle_chat({"prompt": "   "})
        create.assert_not_called()

    def test_oversized_prompt_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            WebApplication().handle_chat({"prompt": "x" * 12001})

    def test_quantum_background_changes_the_agent_explanation_preference(self):
        result = AgentResult(
            ok=True,
            task_type="generate_qasm",
            response_language="zh",
            explanation="已完成。",
        )
        agent = FakeAgent(result)
        with mock.patch("starter_kit.web_backend.chat.create_agent", return_value=agent):
            WebApplication().handle_chat(
                {
                    "prompt": "生成 Bell 态",
                    "quantum_profile": "new",
                    "explain_concepts": True,
                }
            )

        self.assertIn("生成 Bell 态", agent.prompts[0])
        self.assertIn("第一次接触量子计算", agent.prompts[0])
        self.assertIn("补充本次实验涉及的量子概念", agent.prompts[0])

    def test_follow_up_explains_the_active_circuit_without_repeating_qasm(self):
        first = AgentResult(
            ok=True,
            task_type="generate_qasm",
            response_language="zh",
            qasm="OPENQASM 2.0;\nqreg q[3];",
            explanation="已经生成三比特 GHZ 电路。",
            validation={"status": "verified"},
        )
        second = AgentResult(
            ok=True,
            task_type="generate_qasm",
            response_language="zh",
            qasm=first.qasm,
            explanation="H 门先让第一个量子比特进入两种可能性的叠加。",
            validation={"status": "verified"},
        )
        agent = SequenceAgent([first, second])
        app = WebApplication(chat=ChatService(agent_factory=lambda: agent))

        created = app.handle_chat({"prompt": "生成一个三比特 GHZ 电路"})
        explained = app.handle_chat(
            {
                "prompt": "为什么第一个门是 H？",
                "conversation_id": created["conversation_id"],
                "active_artifact_id": created["active_artifact"]["id"],
                "expected_version": 1,
            }
        )

        self.assertEqual(explained["conversation_action"], "explain_current")
        self.assertIsNone(explained["qasm"])
        self.assertEqual(explained["active_artifact"]["version"], 1)
        self.assertIn("当前电路 QASM", agent.prompts[1])
        self.assertIn(first.qasm, agent.prompts[1])
        self.assertIn("为什么第一个门是 H", agent.prompts[1])

    def test_follow_up_modification_creates_the_next_circuit_version(self):
        first = AgentResult(
            ok=True,
            task_type="generate_qasm",
            qasm="OPENQASM 2.0;\nqreg q[3];",
            explanation="三比特版本。",
        )
        second = AgentResult(
            ok=True,
            task_type="repair_qasm",
            qasm="OPENQASM 2.0;\nqreg q[5];",
            explanation="已经改成五比特。",
        )
        agent = SequenceAgent([first, second])
        app = WebApplication(chat=ChatService(agent_factory=lambda: agent))
        created = app.handle_chat({"prompt": "生成三比特 GHZ 电路"})
        artifact = created["active_artifact"]

        modified = app.handle_chat(
            {
                "prompt": "把它改成五比特",
                "conversation_id": created["conversation_id"],
                "active_artifact_id": artifact["id"],
                "expected_version": artifact["version"],
            }
        )

        self.assertEqual(modified["conversation_action"], "modify_current")
        self.assertEqual(modified["active_artifact"]["id"], artifact["id"])
        self.assertEqual(modified["active_artifact"]["version"], 2)
        self.assertIn("基于当前 QASM 完成修改", agent.prompts[1])

    def test_run_follow_up_uses_current_qasm_without_creating_a_version(self):
        result = AgentResult(
            ok=True,
            task_type="generate_qasm",
            qasm="OPENQASM 2.0;\nqreg q[2];",
            explanation="Bell 电路已经运行。",
            validation={"shots": 100, "counts": {"00": 50, "11": 50}},
        )
        agent = FakeAgent(result)
        app = WebApplication(chat=ChatService(agent_factory=lambda: agent))
        created = app.handle_chat({"prompt": "生成 Bell 电路"})
        artifact = created["active_artifact"]

        rerun = app.handle_chat(
            {
                "prompt": "再运行一次当前电路",
                "conversation_id": created["conversation_id"],
                "active_artifact_id": artifact["id"],
                "expected_version": 1,
            }
        )

        self.assertEqual(rerun["conversation_action"], "run_current")
        self.assertEqual(rerun["active_artifact"], artifact)
        self.assertEqual(rerun["qasm"], result.qasm)
        self.assertIn(result.qasm, agent.prompts[1])

    def test_stale_circuit_version_is_rejected_before_agent_call(self):
        result = AgentResult(
            ok=True,
            task_type="generate_qasm",
            qasm="OPENQASM 2.0;\nqreg q[2];",
            explanation="Bell 电路。",
        )
        agent = FakeAgent(result)
        app = WebApplication(chat=ChatService(agent_factory=lambda: agent))
        created = app.handle_chat({"prompt": "生成 Bell 电路"})

        with self.assertRaisesRegex(ValueError, "版本已变化"):
            app.handle_chat(
                {
                    "prompt": "修改它",
                    "conversation_id": created["conversation_id"],
                    "active_artifact_id": created["active_artifact"]["id"],
                    "expected_version": 99,
                }
            )
        self.assertEqual(len(agent.prompts), 1)

    def test_conversation_store_keeps_only_a_bounded_turn_window(self):
        store = ConversationStore(max_turns=2)
        conversation = store.get_or_create(None)
        for index in range(3):
            store.record(
                conversation,
                user_text="user-%d" % index,
                assistant_text="assistant-%d" % index,
                action="explain_current",
            )

        self.assertEqual([turn.user_text for turn in conversation.turns], ["user-1", "user-2"])

    def test_ending_a_conversation_deletes_turns_and_active_circuit(self):
        result = AgentResult(
            ok=True,
            task_type="generate_qasm",
            qasm="OPENQASM 2.0;\nqreg q[2];",
            explanation="Bell 电路。",
        )
        store = ConversationStore()
        app = WebApplication(
            chat=ChatService(agent_factory=lambda: FakeAgent(result), conversation_store=store)
        )
        created = app.handle_chat({"prompt": "生成 Bell 电路"})
        conversation_id = created["conversation_id"]

        reset = app.reset_conversation({"conversation_id": conversation_id})
        replacement = store.get_or_create(conversation_id)

        self.assertEqual(reset, {"ok": True, "deleted": True})
        self.assertNotEqual(replacement.conversation_id, conversation_id)
        self.assertEqual(replacement.turns, [])
        self.assertIsNone(replacement.active_artifact)

    def test_configuration_status_never_returns_api_key(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env.l2"
            env_file.write_text(
                "LOOMQ_LLM_BASE_URL=https://api.deepseek.com\n"
                "LOOMQ_LLM_API_KEY=super-secret-value\n"
                "LOOMQ_LLM_MODEL=deepseek-v4-flash\n"
                "LOOMQ_LLM_TIMEOUT_SECONDS=120\n",
                encoding="utf-8",
            )
            with mock.patch.dict("os.environ", {}, clear=True):
                status = WebApplication(env_file).configuration_status()

        self.assertTrue(status["ready"])
        self.assertNotIn("super-secret-value", str(status))
        api_key = next(
            field for field in status["fields"] if field["name"] == "LOOMQ_LLM_API_KEY"
        )
        self.assertEqual(api_key["value"], "")
        self.assertTrue(api_key["configured"])

    def test_configuration_can_be_created_from_the_web_onboarding(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env.l2"
            with mock.patch.dict("os.environ", {}, clear=True):
                app = WebApplication(env_file)
                before = app.configuration_status()
                after = app.save_configuration(
                    {
                        "LOOMQ_LLM_BASE_URL": "https://api.deepseek.com",
                        "LOOMQ_LLM_API_KEY": "test-key",
                        "LOOMQ_LLM_MODEL": "deepseek-v4-flash",
                        "LOOMQ_LLM_TIMEOUT_SECONDS": "120",
                    }
                )
                saved = env_file.read_text(encoding="utf-8")

        self.assertFalse(before["ready"])
        self.assertTrue(after["ready"])
        self.assertIn("LOOMQ_LLM_API_KEY=test-key", saved)
        self.assertNotIn("test-key", str(after))


class WebAssetsTests(unittest.TestCase):
    def test_required_assets_exist_and_have_product_content(self):
        index = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        workspace = (WEB_ROOT / "workspace.html").read_text(encoding="utf-8")
        css = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
        javascript_files = sorted((WEB_ROOT / "js").glob("*.js"))
        javascript = "\n".join(
            path.read_text(encoding="utf-8") for path in javascript_files
        )

        self.assertIn("LoomQ Agent", index)
        self.assertIn("无需 QASM 知识", index)
        self.assertNotIn('id="composer"', index)
        self.assertIn('href="/workspace.html"', index)
        self.assertIn('id="open-config"', index)
        self.assertIn('id="composer"', workspace)
        self.assertIn('id="conversation-context"', workspace)
        self.assertIn('href="/"', workspace)
        self.assertIn("返回主界面", workspace)
        self.assertIn('id="onboarding"', index)
        self.assertIn('id="open-guide"', index)
        self.assertIn("新手引导", index)
        self.assertIn('type="module" src="/js/main.js"', index)
        self.assertIn('type="module" src="/js/workspace.js"', workspace)
        self.assertIn("你对量子计算熟悉吗", index)
        self.assertIn("基础概念科普", index)
        self.assertIn("示例电路互动", index)
        self.assertIn('id="module-concept-basics"', index)
        self.assertIn('id="module-example-circuit"', index)
        self.assertIn("默认跳过基础概念，直接看示例电路", index)
        self.assertIn("先认识电路里的四样东西", index)
        self.assertIn("量子比特", index)
        self.assertIn("自带概率的比特", index)
        self.assertIn("正在旋转的硬币", index)
        self.assertIn("量子门", index)
        self.assertIn("量子电路", index)
        self.assertIn("测量", index)
        self.assertIn('id="concept-basics"', index)
        self.assertIn('class="concept-sidebar"', index)
        self.assertIn('data-concept-target="qubit"', index)
        self.assertIn('data-concept-panel="measurement"', index)
        self.assertIn('id="next-concept"', index)
        self.assertIn('data-basic-action="h"', index)
        self.assertIn('id="basic-gate-chip"', index)
        self.assertIn("尚未加载量子门", index)
        self.assertIn("测量一次，只会得到一个普通结果", index)
        self.assertIn('class="qubit-story-copy"', index)
        self.assertIn("像在某一刻按下快门", index)
        self.assertNotIn('class="quantum-compass"', index)
        self.assertIn('data-basic-action="measure"', index)
        self.assertIn("亲手运行第一个量子电路", index)
        self.assertIn('data-lab-action="h"', index)
        self.assertIn('data-lab-action="cx"', index)
        self.assertIn("CX 门", index)
        self.assertIn("点击关联", index)
        self.assertIn('data-lab-action="why-q1"', index)
        self.assertIn('id="measurement-results"', index)
        self.assertIn('id="lab-action-text"', index)
        self.assertNotIn('class="reality-strip"', index)
        self.assertIn("女性法律援助中心", index)
        self.assertIn("审计记录", index)
        self.assertIn("/api/chat", javascript)
        self.assertIn("/api/config", javascript)
        self.assertIn("/api/conversation/reset", javascript)
        self.assertIn("loomq.quantumProfile", javascript)
        self.assertIn("class QuantumLab", javascript)
        self.assertIn("class ConceptBasics", javascript)
        self.assertIn("animateGate(action)", javascript)
        self.assertNotIn("renderQubitVisual(state)", javascript)
        self.assertIn("measure()", javascript)
        self.assertIn("reset()", javascript)
        self.assertIn("explainWaitingQubit", javascript)
        self.assertIn("nextActionText", javascript)
        self.assertIn("validation.counts", javascript)
        self.assertIn("class ConversationSession", javascript)
        self.assertIn("conversation_id", javascript)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertNotIn("LOOMQ_LLM_API_KEY", index + javascript)
        self.assertGreaterEqual(len(javascript_files), 8)
        self.assertTrue((WEB_ROOT.parent / "web_backend" / "configuration.py").is_file())
        self.assertTrue((WEB_ROOT.parent / "web_backend" / "chat.py").is_file())
        self.assertTrue((WEB_ROOT.parent / "web_backend" / "http.py").is_file())


if __name__ == "__main__":
    unittest.main()
