# Individual, nested, and permission prerequisites.

import unittest

from csp.data import load_courses
from csp.constraints import (
    prerequisites_satisfied,
    split_conditions
)


class TestPrerequisites(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()

    def test_nested_conditions(self):
        result = split_conditions(
            "COMP1161; OR(COMP1210; MATH1152)"
        )

        self.assertEqual(
            result,
            ["COMP1161", "OR(COMP1210; MATH1152)"]
        )

    def test_and_requires_both(self):
        self.assertFalse(
            prerequisites_satisfied(
                "COMP1161",
                {"COMP1126"},
                self.courses
            )
        )

        self.assertTrue(
            prerequisites_satisfied(
                "COMP1161",
                {"COMP1126", "COMP1127"},
                self.courses
            )
        )

    def test_or_accepts_either(self):
        self.assertFalse(
            prerequisites_satisfied(
                "COMP2201",
                set(),
                self.courses
            )
        )

        self.assertTrue(
            prerequisites_satisfied(
                "COMP2201",
                {"MATH1152"},
                self.courses
            )
        )

    def test_nested_and_or(self):
        self.assertFalse(
            prerequisites_satisfied(
                "COMP2190",
                {"COMP1126", "COMP1127", "COMP1161"},
                self.courses
            )
        )

        self.assertTrue(
            prerequisites_satisfied(
                "COMP2190",
                {
                    "COMP1126",
                    "COMP1127",
                    "COMP1161",
                    "MATH1152"
                },
                self.courses
            )
        )

    def test_permission(self):
        self.assertFalse(
            prerequisites_satisfied(
                "COMP3911",
                set(),
                self.courses
            )
        )

        self.assertTrue(
            prerequisites_satisfied(
                "COMP3911",
                set(),
                self.courses,
                {"COMP3911"}
            )
        )

    def test_additional_comp_credits(self):
        self.assertFalse(
            prerequisites_satisfied(
                "COMP3901",
                {"COMP2140", "COMP2211"},
                self.courses
            )
        )

        self.assertTrue(
            prerequisites_satisfied(
                "COMP3901",
                {
                    "COMP2140",
                    "COMP2211",
                    "COMP2130",
                    "COMP2201"
                },
                self.courses
            )
        )

    def test_prerequisite_outside_catalogue(self):
        courses = {
            "MATH3410": {"prerequisites": "MATH2410"},
            "COMP2201": {"prerequisites": "OR(MATH2410; COMP1210)"},
            "COMP1210": {"prerequisites": "NONE"}
        }
        cases = [
            ("MATH3410", set(), False),
            ("MATH3410", {"MATH2410"}, True),
            ("COMP2201", set(), False),
            ("COMP2201", {"MATH2410"}, True),
            ("COMP2201", {"COMP1210"}, True)
        ]

        for code, completed, expected in cases:
            with self.subTest(code=code, completed=completed):
                self.assertEqual(
                    prerequisites_satisfied(code, completed, courses),
                    expected
                )

    def test_unrecognized_condition(self):
        courses = {"MATH3410": {"prerequisites": "UNSUPPORTED_RULE"}}

        with self.assertRaisesRegex(ValueError, "Unrecognized condition"):
            prerequisites_satisfied("MATH3410", set(), courses)


if __name__ == "__main__":
    unittest.main()
