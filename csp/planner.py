# Coordinate elective and semester CSP search, then verify the full plan.

import argparse

from csp.constraints import TimetableIndex, build_semesters, validate_semester_plan
from csp.course_selection import (
    SelectionInfeasible, search_degree_courses, validate_degree_selection
)
from csp.data import load_courses, load_constraints, load_tracks, get_degree_blueprint
from csp.search import SearchBudget
from csp.solver import _find_partial_degree_plan


def verify_degree_plan(major, selected_courses, plan, courses, constraints, tracks,
                       semesters, approved_courses=None, allow_unknown=True):
    # Verify actual courses and semesters independently of search caches.
    # Check graduation requirements and semester assignments separately.

    selection = validate_degree_selection(
        major, selected_courses, courses, constraints, tracks, approved_courses
    )

    schedule = validate_semester_plan(
        plan, courses, constraints, semesters, approved_courses=approved_courses,
        allow_unknown=allow_unknown, expected_courses=selected_courses
    )

    errors = selection["errors"] + schedule["errors"]

    return {"valid": not errors, "errors": errors,
            "tentative_courses": schedule["tentative_courses"]}


def _degree_candidates(major, track, blueprint, courses, tracks):
    # Keep compulsory courses first, then try foundation and preferred options.
    ordered = blueprint["required_level1"] + blueprint["required_advanced"]
    required = set(ordered)

    for block in blueprint["foundation_blocks"]:
        if block["type"] == "course":
            options = [block["code"]]
        else:
            options = block["options"]

        ordered.extend(options)
        required.update(options)

    if track is not None:
        ordered.extend(tracks["tracks"][major][track]["preferred_electives"])
    ordered.extend(courses)

    candidates = []
    seen = set()

    for code in ordered:
        if code in courses and code not in seen:
            candidates.append(code)
            seen.add(code)

    return candidates, required


def _describe_requirements(result, blueprint, checked):
    # A full credit total alone is not enough: compulsory courses and blocks
    # must also be present before the degree can be marked complete.
    selected = set(result["selected_courses"])
    required = blueprint["required_level1"] + blueprint["required_advanced"]

    for block in blueprint["foundation_blocks"]:
        if block["type"] == "course":
            required.append(block["code"])

    result["missing_courses"] = []

    for code in required:
        if code not in selected and code not in result["missing_courses"]:
            result["missing_courses"].append(code)

    targets = blueprint["targets"]
    result["missing_credits"] = {
        "level1": max(0, targets["level1"] - checked["level1_credits"]),
        "advanced": max(0, targets["advanced"] - checked["advanced_credits"]),
        "foundation": max(0, targets["foundation"] - checked["foundation_credits"])
    }

    result["credit_shortfall"] = max(0, targets["total"] - result["scheduled_credits"])
    result["unsatisfied_requirements"] = checked["errors"]


def plan_degree(major, courses, constraints, tracks, track=None, years=3,
                include_summer=False, approved_courses=None, allow_unknown=True,
                max_nodes=20000):
    # Try a full degree first, then keep a valid incomplete schedule if needed.

    budget = SearchBudget(max_nodes)
    semesters = build_semesters(years, include_summer)
    blueprint = get_degree_blueprint(major, courses, constraints, tracks)

    if track is not None and track not in tracks.get("tracks", {}).get(major, {}):
        raise ValueError(f"Unknown track for {major}: {track}")

    timetable = TimetableIndex(courses)
    approved = set(approved_courses or [])
    candidates, required = _degree_candidates(major, track, blueprint, courses, tracks)
    progress = {"plan": {}, "score": (0, 0), "required_courses": required,
                "tentative_courses": []}

    result = {
        "success": False, "complete": False, "verified": False,
        "major": major, "track": track,
        "required_credits": blueprint["targets"]["total"],
        "selected_credits": 0, "scheduled_credits": 0, "selected_courses": [],
        "elective_selections": {}, "plan": {}, "semester_credits": {},
        "tentative_courses": [], "timetable_status": None,
        "unsatisfied_requirements": [], "reason": None,
        "full_search_status": None
    }

    outcome = None
    selection_error = None

    try:
        # Full scheduling saves safe progress before undoing failed assignments.
        outcome = search_degree_courses(
            major, courses, constraints, tracks, track, approved, years,
            max_nodes, include_summer, allow_unknown, semesters=semesters,
            _budget=budget, _timetable=timetable, _partial=progress
        )
    except SelectionInfeasible as error:
        selection_error = str(error)

    full_schedule = None
    if outcome is not None and outcome["last_schedule"] is not None:
        if outcome["last_schedule"]["success"]:
            full_schedule = outcome["last_schedule"]

    if full_schedule is not None:
        result["plan"] = full_schedule["plan"]
        result["full_search_status"] = "complete"
    else:
        if budget.limit_reached:
            result["full_search_status"] = "limit_reached"
            result["reason"] = "Search limit reached"
        else:
            result["full_search_status"] = "infeasible"
            result["reason"] = "No valid degree plan"

        # Do not reset the node budget or relax any semester-level constraints.
        _find_partial_degree_plan(
            candidates, courses, constraints, semesters, approved, allow_unknown,
            budget, timetable, progress
        )
        result["plan"] = progress["plan"]

    for semester_id, codes in result["plan"].items():
        total = 0
        for code in codes:
            total += courses[code]["credits"]
            result["selected_courses"].append(code)
        result["semester_credits"][semester_id] = total

    result["scheduled_credits"] = sum(result["semester_credits"].values())
    result["selected_credits"] = result["scheduled_credits"]

    checked = validate_degree_selection(
        major, result["selected_courses"], courses, constraints, tracks, approved
    )
    result["elective_selections"] = checked["elective_selections"]
    _describe_requirements(result, blueprint, checked)

    if result["plan"]:
        verified = validate_semester_plan(
            result["plan"], courses, constraints, semesters,
            approved_courses=approved, allow_unknown=allow_unknown,
            expected_courses=result["selected_courses"]
        )

        if not verified["valid"]:
            raise RuntimeError("Invalid CSP result: " + "; ".join(verified["errors"]))

        result["verified"] = True
        result["tentative_courses"] = verified["tentative_courses"]
        result["timetable_status"] = "confirmed"

        if result["tentative_courses"]:
            result["timetable_status"] = "tentative"

        if checked["valid"]:
            result["success"] = True
            result["complete"] = True
            result["full_search_status"] = "complete"
            result["reason"] = None
            result["status"] = result["timetable_status"]
        else:
            # verified means the returned schedule is safe; it is not graduation.
            result["status"] = "partial"
    else:
        result["status"] = result["full_search_status"]

    if not result["complete"]:
        if selection_error is not None:
            result["unsatisfied_requirements"].insert(0, selection_error)

        if result["full_search_status"] == "limit_reached":
            result["unsatisfied_requirements"].insert(0, "Search limit reached; a complete degree may still be possible")

    result.update(budget.snapshot())

    return result


def generate_full_degree_plan(major, track=None, years=3, include_summer=False,
                              approved_courses=None, allow_unknown=True,
                              max_nodes=20000):
    # Plan a full degree and return a valid partial fallback when needed.

    return plan_degree(
        major, load_courses(), load_constraints(), load_tracks(), track, years,
        include_summer, approved_courses, allow_unknown, max_nodes
    )


def main():
    parser = argparse.ArgumentParser(description="CSP full-degree planner")
    parser.add_argument("--major", default="computer_science",
                        help="Major to plan (default: computer_science)")
    parser.add_argument("--track", help="Specialization within the selected major")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--include-summer", action="store_true")
    parser.add_argument("--strict-timetable", action="store_true")
    parser.add_argument("--approved-courses", nargs="*", default=[])
    parser.add_argument("--max-nodes", type=int, default=20000)

    args = parser.parse_args()

    options = dict(years=args.years, include_summer=args.include_summer,
                   allow_unknown=not args.strict_timetable,
                   approved_courses=args.approved_courses, max_nodes=args.max_nodes)

    try:
        result = generate_full_degree_plan(args.major, args.track, **options)
    except ValueError as exc:
        parser.error(str(exc))

    print("AI-BASED DEGREE PLANNER")
    print("Major:", result["major"])

    if result["track"] is not None:
        print("Track:", result["track"])

    print("Status:", result["status"])

    # Display a safe partial schedule too, even when graduation is incomplete.
    if result["plan"]:
        courses = load_courses()
        semesters = build_semesters(args.years, args.include_summer)

        # Show the whole planning period, including any unused summer terms.
        for semester in semesters:
            sid = semester["id"]
            codes = result["plan"].get(sid, [])
            credits = result["semester_credits"].get(sid, 0)

            print(f"\n{sid} ({credits} credits)")

            if not codes:
                print("  No courses assigned")

            for code in codes:
                print(f"  {code}: {courses[code]['title']}")

        print(f"\nTotal scheduled credits: {result['scheduled_credits']}")

        if result["tentative_courses"]:
            print("Courses requiring confirmation:", ", ".join(result["tentative_courses"]))

    if not result["complete"]:
        print("Full degree not completed:", result["reason"])
        print("Credits still needed:", result["credit_shortfall"])

        if result["missing_courses"]:
            print("Missing compulsory courses:", ", ".join(result["missing_courses"]))

        for error in result["unsatisfied_requirements"]:
            print("-", error)

    print(f"Nodes explored: {result['nodes_explored']}")
    print(f"Backtracks: {result['backtracks']}")
    print(f"Execution time: {result['execution_time']:.4f} seconds")

    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
