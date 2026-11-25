# Backtracking, forward checks, and search limits on small datasets.

import unittest
from copy import deepcopy
from itertools import product

from csp.constraints import build_semesters, get_course_domain, validate_semester_plan
from csp.data import load_constraints
from csp.solver import solve_degree_plan
from tests.helpers import make_course, make_degree_fixture


class TestSolverStress(unittest.TestCase):

    def setUp(self):
        # These courses force the solver to undo a bad semester choice.
        self.courses = {
            "TEST1001": make_course(terms=("1", "2")),
            "TEST1002": make_course(terms=("1", "2")),
            "TEST2001": make_course(terms=("2",), prerequisite="TEST1002",
                                    start="10:00", end="11:00")
        }
        self.constraints = deepcopy(load_constraints())
        for part in ("part_1", "part_2"):
            limits = self.constraints["registration_limits"][part]
            limits["min_credits_per_semester"] = 0
            limits["max_credits_per_semester"] = 18
        self.semesters = build_semesters(years=1)

    def solve(self, codes, **kwargs):
        return solve_degree_plan(
            requested_courses=codes,
            courses=self.courses,
            constraints=self.constraints,
            semesters=self.semesters,
            **kwargs
        )

    def test_solver_backtracks_and_recovers(self):
        # The first choice fails, so the solver must undo it and try again.
        result = self.solve([
            "TEST1001",
            "TEST1002",
            "TEST2001"
        ])

        self.assertTrue(result["success"])

        # Confirm actual backtracking occurred.
        self.assertGreater(result["backtracks"], 0)

        # TEST1002 must precede TEST2001.
        self.assertEqual(
            result["plan"]["Y1S1"],
            ["TEST1002"]
        )

        self.assertCountEqual(
            result["plan"]["Y1S2"],
            ["TEST1001", "TEST2001"]
        )

    def test_impossible_schedule(self):
        # Both conflicting courses can only use Semester 1.
        self.courses["TEST1001"]["semesters"] = ["1"]
        self.courses["TEST1002"]["semesters"] = ["1"]

        result = self.solve([
            "TEST1001",
            "TEST1002",
            "TEST2001"
        ])

        self.assertFalse(result["success"])
        self.assertEqual(
            result["reason"],
            "No valid semester arrangement"
        )

    def test_search_limit(self):
        # Stop at the budget and report an unfinished search.
        result = self.solve(
            [
                "TEST1001",
                "TEST1002",
                "TEST2001"
            ],
            max_nodes=1
        )

        self.assertFalse(result["success"])

        self.assertEqual(
            result["reason"],
            "Search limit reached"
        )

        self.assertEqual(
            result["nodes_explored"],
            1
        )


class TestForwardChecking(unittest.TestCase):
    def setUp(self):
        self.courses, self.constraints, self.tracks = make_degree_fixture()

    def test_forward_checks_agree_with_exhaustive_search(self):
        semesters = build_semesters(years=2)
        for condition, conflicting in product(
            ["NONE", "COMP1001", "OR(COMP1001; COMP2001)", "AND(COMP1001; COMP2001)"],
            [False, True]
        ):
            with self.subTest(condition=condition, conflicting=conflicting):
                courses = deepcopy(self.courses)
                courses["COMP2002"]["prerequisites"] = condition
                if conflicting:
                    courses["COMP2001"]["schedule"] = deepcopy(courses["COMP1001"]["schedule"])
                codes = list(courses)
                expected = False
                domains = [get_course_domain(c, semesters, courses) for c in codes]
                for slots in product(*domains):
                    candidate = {}
                    for code, slot in zip(codes, slots):
                        candidate.setdefault(slot["id"], []).append(code)
                    if validate_semester_plan(candidate, courses, self.constraints, semesters)["valid"]:
                        expected = True
                        break
                actual = solve_degree_plan(codes, courses, self.constraints, semesters)
                self.assertEqual(actual["success"], expected)


if __name__ == "__main__":
    unittest.main()
