# Semester assignment checks using the project's actual course catalogue.

import unittest
from copy import deepcopy

from csp.data import load_courses, load_constraints
from csp.constraints import build_semesters
from csp.solver import solve_degree_plan


class TestSemesterAssignment(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()
        cls.constraints = load_constraints()

    def solve(self, requested, years=3, **kwargs):
        return solve_degree_plan(
            requested,
            self.courses,
            self.constraints,
            semesters=build_semesters(years=years),
            **kwargs
        )

    def test_prerequisite_order(self):
        result = self.solve([
            "COMP1126",
            "COMP1127",
            "COMP1161",
            "COMP2130"
        ])

        self.assertTrue(result["success"])

        self.assertEqual(
            result["plan"]["Y1S1"],
            ["COMP1126", "COMP1127"]
        )

        self.assertEqual(
            result["plan"]["Y1S2"],
            ["COMP1161"]
        )

        self.assertEqual(
            result["plan"]["Y2S1"],
            ["COMP2130"]
        )

    def test_missing_prerequisites(self):
        result = self.solve(["COMP1161"])

        self.assertFalse(result["success"])

    def test_clash_spreads_courses(self):
        completed = {
            "COMP1126",
            "COMP1127",
            "COMP1161"
        }

        result = self.solve(
            ["COMP2130", "INFO2180"],
            years=2,
            completed_courses=completed
        )

        self.assertTrue(result["success"])

        self.assertIn(
            "COMP2130",
            result["plan"]["Y1S1"]
        )

        self.assertIn(
            "INFO2180",
            result["plan"]["Y2S1"]
        )

    def test_impossible_timetable(self):
        completed = {
            "COMP1126",
            "COMP1127",
            "COMP1161"
        }

        result = self.solve(
            ["COMP2130", "INFO2180"],
            years=1,
            completed_courses=completed
        )

        self.assertFalse(result["success"])
        self.assertGreater(result["backtracks"], 0)

    def test_unknown_timetable(self):
        self.courses = deepcopy(self.courses)
        self.courses["COMP3191"]["schedule"] = '[{"day": "TBA"}]'

        result = self.solve(
            ["COMP3191"],
            completed_courses={"COMP2190"}
        )

        self.assertTrue(result["success"])

        self.assertEqual(
            result["tentative_courses"],
            ["COMP3191"]
        )

        strict = self.solve(
            ["COMP3191"],
            completed_courses={"COMP2190"},
            allow_unknown=False
        )

        self.assertFalse(strict["success"])

    def test_foundation_year(self):
        result = self.solve(["FOUN1014"])

        self.assertTrue(result["success"])

        self.assertEqual(
            list(result["plan"]),
            ["Y1S1"]
        )

    def test_credit_limit(self):
        modified = deepcopy(self.constraints)

        modified["registration_limits"]["part_1"][
            "max_credits_per_semester"
        ] = 3

        completed = {
            "COMP1126", "COMP1127",
            "COMP1161", "COMP1210"
        }

        result = solve_degree_plan(
            ["COMP2130", "COMP2201"],
            self.courses,
            modified,
            semesters=build_semesters(years=1),
            completed_courses=completed
        )

        self.assertFalse(result["success"])

    def test_completed_courses_not_rescheduled(self):
        result = self.solve(
            ["COMP1126", "COMP1161"],
            completed_courses={
                "COMP1126",
                "COMP1127"
            }
        )

        self.assertTrue(result["success"])

        scheduled = sum(
            result["plan"].values(), []
        )

        self.assertNotIn(
            "COMP1126",
            scheduled
        )

    def test_duplicate_courses(self):
        with self.assertRaises(ValueError):
            self.solve([
                "COMP1126",
                "COMP1126"
            ])


if __name__ == "__main__":
    unittest.main()
