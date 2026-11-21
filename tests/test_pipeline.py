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
        backdrops_dir = ROOT / "brand" / "assets" / "backdrops"
        for name in ("porsche-gt3-rain.jpg", "neon-alley-coupe.jpg", "ferrari-crimson-dock.jpg", "skyline-overpass.jpg"):
            self.assertTrue((backdrops_dir / name).exists())
        bandida_dir = ROOT / "brand" / "assets" / "chibi-bandida"
        for i in range(1, 13):
            self.assertTrue((bandida_dir / f"pose_{i:02d}.png").exists())

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

    def test_sprite_prep_removes_trapped_side_white_hole_keeps_center(self):
        from PIL import Image, ImageDraw
        sys.path.insert(0, str(ROOT / "scripts"))
        from sprite_prep import remove_trapped_white_holes

        img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # Character body silhouette in (10,10)-(90,90)
        d.rectangle([10, 10, 90, 90], fill=(30, 30, 30, 255))
        # Protected center white shirt/eye
        d.rectangle([45, 35, 55, 45], fill=(255, 255, 255, 255))
        # Trapped pure-white pocket on far-left hair edge
        d.rectangle([14, 15, 22, 25], fill=(255, 255, 255, 255))

        cleaned = remove_trapped_white_holes(img)
        self.assertEqual(cleaned.getpixel((18, 20))[3], 0)
        self.assertEqual(cleaned.getpixel((50, 40))[3], 255)

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

    def test_fal_studio_check_and_dry_runs(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("FAL_KEY=", env_example)
        self.assertTrue((ROOT / "skills" / "fal-ai-video" / "SKILL.md").exists())
        self.assertTrue((ROOT / "requirements.txt").exists())

        chk = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "fal_studio.py"), "check", "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        chk_data = json.loads(chk.stdout)
        self.assertIn(chk_data["fal_key_state"], ("Present", "Absent", "Inaccessible"))
        self.assertFalse(chk_data["api_call_made"])
        self.assertEqual(
            chk_data["endpoints"]["motion_control"]["v3-pro"]["endpoint"],
            "fal-ai/kling-video/v3/pro/motion-control",
        )
        self.assertEqual(
            chk_data["endpoints"]["video_bg_removal"]["endpoint"],
            "bria/video/background-removal/v3",
        )

        # Dry-run motion transfer against existing local Bandida pose + sample mp4 (0 network calls)
        sample_video = ROOT / "pipeline" / "05_ready_to_post" / "20261121-bandida-9mm-glitch" / "reel.mp4"
        bandida_pose = ROOT / "brand" / "assets" / "chibi-bandida" / "pose_01.png"
        if sample_video.exists() and bandida_pose.exists():
            mt = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "fal_studio.py"),
                    "motion-transfer",
                    "--character",
                    str(bandida_pose),
                    "--dance",
                    str(sample_video),
                    "--model",
                    "v3-pro",
                    "--green-screen",
                    "--out",
                    "/tmp/test_motion_out.mp4",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            mt_data = json.loads(mt.stdout)
            self.assertTrue(mt_data["dry_run"])
            self.assertEqual(mt_data["arguments"]["character_orientation"], "video")
            self.assertIn("#00FF00", mt_data["arguments"]["prompt"])
            self.assertGreater(mt_data["estimated_cost_usd"], 0)

            bg = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "fal_studio.py"),
                    "remove-bg-video",
                    "--video",
                    str(sample_video),
                    "--out",
                    "/tmp/test_alpha_out.webm",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            bg_data = json.loads(bg.stdout)
            self.assertEqual(bg_data["arguments"]["background_color"], "Transparent")
            self.assertEqual(bg_data["arguments"]["output_container_and_codec"], "webm_vp9")

    def test_live2d_rig_assets_pose_tracker_and_colab_notebook(self):
        rig_dir = ROOT / "brand" / "assets" / "bandida-rig"
        expected_parts = (
            "head_smirk.png",
            "head_bang.png",
            "hair_back.png",
            "torso.png",
            "skirt.png",
            "tie.png",
            "backpack.png",
            "arm_upper.png",
            "arm_lower.png",
            "arm_bang.png",
            "thigh.png",
            "leg_left.png",
            "leg_right.png",
        )
        for fname in expected_parts:
            self.assertTrue((rig_dir / fname).exists(), f"Missing Live2D rig asset: {fname}")

        pt_help = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "pose_track.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("MediaPipe Pose", pt_help.stdout)

        nb_path = ROOT / "notebooks" / "bandida_colab_motion_t4.ipynb"
        self.assertTrue(nb_path.exists())
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        self.assertEqual(nb.get("nbformat"), 4)
        self.assertGreaterEqual(len(nb.get("cells", [])), 5)


if __name__ == "__main__":
    unittest.main()
