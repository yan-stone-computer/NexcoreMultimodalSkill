import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "comfyui_local", ROOT / "scripts" / "comfyui_local.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ComfyUIBridgeTests(unittest.TestCase):
    def test_skill_and_readme_route_local_generation(self):
        skill = (ROOT / "SKILL.md").read_text("utf-8")
        readme = (ROOT / "README.md").read_text("utf-8")
        env_example = (ROOT / ".env.example").read_text("utf-8")
        self.assertIn("comfyui_local.py", skill)
        self.assertIn("Local text/image → image", skill)
        self.assertIn("ComfyUI Qwen", readme)
        self.assertIn("COMFYUI_QWEN_CLI", env_example)

    def test_explicit_cli_path_wins(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = Path(temp_dir) / "comfyui_qwen.py"
            cli.write_text("# stub", "utf-8")
            self.assertEqual(bridge.resolve_cli(str(cli)), cli.resolve())

    def test_environment_cli_path_is_supported(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = Path(temp_dir) / "comfyui_qwen.py"
            cli.write_text("# stub", "utf-8")
            with patch.dict(os.environ, {"COMFYUI_QWEN_CLI": str(cli)}):
                self.assertEqual(bridge.resolve_cli(), cli.resolve())

    def test_generate_forwards_arguments_without_a_shell(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as temp_dir:
            cli = Path(temp_dir) / "comfyui_qwen.py"
            cli.write_text("# stub", "utf-8")
            with patch("subprocess.run") as run:
                run.return_value.returncode = 0
                code = bridge.main(
                    [
                        "--cli",
                        str(cli),
                        "generate",
                        "a quiet tea house",
                        "--preset",
                        "preview",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(
                run.call_args.args[0],
                [
                    sys.executable,
                    str(cli.resolve()),
                    "generate",
                    "a quiet tea house",
                    "--preset",
                    "preview",
                ],
            )
            self.assertFalse(run.call_args.kwargs["check"])
            self.assertNotIn("shell", run.call_args.kwargs)

    def test_unknown_command_is_rejected_before_launch(self):
        bridge = load_bridge()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            bridge.main(["shell", "whoami"])


if __name__ == "__main__":
    unittest.main()
