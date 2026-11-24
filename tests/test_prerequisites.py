
import unittest

from csp.data_loader import load_courses
from csp.prerequisites import (
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


if __name__ == "__main__":
    unittest.main()
