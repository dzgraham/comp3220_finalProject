# Academic constraints shared by course selection and semester scheduling.

import json
import re
from collections import Counter
from itertools import combinations

COMPUTING_PREFIXES = {"COMP", "INFO", "SWEN"}
MATH_PREFIXES = {"MATH", "STAT"}
# Preserve the existing dataset's faculty classification.
FACULTY_PREFIXES = COMPUTING_PREFIXES | MATH_PREFIXES

_condition_cache = {}

def _condition_terms(expression):
    # Reuse the split result when the same prerequisite rule is checked again.
    if expression not in _condition_cache:
        _condition_cache[expression] = split_conditions(expression)

    return _condition_cache[expression]

def split_conditions(exp):
    # Split only outside parentheses so nested AND/OR rules stay together.
    parts = []
    depth = 0
    start = 0

    for index, char in enumerate(exp):
        if char == "(":
            depth += 1

        elif char == ")":
            depth -= 1

        elif char == ";" and depth == 0:
            parts.append(exp[start:index].strip())
            start = index + 1

    parts.append(exp[start:].strip())

    return parts

def prerequisites_satisfied(course_code, completed_courses, courses, approved_courses=None):
    # Checks whether a student has satisfied the course prerequisites
    if course_code not in courses:
        raise ValueError(f"Unknown course: {course_code}")

    completed = set(completed_courses)
    approved = set(approved_courses or [])

    exp = courses[course_code]["prerequisites"].strip()

    def evaluate(rule):
        # An empty rule or NONE means there are no prerequisites.
        if rule in ("", "NONE"):
            return True

        # All conditions must be satisfied
        if rule.startswith("AND(") and rule.endswith(")"):
            terms = _condition_terms(rule[4:-1])
            return all(evaluate(term) for term in terms)

        # At least one condition must be satisfied
        if rule.startswith("OR(") and rule.endswith(")"):
            terms = _condition_terms(rule[3:-1])
            return any(evaluate(term) for term in terms)

        # Departmental approval
        if rule == "HEAD_PERMISSION":
            return course_code in approved

        # Six additional Level 2/3 Computing credits
        if rule == "6_CREDITS_LVL_2_3_COMP":
            eligible_credits = sum(
                courses[code]["credits"]
                for code in completed
                if code in courses
                and code not in {"COMP2140", "COMP2211"}
                and code.startswith("COMP")
                and courses[code]["level"] in (2, 3)
            )

            return eligible_credits >= 6

        # A prerequisite can refer to a course outside this catalogue.
        if rule in courses or re.fullmatch(r"[A-Z]{4}[0-9]{4}", rule):
            return rule in completed

        raise ValueError(f"Unrecognized condition: {rule}")

    return evaluate(exp)

VALID_TERMS = {"1", "2", "3"}

def build_semesters(years=3, include_summer=False):
    # Generate semesters available for degree planning
    # By default, generate Semester 1 and 2 for each academic year

    if not isinstance(years, int) or years < 1:
        raise ValueError("Years must be a positive integer.")

    terms = ["1", "2"]

    if include_summer:
        terms.append("3")

    semesters = []

    for year in range(1, years + 1):
        for term in terms:
            semesters.append({
                "id": f"Y{year}S{term}",
                "year": year,
                "term": term
            })

    return semesters

def get_offered_terms(course_code, courses):
    # Return the terms in which a course is offered

    if course_code not in courses:
        raise ValueError(f"Unknown course: {course_code}")

    terms = set(courses[course_code]["semesters"])

    if not terms or not terms.issubset(VALID_TERMS):
        raise ValueError(f"Invalid semester terms for {course_code}: {terms}")

    return tuple(sorted(terms, key=int))

def is_course_offered(course_code, term, courses):
    # Check whether a course is offered in a given term

    term = str(term).strip()

    if term not in VALID_TERMS:
        raise ValueError(f"Invalid semester term: {term}")

    return term in get_offered_terms(course_code, courses)

def get_course_domain(course_code, semesters, courses):
    # Return every semester in which a course could initially be scheduled

    return [
        semester
        for semester in semesters
        if is_course_offered(
            course_code,
            semester["term"],
            courses
        )
    ]

def calculate_semester_credits(course_codes, courses):
    # Calculate total credits for a list of courses

    total = 0

    for code in course_codes:
        if code not in courses:
            raise ValueError(f"Unknown course: {code}")

        total += courses[code]["credits"]

    return total

def get_foundation_codes(constraints):
    # Retrieve foundation courses
    codes = set()

    blocks = constraints["foundation_courses"]["required_blocks"]

    for block in blocks:
        if block["type"] == "course":
            codes.add(block["code"])
        elif block["type"] == "choose_one":
            codes.update(block["options"])

    return codes

def semester_load_valid(course_codes, courses, constraints, part="part_1", enforce_minimum=False):
    # Check credit and foundation-course limits
    course_codes = list(course_codes)

    # Prevent duplicate courses in one semester
    if len(course_codes) != len(set(course_codes)):
        return False

    total_credits = calculate_semester_credits(course_codes, courses)

    limits = constraints["registration_limits"][part]

    if total_credits > limits["max_credits_per_semester"]:
        return False

    if enforce_minimum:
        # An unfinished assignment can grow; only check the minimum at the end.
        if total_credits < limits["min_credits_per_semester"]:
            return False

    # Count foundation courses
    foundation_codes = get_foundation_codes(constraints)

    foundation_count = sum(code in foundation_codes for code in course_codes)

    mxFoundation = constraints["foundation_courses"]["max_per_semester"]

    if foundation_count > mxFoundation:
        return False

    return True

WEEKDAYS = {
    "MON", "TUE", "WED", "THU", "FRI"
}

VALID_HALVES = {"", "H1", "H2"}

TIME_PATTERN = re.compile(
    r"(?:[01]\d|2[0-3]):[0-5]\d\Z"
)

def _minutes(value):
    # Convert 24-hour time into minutes after midnight

    if not isinstance(value, str) or not TIME_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid timetable time: {value!r}")

    hours, minutes = map(int, value.split(":"))
    return hours * 60 + minutes

def parse_schedule(raw):
    # Return known meetings and a flag for any missing class times.

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Schedule is not valid JSON") from exc

    if not isinstance(raw, list):
        raise ValueError("Schedule must be a list of meetings")

    meetings = []
    unknown = len(raw) == 0

    for meeting in raw:
        if not isinstance(meeting, dict):
            raise ValueError("Each meeting must be an object")

        day = meeting.get("day")

        # Keep checking the known meetings even when another meeting is TBA.
        if day == "TBA":
            unknown = True
            continue

        if day not in WEEKDAYS:
            raise ValueError(f"Invalid timetable day: {day!r}")

        start = _minutes(meeting.get("start"))
        end = _minutes(meeting.get("end"))

        if start >= end:
            raise ValueError(f"Invalid time: {meeting!r}")

        meetings.append({
            "day": day,
            "start": start,
            "end": end
        })

    return meetings, unknown

def _read_course(course_code, courses):
    # Retrieve and validate a course's timetable

    if course_code not in courses:
        raise ValueError(f"Unknown course: {course_code}")

    course = courses[course_code]

    half = (course.get("half") or "").strip().upper()

    if half not in VALID_HALVES:
        raise ValueError(f"Unknown semester half for {course_code}: {half!r}")

    meetings, unknown = parse_schedule(course["schedule"])

    return{
        "meetings": meetings,
        "unknown": unknown,
        "half": half
    }

def _same_weeks(half_a, half_b):
    # H1 and H2 meet in different weeks and cannot clash with each other.
    # A full-semester course can clash with either half.

    return {half_a, half_b} != {"H1", "H2"}

def _overlap(a, b):
    # Ending at 10:00 does not clash with another class starting at 10:00.
    return(
        a["day"] == b["day"]
        and a["start"] < b["end"]
        and b["start"] < a["end"]
    )

def check_semester_timetable(course_codes, courses, allow_unknown=False):
    # Check known timetable clashes and flag courses with missing times.
    # allow_unknown permits a tentative plan; it does not confirm missing times.

    course_codes = list(course_codes)

    if len(set(course_codes)) != len(course_codes):
        raise ValueError("A course appears more than once in the same semester")

    details = {
        code: _read_course(code, courses)
        for code in course_codes
    }

    unknown_courses = [
        code for code in course_codes if details[code]["unknown"]
    ]

    conflicts = []

    # Compare every pair of courses in the semester
    for first, second in combinations(course_codes, 2):
        a = details[first]
        b = details[second]

        # H1 and H2 never meet during the same weeks
        if not _same_weeks(a["half"], b["half"]):
            continue

        # Compare all known meetings of both courses
        for m1 in a["meetings"]:
            for m2 in b["meetings"]:

                if _overlap(m1, m2):
                    start = max(m1["start"], m2["start"])
                    end = min(m1["end"], m2["end"])

                    conflicts.append({
                        "course_a": first,
                        "course_b": second,
                        "day": m1["day"],
                        "start": (
                            f"{start // 60:02d}:"
                            f"{start % 60:02d}"
                        ),
                        "end": (
                            f"{end // 60:02d}:"
                            f"{end % 60:02d}"
                        )
                    })

    # A known clash takes priority over any unknown class times.
    if conflicts:
        status = "conflict"
    elif unknown_courses:
        status = "tentative"
    else:
        status = "confirmed"

    return{
        "valid": (
            not conflicts
            and (allow_unknown or not unknown_courses)
        ),
        "status": status,
        "conflicts": conflicts,
        "unknown_courses": unknown_courses
    }

class TimetableIndex:
    # Parse each timetable once per planning request and cache pair clashes.

    def __init__(self, courses):
        self.details = {code: _read_course(code, courses) for code in courses}
        self.unknown = {code for code, detail in self.details.items() if detail["unknown"]}
        self.clashes = {code: set() for code in courses}
        for first, second in combinations(courses, 2):
            a, b = self.details[first], self.details[second]
            if _same_weeks(a["half"], b["half"]) and any(
                _overlap(m1, m2) for m1 in a["meetings"] for m2 in b["meetings"]
            ):
                # Store both directions so either course can look up the clash.
                self.clashes[first].add(second)
                self.clashes[second].add(first)


def find_overloaded_term_clique(
    course_codes,
    courses,
    years=3,
    *,
    _timetable=None
):
    # Return an unavoidable single-term clash group, or None.
    # A clique is a group where every course clashes with every other course.
    # Eg: Four Semester 1 courses cannot fit into only three academic years.

    if not isinstance(years, int) or years < 1:
        raise ValueError(
            "years must be a positive integer"
        )

    timetable = _timetable or TimetableIndex({code: courses[code] for code in course_codes if code in courses})
    for term in ("1", "2", "3"):

        # Consider courses offered ONLY in this term.
        only_this_term = sorted(
            code
            for code in course_codes
            if code in courses
            and set(courses[code]["semesters"]) == {term}
        )

        if len(only_this_term) <= years:
            continue

        # Check pairwise timetable conflicts.
        clashes = {}

        for first, second in combinations(
            only_this_term, 2
        ):
            clashes[(first, second)] = second in timetable.clashes[first]

        # Find a group larger than the number of available semesters.
        for group in combinations(
            only_this_term, years + 1
        ):

            if all(
                clashes[(first, second)]
                for first, second in combinations(group, 2)
            ):
                return {
                    "term": term,
                    "courses": list(group),
                    "available_semesters": years
                }

    return None


def validate_semester_plan(
    plan, courses, constraints, semesters, completed_courses=None,
    approved_courses=None, allow_unknown=True, expected_courses=None
):
    # Independently check the semester assignments returned by the solver.

    errors = []
    tentative = set()

    semesters = sorted(semesters, key=lambda s: (s["year"], int(s["term"])))
    ids = {s["id"] for s in semesters}
    scheduled = [code for codes in plan.values() for code in codes]
    prior = set(completed_courses or ())

    if len(scheduled) != len(set(scheduled)):
        errors.append("A course is scheduled more than once")

    if prior.intersection(scheduled):
        errors.append("Completed courses have been rescheduled")

    if set(plan) - ids:
        errors.append("Plan contains an unknown semester")

    # Compare counts too, so a duplicate cannot replace a missing course.
    if expected_courses is not None and Counter(scheduled) != Counter(expected_courses):
        errors.append("Schedule does not contain exactly the requested courses")

    if set(scheduled) - courses.keys():
        errors.append("Schedule contains unknown courses")
        return {"valid": False, "errors": errors, "tentative_courses": []}

    foundations = get_foundation_codes(constraints)

    for semester in semesters:
        codes = plan.get(semester["id"], [])
        if not codes:
            continue

        sid = semester["id"]
        part = "part_1" if semester["year"] == 1 else "part_2"

        if not semester_load_valid(codes, courses, constraints, part, enforce_minimum=True):
            errors.append(f"Credit or foundation count restriction violated in {sid}")

        if semester["year"] > 1:
            minimum = constraints["registration_limits"]["part_1"].get("min_total_credits_for_part_2", 0)
            earned = sum(courses[c]["credits"] for c in prior if c in courses)
            if earned < minimum:
                errors.append(f"Insufficient prior credits to enter Part 2 in {sid}")

        for code in codes:
            if not is_course_offered(code, semester["term"], courses):
                errors.append(f"{code} is not offered in {sid}")

            if code in foundations and semester["year"] > constraints["foundation_courses"]["must_complete_in_year"]:
                errors.append(f"{code} is scheduled after the foundation deadline")

            if not prerequisites_satisfied(code, prior, courses, approved_courses):
                errors.append(f"Prerequisite or approval missing for {code} in {sid}")

        timetable = check_semester_timetable(codes, courses, allow_unknown)
        tentative.update(timetable["unknown_courses"])
        if not timetable["valid"]:
            errors.append(f"Timetable restriction violated in {sid}")

        # Add courses only after checking all prerequisites for this semester.
        prior.update(codes)

    return {"valid": not errors, "errors": errors, "tentative_courses": sorted(tentative)}
