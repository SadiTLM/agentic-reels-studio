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

    def test_muestras_remixer_skill_and_assets_exist(self):
        skills_dir = ROOT / "skills"
        skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
        self.assertGreaterEqual(len(skill_dirs), 21)
        self.assertTrue((skills_dir / "ig-muestras-remixer" / "SKILL.md").exists())
        chibi_dir = ROOT / "brand" / "assets" / "chibi-racer"
        for i in range(1, 5):
            self.assertTrue((chibi_dir / f"pose_{i:02d}.png").exists())

    def test_sprite_prep_preserves_interior_white_and_removes_exterior_bg(self):
        import tempfile
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            src = td_path / "sample.png"
            out = td_path / "cut.png"
            # White exterior background, dark outline box, pure white interior eye
            img = Image.new("RGB", (80, 80), (255, 255, 255))
            d = ImageDraw.Draw(img)
            d.rectangle([20, 20, 60, 60], fill=(20, 20, 20))
            d.rectangle([32, 32, 48, 48], fill=(255, 255, 255))
            img.save(src)

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "sprite_prep.py"), "cutout", str(src), str(out), "--bg", "white"],
                check=True,
                capture_output=True,
                text=True,
            )
            with Image.open(out) as cut:
                self.assertEqual(cut.mode, "RGBA")
                # Corners (padding) must be fully transparent; center white interior stays opaque
                self.assertEqual(cut.getpixel((0, 0))[3], 0)
                self.assertEqual(cut.getpixel((cut.width // 2, cut.height // 2))[3], 255)

    def test_audio_sync_dual_export_creates_both_mp4s_and_guide(self):
        import tempfile

        sample_video = ROOT / "pipeline" / "05_ready_to_post" / "20261121-cuello-botella-agentes" / "reel.mp4"
        if not sample_video.exists():
            self.skipTest("Sample reel.mp4 not present")

        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "sync_out"
            res = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "audio_sync.py"),
                    "dual-export",
                    str(sample_video),
                    "--out",
                    str(out_dir),
                    "--song",
                    "TAKE ME",
                    "--artist",
                    "D A N N Y",
                    "--start",
                    "14.0",
                    "--bpm",
                    "115",
                    "--cuts",
                    "0.0:Hook,3.6:Drop",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(res.stdout)
            self.assertEqual(payload["start_timestamp"], "0:14")
            self.assertTrue((out_dir / "reel_con_audio.mp4").exists())
            self.assertTrue((out_dir / "reel_sin_sonido.mp4").exists())
            self.assertTrue((out_dir / "AUDIO_SYNC.md").exists())
            self.assertTrue((out_dir / "audio_sync.json").exists())
            guide_text = (out_dir / "AUDIO_SYNC.md").read_text(encoding="utf-8")
            self.assertIn("0:14", guide_text)
            self.assertIn("TAKE ME", guide_text)


if __name__ == "__main__":
    unittest.main()
