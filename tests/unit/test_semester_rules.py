# Course offerings and semester domains.

import unittest

from csp.data import load_courses
from csp.constraints import (
    build_semesters,
    get_offered_terms,
    is_course_offered,
    get_course_domain
)


class TestSemesterRules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()

    def test_standard_semesters(self):
        semesters = build_semesters(years=3)

        self.assertEqual(len(semesters), 6)

        self.assertEqual(
            [s["id"] for s in semesters],
            [
                "Y1S1", "Y1S2",
                "Y2S1", "Y2S2",
                "Y3S1", "Y3S2"
            ]
        )

    def test_summer_semesters(self):
        semesters = build_semesters(
            years=2,
            include_summer=True
        )

        self.assertEqual(len(semesters), 6)
        self.assertEqual(semesters[2]["id"], "Y1S3")

    def test_semester_one_course(self):
        self.assertEqual(
            get_offered_terms("COMP2130", self.courses),
            ("1",)
        )

        self.assertTrue(
            is_course_offered("COMP2130", 1, self.courses)
        )

        self.assertFalse(
            is_course_offered("COMP2130", 2, self.courses)
        )

    def test_semester_two_course(self):
        self.assertTrue(
            is_course_offered("COMP2171", 2, self.courses)
        )

        self.assertFalse(
            is_course_offered("COMP2171", 1, self.courses)
        )

    def test_summer_course(self):
        self.assertTrue(
            is_course_offered("COMP3911", 3, self.courses)
        )

    def test_course_domain(self):
        semesters = build_semesters(years=3)

        domain = get_course_domain(
            "COMP2130",
            semesters,
            self.courses
        )

        self.assertEqual(
            [s["id"] for s in domain],
            ["Y1S1", "Y2S1", "Y3S1"]
        )

    def test_unknown_course(self):
        with self.assertRaises(ValueError):
            get_offered_terms("INVALID9999", self.courses)

    def test_invalid_term(self):
        with self.assertRaises(ValueError):
            is_course_offered("COMP2130", 4, self.courses)


if __name__ == "__main__":
    unittest.main()
