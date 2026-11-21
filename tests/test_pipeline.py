"""Automated validation tests for Agentic Reels Studio (compatible with unittest & pytest)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestAgenticReelsStudio(unittest.TestCase):
    def test_all_skills_have_valid_frontmatter(self):
        skills_dir = ROOT / "skills"
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        self.assertGreaterEqual(len(skill_dirs), 19)
        for d in skill_dirs:
            skill_md = d / "SKILL.md"
            self.assertTrue(skill_md.exists(), f"Missing SKILL.md in {d}")
            text = skill_md.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), f"{skill_md} missing YAML frontmatter")
            fm = text.split("---\n", 2)[1]
            self.assertIn("name:", fm, f"{skill_md} missing name:")
            self.assertIn("description:", fm, f"{skill_md} missing description:")

    def test_projects_catalog_valid(self):
        data = json.loads((ROOT / "brand" / "projects.json").read_text(encoding="utf-8"))
        self.assertEqual(data["brand"]["owner"], "Josué D.")
        self.assertEqual(data["brand"]["alias"], "SadiTLM")
        self.assertGreaterEqual(len(data["projects"]), 3)

    def test_hookscore_and_caption_tools(self):
        res = subprocess.run(
            [
                sys.executable,
                str(ROOT / "skills" / "ig-reel" / "hookscore.py"),
                "--hook",
                "Sin 2da revisión, tu código IA falla.",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        parsed = json.loads(res.stdout)
        self.assertGreater(parsed["score"], 70)

        cap = subprocess.run(
            [
                sys.executable,
                str(ROOT / "skills" / "ig-caption" / "caption.py"),
                "-",
                "--keywords",
                "agentes ia,automatizacion",
                "--json",
            ],
            input="Si tu agente audita su plan, ignora sus propios errores (464 comentarios en HN).\n\nAutomatizacion real con agentes ia.\n\nComenta EGM.\n\n#agentesia #automatizacion #egm\n",
            capture_output=True,
            text=True,
            check=True,
        )
        cap_json = json.loads(cap.stdout)
        self.assertIn("comment a keyword", cap_json["asks"])
        self.assertEqual(cap_json["verdict"], "READY")

    def test_studio_status_and_site_files(self):
        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "studio.py"), "status"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("AGENTIC REELS STUDIO", res.stdout)
        self.assertTrue((ROOT / "site" / "index.html").exists())
        self.assertTrue((ROOT / "site" / "styles.css").exists())
        self.assertTrue((ROOT / "site" / "app.js").exists())


if __name__ == "__main__":
    unittest.main()
