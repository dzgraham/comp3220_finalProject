# Select degree courses using ordinary recursive backtracking.

from csp.constraints import (
    COMPUTING_PREFIXES, FACULTY_PREFIXES, TimetableIndex, build_semesters,
    find_overloaded_term_clique, get_foundation_codes, get_offered_terms,
    prerequisites_satisfied
)
from csp.data import get_degree_blueprint
from csp.search import SearchBudget
from csp.solver import solve_degree_plan


class SelectionInfeasible(ValueError):
    # A required course is unavailable or lacks prerequisites/approval.
    pass


def _matches_block(code, course, block):
    department = block["from_dept"]
    if department not in {"Any", "Computing"}:
        raise ValueError(f"Unsupported elective department: {department}")
    if course["level"] not in block["from_level"]:
        return False
    if department == "Computing" and code[:4] not in COMPUTING_PREFIXES:
        return False
    return True


def _credits(course_codes, courses):
    total = 0
    for code in course_codes:
        total += courses[code]["credits"]
    return total


def _elective_assignment(extras, blocks, courses, budget=None):
    """Try different ways to fill the blocks without reusing a course."""
    assignments = {}
    used_courses = set()
    block_options = []

    for block in blocks:
        if block["type"] != "choose_credits":
            raise ValueError(f"Unsupported elective block: {block['id']}")
        options = []
        for code in extras:
            if _matches_block(code, courses[code], block):
                options.append(code)
        block_options.append((len(options), block["id"], options, block["credits"]))
    # Fill the blocks with fewer choices first.
    block_options.sort()

    def assign_block(block_index):
        if block_index == len(block_options):
            return assignments.copy()
        _, block_id, options, required_credits = block_options[block_index]
        picked = []

        def choose_courses(start, credits_needed):
            if credits_needed == 0:
                # This block is full, but the later blocks must also work.
                assignments[block_id] = picked.copy()
                answer = assign_block(block_index + 1)
                if answer is not None:
                    return answer
                del assignments[block_id]
                if budget is not None:
                    budget.backtracks["selection"] += 1
                return None

            available_credits = 0
            for code in options[start:]:
                if code not in used_courses:
                    available_credits += courses[code]["credits"]
            if available_credits < credits_needed:
                # Stop if the remaining courses cannot fill this block.
                return None

            for index in range(start, len(options)):
                code = options[index]
                cost = courses[code]["credits"]
                if code in used_courses or cost <= 0 or cost > credits_needed:
                    continue
                if budget is not None and not budget.step("selection"):
                    return None

                # Choose, recurse, then undo if this choice does not work.
                picked.append(code)
                # A course can count toward only one elective block.
                used_courses.add(code)
                answer = choose_courses(index + 1, credits_needed - cost)
                if answer is not None:
                    return answer
                used_courses.remove(code)
                picked.pop()
                if budget is not None and budget.limit_reached:
                    return None
            return None

        return choose_courses(0, required_credits)

    return assign_block(0)


def validate_degree_selection(major, course_codes, courses, constraints, tracks,
                              approved_courses=None, *, _budget=None):
    """Check graduation rules from the supplied JSON and course catalogue."""
    blueprint = get_degree_blueprint(major, courses, constraints, tracks)
    codes = list(course_codes)
    selected = set(codes)
    errors = []
    if len(codes) != len(selected):
        errors.append("Duplicate selected courses")
    for code in codes:
        if code not in courses:
            return {"valid": False, "errors": ["Unknown selected courses"]}

    compulsory = set(blueprint["required_level1"] + blueprint["required_advanced"])
    missing = compulsory - selected
    if missing:
        errors.append("Missing major compulsory courses: " + ", ".join(sorted(missing)))

    foundation_codes = get_foundation_codes(constraints)
    for block in blueprint["foundation_blocks"]:
        if block["type"] == "course":
            options = {block["code"]}
        else:
            options = set(block["options"])
        chosen = selected & options
        if len(chosen) != 1 or _credits(chosen, courses) != block["credits"]:
            errors.append("Unsatisfied foundation block: " + ", ".join(sorted(options)))

    counts = {"level1_credits": 0, "advanced_credits": 0,
              "foundation_credits": 0, "total_credits": 0}
    faculty_level1 = 0
    faculty_advanced = 0
    extras = []
    for code in codes:
        course = courses[code]
        credits = course["credits"]
        counts["total_credits"] += credits
        # Foundation credits have their own target, so do not count them twice.
        if code in foundation_codes:
            counts["foundation_credits"] += credits
        elif course["level"] == 1:
            counts["level1_credits"] += credits
        elif course["level"] in (2, 3):
            counts["advanced_credits"] += credits
        if code[:4] in FACULTY_PREFIXES:
            if course["level"] == 1:
                faculty_level1 += credits
            elif course["level"] in (2, 3):
                faculty_advanced += credits
        if code not in compulsory and code not in foundation_codes:
            extras.append(code)
        # A course cannot satisfy its own prerequisite.
        if not prerequisites_satisfied(code, selected - {code}, courses, approved_courses):
            errors.append(f"Missing prerequisite or approval for {code}")

    expected = {
        "level1_credits": blueprint["targets"]["level1"],
        "advanced_credits": blueprint["targets"]["advanced"],
        "foundation_credits": blueprint["targets"]["foundation"],
        "total_credits": blueprint["targets"]["total"]
    }
    for field in expected:
        if counts[field] != expected[field]:
            errors.append(f"{field} must equal {expected[field]}")
    rules = constraints["university_rules"]
    if faculty_level1 < rules["min_in_faculty_level_1_credits"]:
        errors.append("Faculty Level 1 credit minimum not met")
    if faculty_advanced < rules["min_in_faculty_level_2_3_credits"]:
        errors.append("Faculty Level 2/3 credit minimum not met")

    assignments = _elective_assignment(extras, blueprint["elective_blocks"], courses, _budget)
    if assignments is None:
        errors.append("Elective blocks cannot be filled without reusing courses")
        assignments = {}
    result = {"valid": not errors, "errors": errors, "elective_selections": assignments}
    result.update(counts)
    return result


def _reachable_courses(universe, courses, approved):
    """Find courses whose prerequisites can eventually be completed."""
    reached = set()
    # Build up in prerequisite order. Missing dependencies and cycles stay out.
    while True:
        ready = set()
        for code in universe:
            if code not in reached and prerequisites_satisfied(code, reached, courses, approved):
                ready.add(code)
        if not ready:
            return reached
        reached.update(ready)


def _remaining_credit_totals(options, courses, level1_target, advanced_target):
    """For each position, record the totals the remaining courses can make."""
    totals = []
    for index in range(len(options) + 1):
        totals.append({1: {0}, 2: {0}})
    # Work backward so each position can reuse the totals after it.
    for index in range(len(options) - 1, -1, -1):
        code = options[index]
        course = courses[code]
        if course["level"] == 1:
            course_group = 1
        else:
            course_group = 2
        for group, target in ((1, level1_target), (2, advanced_target)):
            possible = totals[index + 1][group].copy()
            if course_group == group:
                for previous_total in totals[index + 1][group]:
                    new_total = previous_total + course["credits"]
                    if new_total <= target:
                        possible.add(new_total)
            totals[index][group] = possible
    return totals


def search_degree_courses(major, courses, constraints, tracks, track=None,
                          approved_courses=None, years=3, max_nodes=20000,
                          include_summer=False, allow_unknown=True, *,
                          semesters=None, find_all=False, _budget=None,
                          _timetable=None, _partial=None):
    """Choose courses recursively and optionally schedule each complete choice."""
    # Reuse the planner's budget so changing electives does not reset the limit.
    budget = _budget
    if budget is None:
        budget = SearchBudget(max_nodes)
    timetable = _timetable
    if timetable is None:
        timetable = TimetableIndex(courses)
    planning_semesters = semesters
    if planning_semesters is None:
        planning_semesters = build_semesters(years, include_summer)
    blueprint = get_degree_blueprint(major, courses, constraints, tracks)
    track_options = tracks.get("tracks", {}).get(major, {})
    if track is not None and track not in track_options:
        raise ValueError(f"Unknown track for {major}: {track}")
    preferred = []
    if track is not None:
        preferred = track_options[track]["preferred_electives"]
    approved = set(approved_courses or [])
    core = blueprint["required_level1"] + blueprint["required_advanced"]
    foundation_codes = get_foundation_codes(constraints)
    terms = set()
    for semester in planning_semesters:
        terms.add(semester["term"])
    available = set()
    # Only consider courses offered during this planning period.
    for code, course in courses.items():
        offered = set(get_offered_terms(code, courses))
        if not offered.intersection(terms):
            continue
        if not allow_unknown and code in timetable.unknown:
            continue
        if course["credits"] > 0:
            available.add(code)

    # Ordinary dictionaries remember checks already performed in this search.
    reachable_cache = {}
    feasibility_cache = {}

    def reachable(universe):
        key = tuple(sorted(universe))
        if key not in reachable_cache:
            reachable_cache[key] = _reachable_courses(universe, courses, approved)
        return reachable_cache[key]

    available = available.intersection(reachable(available))
    missing = set(core) - available
    if missing:
        raise SelectionInfeasible(
            "Required courses unavailable or missing prerequisites/approval: "
            + ", ".join(sorted(missing))
        )

    def candidate_order(code):
        # Try preferred electives first, while keeping other choices available.
        rank = len(preferred)
        if code in preferred:
            rank = preferred.index(code)
        department_rank = 1
        if code[:4] in COMPUTING_PREFIXES:
            department_rank = 0
        return (rank, department_rank, code)

    options = sorted(available - set(core) - foundation_codes, key=candidate_order)
    level1_needed = blueprint["remaining_credits"]["level1"]
    advanced_needed = blueprint["remaining_credits"]["advanced"]
    credit_totals = _remaining_credit_totals(options, courses, level1_needed, advanced_needed)
    selected = core.copy()
    outcome = {"selections": [], "last_selection": None, "last_schedule": None}

    def complete_selection():
        checked = validate_degree_selection(
            major, selected, courses, constraints, tracks, approved, _budget=budget
        )
        if not checked["valid"]:
            budget.pruned_branches += 1
            return False
        budget.selection_attempts += 1
        # Save a copy because later backtracking changes the selected list.
        selection = {
            "major": major, "track": track, "course_codes": selected.copy(),
            "total_credits": checked["total_credits"],
            "level1_credits": checked["level1_credits"],
            "advanced_credits": checked["advanced_credits"],
            "foundation_credits": checked["foundation_credits"],
            "elective_selections": checked["elective_selections"]
        }
        outcome["last_selection"] = selection
        if semesters is not None:
            schedule = solve_degree_plan(
                selected, courses, constraints, semesters,
                approved_courses=approved, allow_unknown=allow_unknown,
                _budget=budget, _timetable=timetable, _partial=_partial
            )
            outcome["last_schedule"] = schedule
            if not schedule["success"]:
                # The caller will undo this elective choice and try another.
                return False
            selection["schedule"] = schedule
        outcome["selections"].append(selection)
        # Stop after one answer unless the caller asked for every selection.
        return not find_all

    def choose_courses(start, needed_level1, needed_advanced):
        # Pruning: stop when the remaining courses cannot make these totals.
        if needed_level1 not in credit_totals[start][1]:
            budget.pruned_branches += 1
            return False
        if needed_advanced not in credit_totals[start][2]:
            budget.pruned_branches += 1
            return False
        key = tuple(sorted(selected))
        if key not in feasibility_cache:
            conflict = find_overloaded_term_clique(selected, courses, years, _timetable=timetable)
            feasibility_cache[key] = conflict is None
        if not feasibility_cache[key]:
            budget.pruned_branches += 1
            return False

        remaining_options = set()
        for code in options[start:]:
            if courses[code]["level"] == 1:
                space = needed_level1
            else:
                space = needed_advanced
            if courses[code]["credits"] <= space:
                remaining_options.add(code)
        possible = set(selected) | remaining_options
        # Prerequisites may be chosen later, but must still be available.
        if not set(selected).issubset(reachable(possible)):
            budget.pruned_branches += 1
            return False
        if needed_level1 == 0 and needed_advanced == 0:
            return complete_selection()

        extras = possible - set(core) - foundation_codes
        for block in blueprint["elective_blocks"]:
            available_credits = 0
            for code in extras:
                if _matches_block(code, courses[code], block):
                    available_credits += courses[code]["credits"]
            if available_credits < block["credits"]:
                budget.pruned_branches += 1
                return False

        for index in range(start, len(options)):
            code = options[index]
            cost = courses[code]["credits"]
            next_level1 = needed_level1
            next_advanced = needed_advanced
            if courses[code]["level"] == 1:
                next_level1 -= cost
            else:
                next_advanced -= cost
            if next_level1 < 0 or next_advanced < 0:
                continue
            if not budget.step("selection"):
                return False

            # Choose a course, search further, then undo a failed choice.
            selected.append(code)
            # Move forward to avoid repeating the same combination in a new order.
            finished = choose_courses(index + 1, next_level1, next_advanced)
            selected.pop()
            if finished:
                return True
            budget.backtracks["selection"] += 1
            if budget.limit_reached:
                return False
        return False

    def choose_foundations(block_index):
        # Try each allowed foundation option before accepting the full degree.
        blocks = blueprint["foundation_blocks"]
        if block_index == len(blocks):
            return choose_courses(0, level1_needed, advanced_needed)
        block = blocks[block_index]
        if block["type"] == "course":
            choices = [block["code"]]
        elif block["type"] == "choose_one":
            choices = block["options"]
        else:
            raise ValueError(f"Unsupported foundation block: {block['type']}")
        for code in choices:
            if code not in available or code in selected:
                continue
            if courses[code]["credits"] != block["credits"]:
                continue
            if not budget.step("selection"):
                return False
            selected.append(code)
            finished = choose_foundations(block_index + 1)
            selected.pop()
            if finished:
                return True
            budget.backtracks["selection"] += 1
            if budget.limit_reached:
                return False
        return False

    choose_foundations(0)
    return outcome


def select_degree_courses(major, courses, constraints, tracks, track=None,
                          approved_courses=None, years=3, max_nodes=20000,
                          include_summer=False, allow_unknown=True):
    """Return the first academically valid selection without scheduling it."""
    budget = SearchBudget(max_nodes)
    outcome = search_degree_courses(
        major, courses, constraints, tracks, track, approved_courses, years,
        max_nodes, include_summer, allow_unknown, _budget=budget
    )
    if budget.limit_reached:
        raise ValueError("Search limit reached during course selection")
    if not outcome["selections"]:
        raise ValueError("No valid degree course selection")
    return outcome["selections"][0]


def find_degree_selections(major, courses, constraints, tracks, track=None,
                          approved_courses=None, years=3, max_nodes=20000,
                          include_summer=False, allow_unknown=True):
    """Return a normal list of all selections found within the node budget."""
    budget = SearchBudget(max_nodes)
    outcome = search_degree_courses(
        major, courses, constraints, tracks, track, approved_courses, years,
        max_nodes, include_summer, allow_unknown, find_all=True, _budget=budget
    )
    if budget.limit_reached:
        raise ValueError("Search limit reached before all course selections were checked")
    return outcome["selections"]


# Keep the earlier import name working; it now returns an ordinary list.
iter_degree_selections = find_degree_selections
