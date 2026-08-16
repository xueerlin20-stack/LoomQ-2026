import unittest
from unittest import mock

from starter_kit.l2_agent import AgentResult
from starter_kit.web_app import WEB_ROOT, WebApplication


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.prompts = []

    def execute(self, prompt):
        self.prompts.append(prompt)
        return self.result


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

        with mock.patch("starter_kit.web_app.create_agent", return_value=agent):
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
            "starter_kit.web_app.create_agent", return_value=FakeAgent(result)
        ):
            response = WebApplication().handle_chat({"prompt": "Choose a backend"})

        self.assertEqual(response["backend_id"], "originq_local_simulator")
        self.assertEqual(response["response_language"], "en")

    def test_empty_prompt_is_rejected_before_agent_creation(self):
        with mock.patch("starter_kit.web_app.create_agent") as create:
            with self.assertRaisesRegex(ValueError, "non-empty"):
                WebApplication().handle_chat({"prompt": "   "})
        create.assert_not_called()

    def test_oversized_prompt_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            WebApplication().handle_chat({"prompt": "x" * 12001})


class WebAssetsTests(unittest.TestCase):
    def test_required_assets_exist_and_have_product_content(self):
        index = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        css = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
        javascript = (WEB_ROOT / "app.js").read_text(encoding="utf-8")

        self.assertIn("LoomQ Agent", index)
        self.assertIn("无需 QASM 知识", index)
        self.assertIn('id="composer"', index)
        self.assertIn("/api/chat", javascript)
        self.assertIn("validation.counts", javascript)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertNotIn("LOOMQ_LLM_API_KEY", index + javascript)


if __name__ == "__main__":
    unittest.main()
