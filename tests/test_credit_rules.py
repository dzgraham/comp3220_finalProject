
import unittest
from copy import deepcopy

from csp.data_loader import load_courses, load_constraints
from csp.credit_rules import (
    calculate_semester_credits,
    get_foundation_codes,
    semester_load_valid
)


class TestCreditRules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()
        cls.constraints = load_constraints()

    def test_credit_calculation(self):
        codes = ["COMP1126", "COMP1127"]

        self.assertEqual(
            calculate_semester_credits(codes, self.courses),
            6
        )

    def test_maximum_credits_allowed(self):
        codes = [
            "COMP1126", "COMP1127", "COMP1161",
            "COMP1210", "COMP1220", "COMP2130"
        ]

        self.assertTrue(
            semester_load_valid(
                codes, self.courses, self.constraints
            )
        )

    def test_credit_overload(self):
        codes = [
            "COMP1126", "COMP1127", "COMP1161",
            "COMP1210", "COMP1220", "COMP2130",
            "COMP2140"
        ]

        self.assertFalse(
            semester_load_valid(
                codes, self.courses, self.constraints
            )
        )

    def test_foundation_codes(self):
        codes = get_foundation_codes(self.constraints)

        self.assertIn("FOUN1014", codes)
        self.assertIn("FOUN1019", codes)
        self.assertIn("FOUN1101", codes)
        self.assertIn("FOUN1301", codes)

    def test_two_foundation_courses(self):
        codes = ["FOUN1014", "FOUN1101"]

        self.assertTrue(
            semester_load_valid(
                codes, self.courses, self.constraints
            )
        )

    def test_three_foundation_courses(self):
        codes = [
            "FOUN1014", "FOUN1101", "FOUN1301"
        ]

        self.assertFalse(
            semester_load_valid(
                codes, self.courses, self.constraints
            )
        )

    def test_duplicate_course(self):
        codes = ["COMP1126", "COMP1126"]

        self.assertFalse(
            semester_load_valid(
                codes, self.courses, self.constraints
            )
        )

    def test_unknown_course(self):
        with self.assertRaises(ValueError):
            calculate_semester_credits(
                ["INVALID9999"], self.courses
            )

    def test_minimum_only_on_final_check(self):
        rules = deepcopy(self.constraints)

        rules["registration_limits"]["part_1"][
            "min_credits_per_semester"
        ] = 6

        codes = ["COMP1126"]

        # Partial CSP assignments can be under the minimum.
        self.assertTrue(
            semester_load_valid(
                codes, self.courses, rules
            )
        )

        # Completed semesters must meet the minimum.
        self.assertFalse(
            semester_load_valid(
                codes, self.courses, rules,
                enforce_minimum=True
            )
        )


if __name__ == "__main__":
    unittest.main()
