# Check how course selection and semester scheduling work together.

import unittest

from csp.constraints import build_semesters
from csp.course_selection import select_degree_courses
from csp.planner import plan_degree, verify_degree_plan
from tests.helpers import make_course, make_degree_fixture


class TestIntegratedSearch(unittest.TestCase):
    def setUp(self):
        self.courses, self.constraints, self.tracks = make_degree_fixture()

    def plan(self, years=1, **options):
        return plan_degree(
            "test", self.courses, self.constraints, self.tracks,
            track="preferred", years=years, **options
        )

    def test_scheduler_failure_backtracks_to_another_elective(self):
        first = select_degree_courses("test", self.courses, self.constraints,
                                      self.tracks, "preferred", years=1)
        self.assertIn("COMP2001", first["course_codes"])
        result = self.plan()
        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        self.assertIn("COMP2002", result["selected_courses"])
        self.assertNotIn("COMP2001", result["selected_courses"])
        self.assertEqual(result["scheduling_attempts"], 2)
        self.assertGreater(result["selection_backtracks"], 0)

    def test_prerequisite_can_be_selected_after_its_dependent(self):
        self.courses["COMP2001"]["prerequisites"] = "COMP2002"
        rules = self.constraints["university_rules"]
        rules.update(total_credits_for_degree=9, level_2_3_credits_required=6)
        self.tracks["majors"]["test"]["elective_blocks"][0]["credits"] = 6
        result = self.plan(years=2)
        self.assertTrue(result["success"])
        self.assertEqual(result["plan"]["Y1S2"], ["COMP2002"])
        self.assertEqual(result["plan"]["Y2S1"], ["COMP2001"])

    def test_level1_choice_is_retried_after_scheduling_failure(self):
        self.courses = {
            "COMP1001": make_course(terms=("2",)),
            "COMP1002": make_course(terms=("1",)),
            "COMP2001": make_course(2, ("2",), "OR(COMP1001; COMP1002)", "TUE")
        }
        self.tracks["majors"]["test"]["level1_required"] = []
        self.tracks["majors"]["test"]["advanced_required"] = ["COMP2001"]
        self.tracks["majors"]["test"]["elective_blocks"] = []
        self.tracks["tracks"]["preferred"]["preferred_electives"] = ["COMP1001"]
        result = self.plan()
        self.assertTrue(result["success"])
        self.assertIn("COMP1002", result["selected_courses"])
        self.assertNotIn("COMP1001", result["selected_courses"])
        self.assertEqual(result["scheduling_attempts"], 2)

    def test_foundation_alternative_survives_early_pruning(self):
        self.courses = {
            "COMP1001": make_course(terms=("2",)),
            "FOUN1001": make_course(terms=("2",)),
            "FOUN1002": make_course(terms=("1",))
        }
        self.constraints["university_rules"].update(
            level_2_3_credits_required=0, foundation_credits_required=3,
            min_in_faculty_level_2_3_credits=0
        )
        self.constraints["foundation_courses"]["required_blocks"] = [{
            "type": "choose_one", "options": ["FOUN1001", "FOUN1002"], "credits": 3
        }]
        self.tracks["majors"]["test"]["elective_blocks"] = []
        result = self.plan()
        self.assertTrue(result["success"])
        self.assertIn("FOUN1002", result["selected_courses"])
        self.assertNotIn("FOUN1001", result["selected_courses"])
        self.assertGreater(result["pruned_branches"], 0)

    def test_impossible_full_degree_keeps_a_valid_partial_plan(self):
        del self.courses["COMP2002"]
        result = self.plan()
        self.assertFalse(result["success"])
        self.assertFalse(result["limit_reached"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["full_search_status"], "infeasible")
        self.assertFalse(result["complete"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["unsatisfied_requirements"])
        self.assertEqual(result["plan"], {"Y1S1": ["COMP1001"]})
        self.assertEqual(result["credit_shortfall"], 3)

    def test_budget_is_shared_across_selection_and_scheduler_retries(self):
        complete = self.plan()
        budget = complete["nodes_explored"] - 1
        result = self.plan(max_nodes=budget)
        self.assertFalse(result["success"])
        self.assertTrue(result["limit_reached"])
        self.assertEqual(result["reason"], "Search limit reached")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["full_search_status"], "limit_reached")
        self.assertFalse(result["complete"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["nodes_explored"], budget)
        self.assertEqual(result["scheduling_attempts"], 2)
        self.assertEqual(result["nodes_explored"], result["selection_nodes"] + result["scheduling_nodes"])

    def test_permission_is_enforced_and_reported(self):
        self.courses["COMP1001"]["prerequisites"] = "HEAD_PERMISSION"
        denied = self.plan()
        self.assertFalse(denied["success"])
        self.assertIn("COMP1001", " ".join(denied["unsatisfied_requirements"]))
        self.assertTrue(self.plan(approved_courses={"COMP1001"})["success"])

    def test_unknown_timetable_stays_tentative(self):
        self.courses["COMP1001"]["schedule"] = []
        result = self.plan()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "tentative")
        self.assertEqual(result["tentative_courses"], ["COMP1001"])
        self.assertFalse(self.plan(allow_unknown=False)["success"])

    def test_prerequisite_cycles_are_not_valid_degree_selections(self):
        self.courses["COMP1001"]["prerequisites"] = "COMP2002"
        self.assertFalse(self.plan()["success"])

    def test_plan_verification_rejects_incomplete_and_misordered_plans(self):
        result = self.plan()
        semesters = build_semesters(1)
        for invalid in ({"Y1S1": ["COMP1001"]},
                        {"Y1S1": ["COMP1001", "COMP2002"]},
                        {"Y1S1": ["COMP2002"], "Y1S2": ["COMP1001"]}):
            with self.subTest(plan=invalid):
                verified = verify_degree_plan(
                    "test", result["selected_courses"], invalid, self.courses,
                    self.constraints, self.tracks, semesters
                )
                self.assertFalse(verified["valid"])


if __name__ == "__main__":
    unittest.main()
