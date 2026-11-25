# A full-degree failure should preserve useful work without relaxing the rules.

import unittest

from csp.constraints import build_semesters, validate_semester_plan
from csp.planner import plan_degree
from tests.helpers import make_course, make_degree_fixture


class TestPartialFallback(unittest.TestCase):
    def setUp(self):
        self.courses, self.constraints, self.tracks = make_degree_fixture()

    def plan(self, **options):
        return plan_degree(
            "test", self.courses, self.constraints, self.tracks,
            years=1, **options
        )

    def check_partial(self, result, allow_unknown=True):
        self.assertFalse(result["success"])
        self.assertFalse(result["complete"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["plan"])
        self.assertTrue(result["unsatisfied_requirements"])
        checked = validate_semester_plan(
            result["plan"], self.courses, self.constraints, build_semesters(1),
            allow_unknown=allow_unknown, expected_courses=result["selected_courses"]
        )
        self.assertTrue(checked["valid"], checked["errors"])
        total = 0
        for codes in result["plan"].values():
            for code in codes:
                total += self.courses[code]["credits"]
        self.assertEqual(result["scheduled_credits"], total)
        self.assertEqual(result["selected_credits"], total)

    def remove_electives(self):
        del self.courses["COMP2001"]
        del self.courses["COMP2002"]

    def test_credit_shortfall_returns_available_courses(self):
        self.remove_electives()
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["scheduled_credits"], 3)
        self.assertEqual(result["credit_shortfall"], 3)
        self.assertEqual(result["missing_credits"], {
            "level1": 0, "advanced": 3, "foundation": 0
        })
        self.assertEqual(result["missing_courses"], [])

    def test_unavoidable_clash_excludes_one_of_the_courses(self):
        self.courses = {"COMP1001": make_course(), "COMP1002": make_course()}
        self.constraints["university_rules"].update(
            level_1_credits_required=6, level_2_3_credits_required=0,
            min_in_faculty_level_1_credits=6, min_in_faculty_level_2_3_credits=0
        )
        self.tracks["majors"]["test"]["level1_required"] = list(self.courses)
        self.tracks["majors"]["test"]["elective_blocks"] = []
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(len(result["selected_courses"]), 1)
        self.assertEqual(len(result["missing_courses"]), 1)
        self.assertEqual(result["scheduled_credits"], 3)

    def test_fallback_undoes_a_course_to_fit_a_better_combination(self):
        self.courses = {
            "COMP1001": make_course(),
            "COMP1002": make_course(),
            "COMP1003": make_course(day="TUE")
        }
        # The first course blocks both later courses; the later two fit together.
        self.courses["COMP1001"]["schedule"].append({
            "day": "TUE", "start": "09:00", "end": "10:00"
        })
        self.constraints["university_rules"].update(
            total_credits_for_degree=12, level_1_credits_required=9,
            min_in_faculty_level_1_credits=9
        )
        self.tracks["majors"]["test"]["level1_required"] = list(self.courses)
        result = self.plan()
        self.check_partial(result)
        self.assertCountEqual(result["selected_courses"], ["COMP1002", "COMP1003"])
        self.assertEqual(result["scheduled_credits"], 6)

    def test_fallback_respects_the_semester_credit_cap(self):
        self.remove_electives()
        self.courses["COMP1002"] = make_course(day="TUE")
        self.constraints["university_rules"].update(
            total_credits_for_degree=9, level_1_credits_required=6,
            min_in_faculty_level_1_credits=6
        )
        self.constraints["registration_limits"]["part_1"]["max_credits_per_semester"] = 3
        self.tracks["majors"]["test"]["level1_required"] = list(self.courses)
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["scheduled_credits"], 3)

    def test_missing_compulsory_course_is_reported(self):
        self.courses["COMP1001"]["semesters"] = ["3"]
        self.courses["COMP2002"]["prerequisites"] = "NONE"
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["selected_courses"], ["COMP2002"])
        self.assertEqual(result["missing_courses"], ["COMP1001"])
        self.assertEqual(result["missing_credits"]["level1"], 3)

    def test_dependent_cannot_follow_a_prerequisite_in_the_same_semester(self):
        del self.courses["COMP2002"]
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["selected_courses"], ["COMP1001"])
        self.assertNotIn("COMP2001", result["selected_courses"])

    def test_missing_permission_is_not_bypassed(self):
        self.courses["COMP1001"]["prerequisites"] = "HEAD_PERMISSION"
        self.courses["COMP2002"]["prerequisites"] = "NONE"
        result = self.plan()
        self.check_partial(result)
        self.assertNotIn("COMP1001", result["selected_courses"])
        self.assertNotIn("COMP2001", result["selected_courses"])
        self.assertIn("COMP1001", result["missing_courses"])

    def test_unknown_times_remain_tentative_in_a_partial_plan(self):
        self.remove_electives()
        self.courses["COMP1001"]["schedule"] = []
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["timetable_status"], "tentative")
        self.assertEqual(result["tentative_courses"], ["COMP1001"])

    def test_strict_mode_excludes_unknown_times(self):
        self.courses["COMP1001"]["schedule"] = []
        self.courses["COMP2002"]["prerequisites"] = "NONE"
        result = self.plan(allow_unknown=False)
        self.check_partial(result, allow_unknown=False)
        self.assertEqual(result["selected_courses"], ["COMP2002"])
        self.assertEqual(result["tentative_courses"], [])
        self.assertEqual(result["timetable_status"], "confirmed")

    def test_half_semester_courses_can_share_a_time(self):
        self.courses = {
            "COMP1001": make_course(half="H1"),
            "COMP1002": make_course(half="H2")
        }
        self.constraints["university_rules"].update(
            total_credits_for_degree=9, level_1_credits_required=6,
            min_in_faculty_level_1_credits=6
        )
        self.tracks["majors"]["test"]["level1_required"] = list(self.courses)
        result = self.plan()
        self.check_partial(result)
        self.assertCountEqual(result["selected_courses"], list(self.courses))
        self.assertEqual(result["scheduled_credits"], 6)

    def test_minimum_semester_load_is_not_relaxed(self):
        self.remove_electives()
        self.constraints["registration_limits"]["part_1"]["min_credits_per_semester"] = 6
        result = self.plan()
        self.assertFalse(result["complete"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["plan"], {})
        self.assertEqual(result["scheduled_credits"], 0)

    def test_foundation_alternatives_are_not_counted_twice(self):
        self.remove_electives()
        self.courses["FOUN1001"] = make_course(day="TUE")
        self.courses["FOUN1002"] = make_course(day="WED")
        self.constraints["university_rules"].update(
            total_credits_for_degree=9, foundation_credits_required=3
        )
        self.constraints["foundation_courses"]["required_blocks"] = [{
            "type": "choose_one", "options": ["FOUN1001", "FOUN1002"],
            "credits": 3
        }]
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["scheduled_credits"], 6)
        self.assertEqual(result["missing_credits"]["foundation"], 0)
        self.assertNotEqual(set(result["selected_courses"]), set(self.courses))

    def test_fallback_respects_the_foundation_count_limit(self):
        self.remove_electives()
        self.courses["FOUN1001"] = make_course(day="TUE")
        self.courses["FOUN1002"] = make_course(day="WED")
        self.constraints["university_rules"].update(
            total_credits_for_degree=9, level_2_3_credits_required=0,
            min_in_faculty_level_2_3_credits=0, foundation_credits_required=6
        )
        self.constraints["foundation_courses"]["max_per_semester"] = 1
        self.constraints["foundation_courses"]["required_blocks"] = [
            {"type": "course", "code": "FOUN1001", "credits": 3},
            {"type": "course", "code": "FOUN1002", "credits": 3}
        ]
        self.tracks["majors"]["test"]["elective_blocks"] = []
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["scheduled_credits"], 6)
        self.assertEqual(result["missing_credits"]["foundation"], 3)

    def test_full_solution_still_takes_priority(self):
        result = self.plan()
        self.assertTrue(result["success"])
        self.assertTrue(result["complete"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["credit_shortfall"], 0)
        self.assertEqual(result["missing_courses"], [])
        self.assertEqual(result["unsatisfied_requirements"], [])

    def test_search_limit_keeps_progress_within_the_same_budget(self):
        complete = self.plan()
        limit = complete["nodes_explored"] - 1
        result = self.plan(max_nodes=limit)
        self.check_partial(result)
        self.assertTrue(result["limit_reached"])
        self.assertEqual(result["full_search_status"], "limit_reached")
        self.assertEqual(result["reason"], "Search limit reached")
        self.assertLessEqual(result["nodes_explored"], limit)

    def test_tiny_budget_does_not_invent_a_partial_plan(self):
        result = self.plan(max_nodes=1)
        self.assertEqual(result["plan"], {})
        self.assertFalse(result["verified"])
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"], "limit_reached")
        self.assertEqual(result["nodes_explored"], 1)

    def test_full_credit_total_does_not_hide_a_missing_compulsory_course(self):
        self.courses["COMP1001"]["prerequisites"] = "HEAD_PERMISSION"
        self.courses["COMP1002"] = make_course()
        self.courses["COMP2002"]["prerequisites"] = "NONE"
        result = self.plan()
        self.check_partial(result)
        self.assertEqual(result["scheduled_credits"], 6)
        self.assertEqual(result["credit_shortfall"], 0)
        self.assertIn("COMP1001", result["missing_courses"])


if __name__ == "__main__":
    unittest.main()
