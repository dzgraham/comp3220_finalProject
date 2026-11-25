# Course selection and elective combination checks.

import unittest

from csp.course_selection import (
    find_degree_selections, iter_degree_selections, select_degree_courses
)
from csp.constraints import prerequisites_satisfied
from csp.data import load_courses, load_constraints, load_tracks
from tests.helpers import make_degree_fixture


class TestCourseSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()
        cls.constraints = load_constraints()
        cls.tracks = load_tracks()

    def choose(
        self,
        major,
        track=None,
        approved_courses=None
    ):
        return select_degree_courses(
            major,
            self.courses,
            self.constraints,
            self.tracks,
            track=track,
            approved_courses=approved_courses
        )

    def test_cs_degree_total(self):
        result = self.choose(
            "computer_science",
            "ai_data"
        )

        self.assertEqual(result["total_credits"], 93)
        self.assertEqual(result["level1_credits"], 24)
        self.assertEqual(result["advanced_credits"], 60)
        self.assertEqual(result["foundation_credits"], 9)

    def test_no_duplicates_or_extra_foundations(self):
        codes = self.choose(
            "computer_science"
        )["course_codes"]

        self.assertEqual(
            len(codes),
            len(set(codes))
        )

        self.assertEqual(
            [c for c in codes if c.startswith("FOUN")],
            ["FOUN1014", "FOUN1101", "FOUN1301"]
        )

    def test_prerequisites_in_selection(self):
        codes = self.choose(
            "computer_science"
        )["course_codes"]

        for code in codes:
            self.assertTrue(
                prerequisites_satisfied(
                    code, codes, self.courses
                )
            )

    def test_it_elective_blocks(self):
        result = self.choose(
            "information_technology",
            "web_systems"
        )

        blocks = result["elective_selections"]

        dept = blocks["it_dept_electives"]
        free = blocks["it_free_electives"]

        self.assertEqual(
            sum(self.courses[c]["credits"] for c in dept),
            3
        )

        self.assertEqual(
            sum(self.courses[c]["credits"] for c in free),
            18
        )

        self.assertFalse(set(dept) & set(free))

    def test_se_requires_permission(self):
        with self.assertRaises(ValueError):
            self.choose("software_engineering")

        result = self.choose(
            "software_engineering",
            approved_courses={"COMP3911"}
        )

        self.assertIn(
            "COMP3911",
            result["course_codes"]
        )

        self.assertEqual(result["total_credits"], 93)

    def test_invalid_major_or_track(self):
        with self.assertRaises(ValueError):
            self.choose("unknown_major")

        with self.assertRaises(ValueError):
            self.choose(
                "computer_science",
                "invalid_track"
            )


class TestSelectionSearch(unittest.TestCase):
    def setUp(self):
        self.courses, self.constraints, self.tracks = make_degree_fixture()

    def test_selection_list_has_alternatives_without_duplicates(self):
        choices = find_degree_selections(
            "test", self.courses, self.constraints, self.tracks, "preferred", years=1
        )
        self.assertIsInstance(choices, list)
        self.assertEqual(len(choices), 2)
        unique_choices = set()
        for choice in choices:
            unique_choices.add(tuple(sorted(choice["course_codes"])))
        self.assertEqual(len(unique_choices), 2)
        self.assertEqual(iter_degree_selections(
            "test", self.courses, self.constraints, self.tracks, "preferred", years=1
        ), choices)

    def test_collecting_all_selections_reports_budget_limit(self):
        with self.assertRaisesRegex(ValueError, "Search limit reached"):
            find_degree_selections(
                "test", self.courses, self.constraints, self.tracks,
                "preferred", years=1, max_nodes=1
            )


if __name__ == "__main__":
    unittest.main()
