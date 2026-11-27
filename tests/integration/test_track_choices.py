# Independent specialization choices and math eligibility across all search paths.

import unittest

from csp.constraints import build_semesters
from csp.course_selection import (
    find_degree_selections, select_degree_courses, validate_degree_selection
)
from csp.planner import plan_degree, verify_degree_plan
from tests.helpers import make_course, make_degree_fixture


class TestTrackChoices(unittest.TestCase):
    def setUp(self):
        self.courses, self.constraints, self.tracks = make_degree_fixture()
        self.tracks["majors"]["test"]["elective_blocks"] = []
        self.courses["MATH2001"] = make_course(2, ("2",), "COMP1001", "WED")
        self.courses["STAT2001"] = make_course(2, ("2",), "COMP1001", "THU")
        self.tracks["math_tracks"] = {
            "statistics": {"preferred_electives": ["STAT2001"]}
        }

    def plan(self, **options):
        return plan_degree("test", self.courses, self.constraints, self.tracks,
                           years=1, **options)

    def test_default_excludes_math_even_if_computing_track_prefers_it(self):
        self.tracks["tracks"]["preferred"]["preferred_electives"] = ["STAT2001", "MATH2001"]
        result = self.plan(track="preferred")
        self.assertTrue(result["complete"])
        self.assertIn("COMP2002", result["selected_courses"])
        self.assertFalse(any(c.startswith(("MATH", "STAT")) for c in result["selected_courses"]))

    def test_math_track_alone_prioritizes_its_elective(self):
        result = self.plan(math_track="statistics")
        self.assertTrue(result["complete"])
        self.assertIsNone(result["track"])
        self.assertEqual(result["math_track"], "statistics")
        self.assertIn("STAT2001", result["selected_courses"])
        self.assertTrue(verify_degree_plan(
            "test", result["selected_courses"], result["plan"], self.courses,
            self.constraints, self.tracks, build_semesters(1), math_track="statistics"
        )["valid"])

    def test_math_prerequisites_are_only_available_with_math_opt_in(self):
        self.courses["COMP2002"]["prerequisites"] = "MATH1001"
        self.courses["MATH1001"] = make_course(terms=("1",), day="FRI")
        self.constraints["university_rules"].update(
            total_credits_for_degree=9, level_1_credits_required=6
        )
        denied = self.plan()
        self.assertFalse(denied["complete"])
        self.assertNotIn("COMP2002", denied["selected_courses"])
        self.assertNotIn("MATH1001", denied["selected_courses"])
        allowed = self.plan(math_track="statistics")
        self.assertTrue(allowed["complete"])
        self.assertIn("MATH1001", allowed["selected_courses"])

    def test_partial_fallback_cannot_reintroduce_math(self):
        del self.courses["COMP2001"]
        del self.courses["COMP2002"]
        result = self.plan()
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["verified"])
        self.assertEqual(result["selected_courses"], ["COMP1001"])
        self.assertTrue(self.plan(math_track="statistics")["complete"])

    def test_selection_validation_rejects_math_without_a_math_track(self):
        for code in ("MATH2001", "STAT2001"):
            with self.subTest(code=code):
                selected = ["COMP1001", code]
                denied = validate_degree_selection(
                    "test", selected, self.courses, self.constraints, self.tracks
                )
                self.assertFalse(denied["valid"])
                self.assertIn("Math courses require a math track", "; ".join(denied["errors"]))
                allowed = validate_degree_selection(
                    "test", selected, self.courses, self.constraints, self.tracks,
                    math_track="statistics"
                )
                self.assertTrue(allowed["valid"], allowed["errors"])
                verified = verify_degree_plan(
                    "test", selected, {"Y1S1": ["COMP1001"], "Y1S2": [code]},
                    self.courses, self.constraints, self.tracks, build_semesters(1)
                )
                self.assertFalse(verified["valid"])

    def test_selection_helpers_propagate_math_choice(self):
        selection = select_degree_courses(
            "test", self.courses, self.constraints, self.tracks, math_track="statistics"
        )
        self.assertIn("STAT2001", selection["course_codes"])
        self.assertEqual(selection["math_track"], "statistics")
        choices = find_degree_selections("test", self.courses, self.constraints, self.tracks)
        self.assertFalse(any(c.startswith(("MATH", "STAT"))
                             for choice in choices for c in choice["course_codes"]))
        allowed = find_degree_selections(
            "test", self.courses, self.constraints, self.tracks, math_track="statistics"
        )
        self.assertTrue(any("STAT2001" in choice["course_codes"] for choice in allowed))

    def test_invalid_math_track_is_rejected_before_fallback(self):
        with self.assertRaisesRegex(ValueError, "Unknown math track"):
            self.plan(math_track="unknown")


if __name__ == "__main__":
    unittest.main()
