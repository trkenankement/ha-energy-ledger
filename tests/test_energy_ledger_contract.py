"""Packaging and no-network boundaries; not a live HA acceptance test."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/energy_ledger"


class ContractTests(unittest.TestCase):
    def test_manifest_requires_local_recorder_only(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text())
        self.assertEqual(manifest["domain"], "energy_ledger")
        self.assertEqual(manifest["requirements"], [])
        self.assertEqual(manifest["dependencies"], ["recorder"])
        self.assertTrue(manifest["config_flow"])

    def test_translations_have_same_structure_and_placeholders(self):
        def shape(value):
            if isinstance(value, dict):
                return {k: shape(v) for k, v in value.items()}
            import re
            return sorted(re.findall(r"\{([^}]+)\}", value))
        original = json.loads((COMPONENT / "strings.json").read_text())
        for path in (COMPONENT / "translations").glob("*.json"):
            self.assertEqual(shape(json.loads(path.read_text(encoding="utf-8"))), shape(original))

    def test_all_flow_steps_have_translations(self):
        tree = ast.parse((COMPONENT / "config_flow.py").read_text())
        steps = {node.name.removeprefix("async_step_") for node in ast.walk(tree)
                 if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("async_step_")}
        strings = json.loads((COMPONENT / "strings.json").read_text())
        translated = set(strings["config"]["step"]) | set(strings["options"]["step"])
        self.assertEqual(steps, translated)

    def test_english_source_and_translation_are_identical(self):
        read = lambda p: json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(read(COMPONENT / "strings.json"),
                         read(COMPONENT / "translations/en.json"))

    def test_bilingual_guides_link_and_warn_about_monthly_accounting(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        turkish = (ROOT / "README.tr.md").read_text(encoding="utf-8")
        self.assertIn("(README.tr.md)", english)
        self.assertIn("(README.md)", turkish)
        for guide in (english, turkish):
            for value in ("energy_ledger:gas_consumption", "energy_ledger:gas_cost",
                          ".storage", "3,660" if guide == english else "3.660"):
                self.assertIn(value, guide)
        self.assertIn("not measured daily usage", english)
        self.assertIn("gerçek günlük kullanım değil", turkish)

    def test_no_network_or_direct_database_imports(self):
        forbidden = {"requests", "aiohttp", "httpx", "socket", "urllib", "sqlite3", "sqlalchemy"}
        for path in COMPONENT.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                self.assertFalse(forbidden.intersection(name.split(".")[0] for name in names), path.name)

    def test_summary_does_not_create_duplicate_live_statistics(self):
        tree = ast.parse((COMPONENT / "sensor.py").read_text())
        assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)]
        self.assertFalse(any(isinstance(target, ast.Attribute) and target.attr == "_attr_state_class"
                             for node in assignments for target in node.targets))


if __name__ == "__main__":
    unittest.main()
