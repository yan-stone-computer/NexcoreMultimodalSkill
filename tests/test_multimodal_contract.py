import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MultimodalContractTests(unittest.TestCase):
    def test_media_cli_uses_skill_root_env_file(self):
        media = load_module("agnes_api", SCRIPTS / "agnes_api.py")
        self.assertEqual(media.ENV_FILE, ROOT / ".env")

    def test_skill_uses_merged_name_and_documents_both_directions(self):
        skill = (ROOT / "SKILL.md").read_text("utf-8")
        self.assertIn("name: nexcore-multimodal-skill", skill)
        self.assertIn("image generation", skill.lower())
        self.assertIn("video generation", skill.lower())
        self.assertIn("vision.py", skill)
        self.assertIn("agnes_api.py", skill)

    def test_key_manager_supports_agnes(self):
        keys = load_module("set_key", SCRIPTS / "set_key.py")
        self.assertEqual(keys.resolve_env("agnes"), "AGNES_API_KEY")

    def test_installer_never_copies_local_secrets(self):
        installer = load_module("install", SCRIPTS / "install.py")
        self.assertIn(".env", installer.EXCLUDE)
        self.assertIn("docs", installer.EXCLUDE)


if __name__ == "__main__":
    unittest.main()
