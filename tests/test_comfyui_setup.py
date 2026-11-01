import importlib.util
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_setup():
    spec = importlib.util.spec_from_file_location(
        "comfyui_setup", ROOT / "scripts" / "comfyui_setup.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ComfyUISetupTests(unittest.TestCase):
    def test_default_root_honors_environment(self):
        setup = load_setup()
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"COMFYUI_ROOT": temp_dir}
        ):
            self.assertEqual(setup.default_root(), Path(temp_dir))

    def test_missing_install_is_detected(self):
        setup = load_setup()
        with tempfile.TemporaryDirectory() as temp_dir:
            status = setup.inspect_install(Path(temp_dir))
        self.assertFalse(status["ready"])
        self.assertFalse(status["comfyui"])
        self.assertTrue(all(not present for present in status["models"].values()))

    def test_plan_names_every_required_component(self):
        setup = load_setup()
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = "\n".join(setup.build_plan(Path(temp_dir)))
        self.assertIn("Comfy-Org/ComfyUI", plan)
        self.assertIn("v0.42.0", plan)
        self.assertIn("ComfyUI-GGUF", plan)
        self.assertEqual(plan.count("modelscope.cn/models"), 3)

    def test_install_requires_explicit_consent(self):
        setup = load_setup()
        with tempfile.TemporaryDirectory() as temp_dir:
            stderr = io.StringIO()
            with patch("subprocess.run") as run, contextlib.redirect_stderr(stderr):
                code = setup.main(["install", "--root", temp_dir])
            self.assertEqual(code, 2)
            self.assertFalse((Path(temp_dir) / "main.py").exists())
            self.assertIn("explicit user consent", stderr.getvalue().lower())
            run.assert_not_called()

    def test_check_command_reports_an_incomplete_install(self):
        setup = load_setup()
        with tempfile.TemporaryDirectory() as temp_dir:
            with contextlib.redirect_stdout(io.StringIO()):
                code = setup.main(["check", "--root", temp_dir])
        self.assertEqual(code, 1)

    def test_model_manifest_has_verified_sizes_and_hashes(self):
        setup = load_setup()
        self.assertEqual(len(setup.MODELS), 3)
        self.assertGreater(sum(model["size"] for model in setup.MODELS), 10_000_000_000)
        for model in setup.MODELS:
            self.assertIn("sha256", model)
            self.assertIn("url", model)

    def test_docs_require_user_approval_before_install(self):
        skill = (ROOT / "SKILL.md").read_text("utf-8")
        readme = (ROOT / "README.md").read_text("utf-8")
        guide = (ROOT / "references" / "comfyui-install.md").read_text("utf-8")
        self.assertIn("Ask the user explicitly", skill)
        self.assertIn("explicit **yes**", readme)
        self.assertIn("consent-gated", guide)


if __name__ == "__main__":
    unittest.main()
