"""Analytical checks for the illustrative model, not hardware acceptance tests."""

import copy
import csv
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("layout_study", ROOT / "simulation/layout_study.py")
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


class PhysicsTests(unittest.TestCase):
    def assertVectorAlmostEqual(self, actual, expected):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=8)

    def test_weighted_cog_and_translation(self):
        mass, cog = study.weighted_cog([(10, [0, 0, 100]), (30, [400, -40, 500])])
        self.assertEqual(mass, 40)
        self.assertVectorAlmostEqual(cog, [300, -30, 400])
        _, moved = study.weighted_cog([(10, [20, 5, 100]), (30, [420, -35, 500])])
        self.assertVectorAlmostEqual(moved, [320, -25, 400])

    def test_mass_scaling_preserves_cog(self):
        _, a = study.weighted_cog([(2, [1, 2, 3]), (3, [4, 5, 6])])
        _, b = study.weighted_cog([(20, [1, 2, 3]), (30, [4, 5, 6])])
        self.assertVectorAlmostEqual(a, b)

    def test_flat_projection(self):
        self.assertVectorAlmostEqual(study.gravity_projection([20, -30, 700], 0, 0), [20, -30])

    def test_pitch_and_roll_signs(self):
        self.assertVectorAlmostEqual(study.gravity_projection([0, 0, 600], 30, 0), [-600 / math.sqrt(3), 0])
        self.assertVectorAlmostEqual(study.gravity_projection([0, 0, 600], -30, 0), [600 / math.sqrt(3), 0])
        self.assertVectorAlmostEqual(study.gravity_projection([0, 0, 600], 0, 30), [0, -600 / math.sqrt(3)])

    def test_combined_angles_world_vertical_line(self):
        pitch, roll = math.radians(24), math.radians(-13)
        c = [45, -20, 700]
        p = study.gravity_projection(c, 24, -13) + [0]
        # Independent forward transform: the CoG and landing point must have
        # identical world x/y, because the connecting line follows gravity.
        def world(v):
            x, y, z = v
            yr = math.cos(roll) * y - math.sin(roll) * z
            zr = math.sin(roll) * y + math.cos(roll) * z
            return [math.cos(pitch) * x - math.sin(pitch) * zr, yr,
                    math.sin(pitch) * x + math.cos(pitch) * zr]
        self.assertVectorAlmostEqual(world(c)[:2], world(p)[:2])
        self.assertGreater(world(c)[2], world(p)[2])

    def test_seat_rotation_and_inverse(self):
        point, pivot = [30, 40, 950], [0, 0, 500]
        rotated = study.rotate_seat(point, pivot, -30)
        self.assertGreater(rotated[0], point[0])
        self.assertAlmostEqual(math.dist(rotated, pivot), math.dist(point, pivot))
        self.assertVectorAlmostEqual(study.rotate_seat(rotated, pivot, 30), point)

    def test_hull_and_signed_margins(self):
        hull = study.convex_hull([[100, 50], [-100, 50], [100, -50], [-100, -50], [0, 0], [100, 50]])
        self.assertEqual(len(hull), 4)
        self.assertEqual(study.signed_margin([0, 0], hull), 50)
        self.assertEqual(study.signed_margin([100, 0], hull), 0)
        self.assertEqual(study.signed_margin([125, 0], hull), -25)

    def test_degenerate_contacts_and_invalid_mass(self):
        for points in ([[0, 0]], [[0, 0], [1, 0], [2, 0]]):
            with self.assertRaises(ValueError):
                study.convex_hull(points)
        for mass in (-1, float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                study.weighted_cog([(mass, [0, 0, 0])])
        with self.assertRaises(ValueError):
            study.weighted_cog([(0, [0, 0, 0])])

    def test_projection_rejects_vertical_plane_and_below_plane_cog(self):
        for cog, pitch in (([0, 0, 700], 90), ([0, 0, -1], 0)):
            with self.assertRaises(ValueError):
                study.gravity_projection(cog, pitch, 0)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.layout = json.loads((ROOT / "config/layout-study.json").read_text(encoding="utf-8"))
        self.inputs = json.loads((ROOT / "config/design-inputs.json").read_text(encoding="utf-8"))

    def test_load_sources_and_reduced_support_counterexamples(self):
        results = {r["id"]: r for r in study.evaluate(self.layout, self.inputs)}
        device_mass = sum(c["mass_kg"] for c in self.layout["components"])
        self.assertEqual(results["actual_flat"]["total_kg"], device_mass + 70)
        self.assertEqual(results["design_flat"]["total_kg"], device_mass + 100)
        self.assertGreater(results["design_flat"]["signed_margin_mm"], 0)
        for name in ("reduced_contact", "single_side"):
            self.assertLess(results[name]["signed_margin_mm"], 0)

    def test_input_masses_are_not_hardcoded(self):
        modified = copy.deepcopy(self.inputs)
        modified["user_confirmed"]["mass_kg"] = 73
        modified["provisional_analysis"]["design_occupant_mass_kg"] = 105
        original = study.evaluate(self.layout, self.inputs)
        changed = study.evaluate(self.layout, modified)
        self.assertEqual(changed[1]["total_kg"] - original[1]["total_kg"], 3)
        self.assertEqual(changed[2]["total_kg"] - original[2]["total_kg"], 5)

    def test_seat_group_changes_cog_without_changing_mass(self):
        a = copy.deepcopy(self.layout)
        a["scenarios"] = [copy.deepcopy(a["scenarios"][2])]
        flat = study.evaluate(a, self.inputs)[0]
        a["scenarios"][0]["seat_pitch_deg"] = -30
        tilted = study.evaluate(a, self.inputs)[0]
        self.assertEqual(flat["total_kg"], tilted["total_kg"])
        self.assertGreater(tilted["cog_mm"][0], flat["cog_mm"][0])

    def test_bad_config_is_rejected(self):
        mutations = [
            lambda a: a["units"].update(length="m"),
            lambda a: a["components"][0].update(mass_kg=-1),
            lambda a: a["components"][0].update(mass_range_kg=[21, 30]),
            lambda a: a["scenarios"][0].update(pitch_deg=90),
            lambda a: a["scenarios"][0].update(support="missing"),
            lambda a: a["components"][0].update(cog_mm=[0, 0, float("nan")]),
            lambda a: a["components"][0].update(id=a["components"][1]["id"]),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                modified = copy.deepcopy(self.layout)
                mutate(modified)
                with self.assertRaises(ValueError):
                    study.evaluate(modified, self.inputs)

    def test_cli_outputs_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "output"
            process = subprocess.run([sys.executable, str(ROOT / "simulation/layout_study.py"),
                                      "--output", str(output)], cwd=temp, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads((output / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "illustrative_not_validated")
            self.assertEqual(len(result["scenarios"]), len(self.layout["scenarios"]))
            for name in ("layout.svg", "support-cases.svg"):
                self.assertTrue(ET.parse(output / name).getroot().tag.endswith("svg"))
            with (output / "scenarios.csv").open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), len(self.layout["scenarios"]))
            self.assertIn("400 mm", (output / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
