# Complete degree plans, command-line usage, and old import paths.

import importlib
import subprocess
import sys
import unittest
from pathlib import Path

from csp.constraints import (
    build_semesters, check_semester_timetable, prerequisites_satisfied
)
from csp.data import load_courses
from csp_solver import generate_full_degree_plan


class TestDatasetIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()

    def test_complete_93_credit_ai_data_degree(self):
        result = generate_full_degree_plan("computer_science", "ai_data", max_nodes=2000)
        self.assertTrue(result["success"], result["reason"])
        self.assertTrue(result["complete"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["scheduled_credits"], 93)
        self.assertEqual(sum(result["semester_credits"].values()), 93)
        scheduled = [c for codes in result["plan"].values() for c in codes]
        self.assertCountEqual(scheduled, result["selected_courses"])
        self.assertEqual(len(scheduled), len(set(scheduled)))
        # Check real ordering and timetable rules independently of search state.
        prior = set()
        for semester in build_semesters(3):
            codes = result["plan"].get(semester["id"], [])
            for code in codes:
                self.assertTrue(prerequisites_satisfied(code, prior, self.courses))
            self.assertTrue(check_semester_timetable(codes, self.courses, allow_unknown=True)["valid"])
            prior.update(codes)
        self.assertEqual(result["status"], "tentative")
        self.assertTrue(set(result["tentative_courses"]).issuperset({"FOUN1014", "FOUN1101", "FOUN1301"}))

    def test_command_line_defaults_to_a_complete_degree(self):
        script = Path(__file__).resolve().parents[2] / "csp_solver.py"
        result = subprocess.run(
            [sys.executable, "-B", str(script)],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Major: computer_science", result.stdout)
        self.assertIn("Total scheduled credits: 93", result.stdout)

    def test_command_line_rejects_course_lists(self):
        script = Path(__file__).resolve().parents[2] / "csp_solver.py"
        result = subprocess.run(
            [sys.executable, "-B", str(script), "--courses", "COMP1126"],
            capture_output=True, text=True, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments: --courses", result.stderr)

    def test_command_line_shows_all_semesters_when_summer_is_enabled(self):
        script = Path(__file__).resolve().parents[2] / "csp_solver.py"
        result = subprocess.run(
            [sys.executable, "-B", str(script), "--include-summer"],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for year in range(1, 4):
            for term in range(1, 4):
                self.assertIn(f"Y{year}S{term} (", result.stdout)
        self.assertIn("Total scheduled credits: 93", result.stdout)

    def test_command_line_displays_the_automatic_partial_fallback(self):
        script = Path(__file__).resolve().parents[2] / "csp_solver.py"
        result = subprocess.run(
            [sys.executable, "-B", str(script), "--years", "1", "--max-nodes", "200"],
            capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Status: partial", result.stdout)
        self.assertIn("Total scheduled credits:", result.stdout)
        self.assertIn("Credits still needed:", result.stdout)
        self.assertIn("Missing compulsory courses:", result.stdout)

    def test_original_import_paths_are_compatible(self):
        for old, new, function in [
            ("data_loader", "data", "load_courses"),
            ("degree_requirements", "data", "get_degree_blueprint"),
            ("credit_rules", "constraints", "semester_load_valid"),
            ("prerequisites", "constraints", "prerequisites_satisfied"),
            ("semester_rules", "constraints", "build_semesters"),
            ("timetable_clash", "constraints", "parse_schedule"),
            ("selection_feasibility", "constraints", "find_overloaded_term_clique"),
            ("full_degree_planner", "planner", "generate_full_degree_plan")
        ]:
            with self.subTest(module=old):
                self.assertIs(getattr(importlib.import_module(f"csp.{old}"), function),
                              getattr(importlib.import_module(f"csp.{new}"), function))


if __name__ == "__main__":
    unittest.main()
