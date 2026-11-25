# Assign courses to semesters using MRV (Minimum Remaining Values) and recursive backtracking.

from csp.constraints import (
    TimetableIndex, build_semesters, get_course_domain, get_foundation_codes,
    prerequisites_satisfied, semester_load_valid, validate_semester_plan
)
from csp.search import SearchBudget

def _semester_order(semester):
    return (semester["year"], int(semester["term"]))


def _remember_partial_plan(plan, courses, constraints, semesters, approved,
                           allow_unknown, progress):
    # Keep only courses whose prerequisites are actually earlier in the plan.
    candidate = {}
    prior = set()
    codes = []

    for semester in semesters:
        semester_id = semester["id"]
        eligible = []

        for code in plan.get(semester_id, []):
            if prerequisites_satisfied(code, prior, courses, approved):
                eligible.append(code)

        if not eligible:
            continue

        part = "part_1" if semester["year"] == 1 else "part_2"

        if not semester_load_valid(eligible, courses, constraints, part, enforce_minimum=True):
            continue

        candidate[semester_id] = sorted(eligible)
        codes.extend(eligible)
        prior.update(eligible)

    credits = 0
    core_credits = 0

    for code in codes:
        credits += courses[code]["credits"]

        if code in progress["required_courses"]:
            core_credits += courses[code]["credits"]

    score = (credits, core_credits)

    if not codes or score <= progress["score"]:
        return

    # A useful incomplete plan must still pass every semester-level rule.
    verified = validate_semester_plan(
        candidate, courses, constraints, semesters,
        approved_courses=approved, allow_unknown=allow_unknown,
        expected_courses=codes
    )

    if verified["valid"]:
        progress["plan"] = candidate
        progress["score"] = score
        progress["tentative_courses"] = verified["tentative_courses"]


def solve_degree_plan(requested_courses, courses, constraints, semesters=None,
                      completed_courses=None, approved_courses=None,
                      allow_unknown=True, max_nodes=20000, *,
                      _budget=None, _timetable=None, _partial=None):
    # ry semester assignments until a valid schedule is found.

    budget = _budget

    if budget is None:
        budget = SearchBudget(max_nodes)

    before = budget.snapshot()
    budget.scheduling_attempts += 1

    if semesters is None:
        semesters = build_semesters()

    semesters = sorted(semesters, key=_semester_order)
    semester_ids = []

    for semester in semesters:
        semester_ids.append(semester["id"])

    if len(semester_ids) != len(set(semester_ids)):
        raise ValueError("Semester IDs must be unique")

    requested = list(requested_courses)

    if len(requested) != len(set(requested)):
        raise ValueError("Course selection contains duplicates")

    for code in requested:
        if code not in courses:
            raise ValueError(f"Unknown course: {code}")

    completed = set(completed_courses or [])
    approved = set(approved_courses or [])
    selected = []
    selected_courses = {}

    # Completed courses satisfy prerequisites but do not need scheduling again.
    for code in requested:
        if code not in completed:
            selected.append(code)
            selected_courses[code] = courses[code]

    timetable = _timetable

    if timetable is None:
        timetable = TimetableIndex(selected_courses)

    foundations = get_foundation_codes(constraints)
    foundation_rules = constraints["foundation_courses"]
    positions = {}
    capacity = []

    # Number the semesters so earlier and later semesters can be compared.
    for position, semester in enumerate(semesters):
        positions[semester["id"]] = position

        if semester["year"] == 1:
            part = "part_1"
        else:
            part = "part_2"

        capacity.append(constraints["registration_limits"][part]["max_credits_per_semester"])

    initial_domains = {}

    # A course's domain is the list of semesters it is allowed to use.
    for code in selected:
        initial_domains[code] = []

        for semester in get_course_domain(code, semesters, courses):
            if not allow_unknown and code in timetable.unknown:
                continue

            if code in foundations and semester["year"] > foundation_rules["must_complete_in_year"]:
                continue

            initial_domains[code].append(positions[semester["id"]])

    assignments = {}
    plan = {}

    for semester_id in semester_ids:
        plan[semester_id] = []

    loads = [0] * len(semesters)
    foundation_counts = [0] * len(semesters)
    remaining = set(selected)
    verification = {}
    prerequisite_cache = {}

    def check_prerequisites(code, prior):
        key = (code, tuple(sorted(prior)))

        if key not in prerequisite_cache:
            prerequisite_cache[key] = prerequisites_satisfied(code, prior, courses, approved)

        return prerequisite_cache[key]

    def find_domains():
        # Remove semesters that cannot work with the current assignments.
        domains = {}

        for code, position in assignments.items():
            domains[code] = [position]

        for code in remaining:
            domains[code] = []
            cost = courses[code]["credits"]

            for position in initial_domains[code]:
                if loads[position] + cost > capacity[position]:
                    continue

                if code in foundations and foundation_counts[position] >= foundation_rules["max_per_semester"]:
                    continue

                semester_courses = plan[semester_ids[position]]

                if timetable.clashes[code].intersection(semester_courses):
                    continue

                domains[code].append(position)

            if not domains[code]:
                return None

        # Repeat because removing an early option can affect a later course.
        changed = True

        while changed:
            changed = False
            earliest = {}

            for code in selected:
                earliest[code] = min(domains[code])

            for code in selected:
                allowed = []

                for position in domains[code]:
                    # Unassigned courses may still be placed before this course.
                    possible_prior = completed.copy()

                    for other in selected:
                        if other != code and earliest[other] < position:
                            possible_prior.add(other)

                    if check_prerequisites(code, possible_prior):
                        allowed.append(position)

                if not allowed:
                    return None

                if allowed != domains[code]:
                    domains[code] = allowed
                    changed = True

        # Check that courses confined to a group of semesters fit its credits.
        semester_groups = {tuple(range(len(semesters)))}

        for code in remaining:
            semester_groups.add(tuple(domains[code]))

        for group in semester_groups:
            required_credits = 0

            for code in remaining:
                if set(domains[code]).issubset(group):
                    required_credits += courses[code]["credits"]

            free_credits = 0

            for position in group:
                free_credits += capacity[position] - loads[position]

            if required_credits > free_credits:
                return None

        return domains

    def choose_next_course(domains):
        # MRV: choose the course with the fewest remaining semester options.

        best_code = None
        best_count = 0
        best_clashes = 0

        for code in sorted(remaining):
            option_count = len(domains[code])
            clash_count = len(timetable.clashes[code].intersection(remaining))

            if best_code is None or option_count < best_count:
                best_code = code
                best_count = option_count
                best_clashes = clash_count
            elif option_count == best_count and clash_count > best_clashes:
                # Break an MRV tie by handling the course with more clashes first.
                best_code = code
                best_clashes = clash_count

        return best_code

    def backtrack():
        # Save valid progress before a later clash or search limit causes undoing.
        if _partial is not None:
            _remember_partial_plan(
                plan, courses, constraints, semesters, approved, allow_unknown,
                _partial
            )

        if not remaining:
            # Check actual prerequisite order after every course is assigned.
            verification.clear()
            verification.update(validate_semester_plan(
                plan, courses, constraints, semesters, completed, approved,
                allow_unknown, expected_courses=selected
            ))
            return verification["valid"]

        domains = find_domains()

        if domains is None:
            budget.pruned_branches += 1
            return False

        code = choose_next_course(domains)
        remaining.remove(code)

        for position in domains[code]:
            # One node means trying one course in one semester.
            if not budget.step("scheduling"):
                remaining.add(code)
                return False

            # Choose a semester and check the rest of the schedule.
            semester_id = semester_ids[position]
            assignments[code] = position
            plan[semester_id].append(code)
            loads[position] += courses[code]["credits"]

            if code in foundations:
                foundation_counts[position] += 1

            if backtrack():
                return True

            # Undo this assignment before trying the next semester.
            if code in foundations:
                foundation_counts[position] -= 1

            loads[position] -= courses[code]["credits"]
            plan[semester_id].remove(code)
            del assignments[code]
            budget.backtracks["scheduling"] += 1

            if budget.limit_reached:
                remaining.add(code)
                return False

        remaining.add(code)
        return False

    success = backtrack()
    used = {}
    tentative = []
    diagnostics = []
    reason = None

    if success:
        for semester_id, codes in plan.items():
            if codes:
                used[semester_id] = sorted(codes)

        tentative = verification["tentative_courses"]

        if tentative:
            status = "tentative"
        else:
            status = "confirmed"
    else:
        if budget.limit_reached:
            # Reaching the limit leaves the search unfinished, not impossible.
            reason = "Search limit reached"
            status = "limit_reached"
        else:
            reason = "No valid semester arrangement"
            status = "infeasible"

        unavailable = []

        for code in selected:
            if not initial_domains[code]:
                unavailable.append(code)

        if unavailable:
            diagnostics.append("No permitted semester or timetable for: " + ", ".join(unavailable))

        if verification and not verification["valid"]:
            diagnostics.extend(verification["errors"])

        if not diagnostics:
            diagnostics.append(reason)

    stats = budget.snapshot()

    return {
        "success": success, "plan": used, "tentative_courses": tentative,
        "nodes_explored": stats["scheduling_nodes"] - before["scheduling_nodes"],
        "backtracks": stats["scheduling_backtracks"] - before["scheduling_backtracks"],
        "execution_time": stats["execution_time"] - before["execution_time"],
        "limit_reached": budget.limit_reached, "status": status,
        "unsatisfied_requirements": diagnostics, "reason": reason
    }


def _find_partial_degree_plan(course_codes, courses, constraints, semesters,
                              approved, allow_unknown, budget, timetable,
                              progress):
    # This fallback uses the nodes left after the full-degree search.
    if budget.limit_reached:
        return

    semesters = sorted(semesters, key=_semester_order)
    foundation_codes = get_foundation_codes(constraints)
    foundation_rules = constraints["foundation_courses"]
    rules = constraints["university_rules"]
    targets = {
        "level1": rules["level_1_credits_required"],
        "advanced": rules["level_2_3_credits_required"],
        "foundation": rules["foundation_credits_required"]
    }
    foundation_groups = []

    for block in foundation_rules["required_blocks"]:
        if block["type"] == "course":
            foundation_groups.append({block["code"]})
        else:
            foundation_groups.append(set(block["options"]))

    candidates = []
    groups = {}
    initial_domains = {}

    for code in course_codes:
        course = courses[code]

        if course["credits"] <= 0 or course["level"] not in (1, 2, 3):
            continue

        if not allow_unknown and code in timetable.unknown:
            continue

        if code in foundation_codes:
            groups[code] = "foundation"
        elif code.startswith("FOUN"):
            continue
        elif course["level"] == 1:
            groups[code] = "level1"
        else:
            groups[code] = "advanced"

        initial_domains[code] = []
        offered = get_course_domain(code, semesters, courses)

        for position, semester in enumerate(semesters):
            if semester not in offered:
                continue

            if code in foundation_codes and semester["year"] > foundation_rules["must_complete_in_year"]:
                continue

            initial_domains[code].append(position)

        if initial_domains[code]:
            candidates.append(code)

    plan = {}
    capacity = []

    for semester in semesters:
        plan[semester["id"]] = []
        part = "part_1" if semester["year"] == 1 else "part_2"
        capacity.append(constraints["registration_limits"][part]["max_credits_per_semester"])

    loads = [0] * len(semesters)
    foundation_counts = [0] * len(semesters)
    credits = {"level1": 0, "advanced": 0, "foundation": 0}
    assignments = {}
    prerequisite_cache = {}

    def allowed_domains(start):
        domains = {}

        for code, position in assignments.items():
            domains[code] = [position]

        for code in candidates[start:]:
            domains[code] = []
            cost = courses[code]["credits"]

            if credits[groups[code]] + cost > targets[groups[code]]:
                continue

            if code in foundation_codes:
                alternative_used = False

                for group in foundation_groups:
                    if code in group and group.intersection(assignments):
                        alternative_used = True

                if alternative_used:
                    continue

            for position in initial_domains[code]:
                if loads[position] + cost > capacity[position]:
                    continue

                if code in foundation_codes and foundation_counts[position] >= foundation_rules["max_per_semester"]:
                    continue

                semester_id = semesters[position]["id"]

                if not timetable.clashes[code].intersection(plan[semester_id]):
                    domains[code].append(position)

        # Empty optional domains can be skipped. An assigned course still needs
        # a possible earlier prerequisite, so reject the branch if it loses one.
        changed = True

        while changed:
            changed = False
            earliest = {}

            for code, values in domains.items():
                if values:
                    earliest[code] = min(values)

            for code in domains:
                allowed = []

                for position in domains[code]:
                    possible_prior = set()

                    for other in earliest:
                        if other != code and earliest[other] < position:
                            possible_prior.add(other)

                    key = (code, tuple(sorted(possible_prior)))

                    if key not in prerequisite_cache:
                        prerequisite_cache[key] = prerequisites_satisfied(
                            code, possible_prior, courses, approved
                        )

                    if prerequisite_cache[key]:
                        allowed.append(position)

                if not allowed and code in assignments:
                    return None

                if allowed != domains[code]:
                    domains[code] = allowed
                    changed = True

        return domains

    def backtrack(start):
        _remember_partial_plan(
            plan, courses, constraints, semesters, approved, allow_unknown,
            progress
        )

        if start == len(candidates):
            return

        domains = allowed_domains(start)

        if domains is None:
            budget.pruned_branches += 1
            return

        # Stop if even the remaining credits and semester space cannot improve
        # the best schedule already found.
        upper_bound = sum(credits.values())

        for group in targets:
            available = 0

            for code in candidates[start:]:
                if groups[code] == group and domains[code]:
                    available += courses[code]["credits"]

            upper_bound += min(available, targets[group] - credits[group])

        upper_bound = min(upper_bound, sum(capacity))

        if upper_bound <= progress["score"][0]:
            budget.pruned_branches += 1
            return

        code = candidates[start]
        cost = courses[code]["credits"]

        for position in domains[code]:
            if not budget.step("scheduling"):
                return

            semester_id = semesters[position]["id"]
            assignments[code] = position
            plan[semester_id].append(code)
            loads[position] += cost
            credits[groups[code]] += cost

            if code in foundation_codes:
                foundation_counts[position] += 1

            backtrack(start + 1)

            # Undo this assignment before trying another semester or skipping it.
            if code in foundation_codes:
                foundation_counts[position] -= 1

            credits[groups[code]] -= cost
            loads[position] -= cost
            plan[semester_id].pop()
            del assignments[code]
            budget.backtracks["scheduling"] += 1

            if budget.limit_reached:
                return

        # Skipping is what allows a useful schedule when the full degree fails.
        if not budget.step("scheduling"):
            return

        backtrack(start + 1)
        budget.backtracks["scheduling"] += 1

    budget.scheduling_attempts += 1
    backtrack(0)
