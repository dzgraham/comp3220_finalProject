# Known clashes, missing times, and semester halves.

import json
import unittest
from copy import deepcopy

from csp.constraints import (
    check_semester_timetable, find_overloaded_term_clique, parse_schedule
)
from csp.data import load_courses
from tests.helpers import make_course


class TestTimetable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.courses = load_courses()

    def test_overlap(self):
        result = check_semester_timetable(
            ["COMP2130", "INFO2180"],
            self.courses
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(
            result["conflicts"][0]["day"],
            "TUE"
        )

    def test_no_overlap(self):
        result = check_semester_timetable(
            ["COMP1210", "COMP1220"],
            self.courses
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "confirmed")

    def test_adjacent_not_overlap(self):
        result = check_semester_timetable(
            ["COMP1161", "COMP1210"],
            self.courses
        )

        self.assertTrue(result["valid"])

    def test_different_halves(self):
        result = check_semester_timetable(
            ["COMP1126", "COMP1127"],
            self.courses
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "confirmed")

    def test_half_vs_full_overlaps(self):
        result = check_semester_timetable(
            ["COMP1126", "COMP2140"],
            self.courses
        )

        self.assertFalse(result["valid"])
        self.assertTrue(result["conflicts"])

    def test_tba_requires_attention(self):
        courses = deepcopy(self.courses)
        courses["COMP3191"]["schedule"] = json.dumps([{"day": "TBA"}])

        result = check_semester_timetable(
            ["COMP3191"],
            courses
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "tentative")

        self.assertEqual(
            result["unknown_courses"],
            ["COMP3191"]
        )

        # Allow it only as a tentative assignment.
        result = check_semester_timetable(
            ["COMP3191"],
            courses,
            allow_unknown=True
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "tentative")

    def test_empty_schedule_is_unknown(self):
        result = check_semester_timetable(
            ["FOUN1014"],
            self.courses
        )

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["unknown_courses"],
            ["FOUN1014"]
        )

    def test_bad_interval(self):
        bad_schedule = json.dumps([
            {
                "day": "TUE",
                "start": "15:00",
                "end": "14:00"
            }
        ])

        with self.assertRaises(ValueError):
            parse_schedule(bad_schedule)

    def test_unknown_course(self):
        with self.assertRaises(ValueError):
            check_semester_timetable(
                ["INVALID9999"],
                self.courses
            )

    def test_unknown_does_not_hide_real_clash(self):
        courses = deepcopy(self.courses)
        courses["COMP3191"]["schedule"] = json.dumps([{"day": "TBA"}])

        result = check_semester_timetable(
            ["COMP3191", "COMP2130", "INFO2180"],
            courses,
            allow_unknown=True
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "conflict")

        self.assertEqual(
            result["unknown_courses"],
            ["COMP3191"]
        )

    def test_later_meeting_can_clash_with_unknown_times(self):
        known = [
            {"day": "WED", "start": "10:00", "end": "12:00"},
            {"day": "TUE", "start": "11:30", "end": "12:30"}
        ]
        schedules = [
            known,
            [{"day": "TBA"}] + known,
            known + [{"day": "TBA"}]
        ]

        for schedule in schedules:
            with self.subTest(schedule=schedule):
                courses = deepcopy(self.courses)
                courses["COMP3191"]["schedule"] = json.dumps(schedule)

                result = check_semester_timetable(
                    ["COMP3191", "COMP2130"],
                    courses,
                    allow_unknown=True
                )

                self.assertFalse(result["valid"])
                self.assertEqual(result["status"], "conflict")
                self.assertEqual(result["conflicts"], [{
                    "course_a": "COMP3191",
                    "course_b": "COMP2130",
                    "day": "TUE",
                    "start": "11:30",
                    "end": "12:00"
                }])
                self.assertEqual(
                    result["unknown_courses"],
                    ["COMP3191"] if len(schedule) > len(known) else []
                )

    def test_clique_pruning_respects_semester_halves(self):
        courses = {f"COMP100{i}": make_course() for i in range(4)}
        self.assertIsNotNone(find_overloaded_term_clique(list(courses), courses, years=3))
        courses["COMP1000"]["half"] = "H1"
        courses["COMP1001"]["half"] = "H2"
        self.assertIsNone(find_overloaded_term_clique(list(courses), courses, years=3))


if __name__ == "__main__":
    unittest.main()
