# Small sample datasets shared by the search tests.

from copy import deepcopy

from csp.data import load_constraints


def make_course(level=1, terms=("1",), prerequisite="NONE", day="MON", half="",
                start="09:00", end="10:00"):
    # Return a new dictionary so one test cannot change another test's course.
    return {
        "title": "Controlled test course", "credits": 3, "level": level,
        "semesters": list(terms), "prerequisites": prerequisite, "half": half,
        "schedule": [{"day": day, "start": start, "end": end}]
    }


def make_degree_fixture():
    # This fictional degree needs one Level 1 course and one advanced elective.
    # COMP2001 looks valid during selection but cannot follow its prerequisite
    # within one year. COMP2002 provides the alternative that can be scheduled.
    courses = {
        "COMP1001": make_course(),
        "COMP2001": make_course(2, ("1",), "COMP1001", "TUE"),
        "COMP2002": make_course(2, ("2",), "COMP1001", "TUE")
    }
    constraints = deepcopy(load_constraints())
    constraints["university_rules"].update({
        "total_credits_for_degree": 6, "level_1_credits_required": 3,
        "level_2_3_credits_required": 3, "foundation_credits_required": 0,
        "min_in_faculty_level_1_credits": 3,
        "min_in_faculty_level_2_3_credits": 3
    })
    constraints["foundation_courses"]["required_blocks"] = []
    tracks = {
        "majors": {"test": {
            "name": "Fictional degree", "level1_required": ["COMP1001"],
            "advanced_required": [], "elective_blocks": [{
                "id": "electives", "type": "choose_credits", "credits": 3,
                "from_level": [2], "from_dept": "Computing"
            }]
        }},
        "tracks": {"preferred": {"preferred_electives": ["COMP2001"]}}
    }
    return courses, constraints, tracks
