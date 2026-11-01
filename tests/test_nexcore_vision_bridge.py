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
        "nexcore_vision", ROOT / "scripts" / "nexcore_vision.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class NexcoreVisionBridgeTests(unittest.TestCase):
    def test_bundled_pipeline_contains_required_sources(self):
        root = ROOT / "integrations" / "nexcorevision"
        self.assertTrue((root / "LICENSE").is_file())
        self.assertTrue((root / "NOTICE.md").is_file())
        self.assertTrue((root / "src" / "index.ts").is_file())
        self.assertTrue((root / "src" / "deep_vision.py").is_file())
        self.assertTrue((root / "src" / "windows-ocr.ps1").is_file())

    def test_skill_routes_visual_evidence_through_bundled_pipeline(self):
        skill = (ROOT / "SKILL.md").read_text("utf-8")
        readme = (ROOT / "README.md").read_text("utf-8")
        self.assertIn("scripts/nexcore_vision.py", skill)
        self.assertIn("NexcoreVision evidence architecture", readme)
        self.assertIn("vision.py", skill)
        self.assertTrue((ROOT / "assets" / "media-banner.webp").is_file())
        self.assertTrue((ROOT / "assets" / "nexcore-vision-evidence.png").is_file())
        self.assertTrue((ROOT / "images" / "local-comfyui.png").is_file())

    def test_bundled_pipeline_is_the_default_root(self):
        bridge = load_bridge()
        self.assertEqual(bridge.resolve_root(), ROOT / "integrations" / "nexcorevision")

    def test_environment_root_overrides_the_bundle(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text("{}", "utf-8")
            (root / "src").mkdir()
            (root / "src" / "cli.ts").write_text("// stub", "utf-8")
            with patch.dict(os.environ, {"NEXCORE_VISION_ROOT": temp_dir}):
                self.assertEqual(bridge.resolve_root(), root.resolve())

    def test_analyze_forwards_to_node_without_a_shell(self):
        bridge = load_bridge()
        cli = bridge.resolve_root() / "src" / "cli.ts"
        with patch("shutil.which", return_value="node.exe"), patch(
            "subprocess.run"
        ) as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "v24.15.0\n"
            code = bridge.main(["analyze", "screenshot.png", "--deep"])
        self.assertEqual(code, 0)
        self.assertEqual(
            run.call_args_list[-1].args[0],
            [
                "node.exe",
                "--experimental-strip-types",
                str(cli),
                "screenshot.png",
                "--deep",
            ],
        )
        self.assertNotIn("shell", run.call_args_list[-1].kwargs)

    def test_unknown_command_is_rejected(self):
        bridge = load_bridge()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            bridge.main(["shell"])


if __name__ == "__main__":
    unittest.main()
