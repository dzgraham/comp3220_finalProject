# Dataset loading and degree requirement blueprints.

import csv
import json
from pathlib import Path

# Find data relative to this file, even when Python runs from another folder.
BASE_DIR = Path(__file__).resolve().parent.parent

def load_courses():
    courses = {}

    with open(
        BASE_DIR / "courses.csv",
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            code = row["code"].strip()

            # Convert numeric text to numbers and split the offered terms.
            courses[code] = {
                "title": row["title"],
                "credits": int(row["credits"]),
                "level": int(row["level"]),
                "semesters": [
                    s.strip()
                    for s in row["semester_offered"].split(",")
                ],
                "prerequisites": row["prerequisites_parsed"],
                "schedule": row["schedule"],
                "half": row["half"]
            }

    return courses


def load_constraints():
    with open(
        BASE_DIR / "constraints.json",
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def load_tracks():
    with open(
        BASE_DIR / "tracks2.json",
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def get_track_preferences(tracks, track=None, math_track=None):
    # Specializations are shared by every major; math is a separate opt-in.
    preferred = []
    for category, choice, label in (
        ("tracks", track, "track"),
        ("math_tracks", math_track, "math track")
    ):
        if choice is None:
            continue
        options = tracks.get(category, {})
        if choice not in options:
            raise ValueError(f"Unknown {label}: {choice}")
        for code in options[choice]["preferred_electives"]:
            if code not in preferred:
                preferred.append(code)
    return preferred


def get_degree_blueprint(major, courses, constraints, tracks):
    # Get mandatory courses and remaining credit requirements for a selected major.
    majors = tracks["majors"]

    if major not in majors:
        raise ValueError(f"Unknown major: {major}")

    specification = majors[major]

    required_level1 = specification["level1_required"]
    required_advanced = specification["advanced_required"]

    required = required_level1 + required_advanced

    if len(required) != len(set(required)):
        raise ValueError("Duplicate required course")

    # Check that every compulsory course exists and has the expected level.
    for code in required:
        if code not in courses:
            raise ValueError(
                f"Major requires unknown course: {code}"
            )

    for code in required_level1:
        if courses[code]["level"] != 1:
            raise ValueError(
                f"Expected Level 1 course: {code}"
            )

    for code in required_advanced:
        if courses[code]["level"] not in (2, 3):
            raise ValueError(
                f"Expected Level 2/3 course: {code}"
            )

    credits_level1 = sum(
        courses[code]["credits"]
        for code in required_level1
    )

    credits_advanced = sum(
        courses[code]["credits"]
        for code in required_advanced
    )

    # Read credit targets from JSON rather than hard-coding them here.
    rules = constraints["university_rules"]

    foundation_blocks = constraints[
        "foundation_courses"
    ]["required_blocks"]

    foundation_credits = sum(
        block["credits"]
        for block in foundation_blocks
    )

    targets = {
        "total": rules["total_credits_for_degree"],
        "level1": rules["level_1_credits_required"],
        "advanced": rules["level_2_3_credits_required"],
        "foundation": foundation_credits
    }

    if foundation_credits != rules["foundation_credits_required"]:
        raise ValueError("Foundation credit mismatch")

    if (
        targets["level1"]
        + targets["advanced"]
        + targets["foundation"]
        != targets["total"]
    ):
        raise ValueError("Degree credit totals do not match")

    # Electives only need to fill the credits left after compulsory courses.
    remaining_level1 = targets["level1"] - credits_level1
    remaining_advanced = (
        targets["advanced"] - credits_advanced
    )

    if remaining_level1 < 0 or remaining_advanced < 0:
        raise ValueError(
            "Required courses exceed degree credit limits"
        )

    return {
        "major": major,
        "name": specification["name"],
        "required_level1": list(required_level1),
        "required_advanced": list(required_advanced),
        "foundation_blocks": foundation_blocks,
        "elective_blocks": specification["elective_blocks"],
        "targets": targets,
        "core_credits": {
            "level1": credits_level1,
            "advanced": credits_advanced
        },
        "remaining_credits": {
            "level1": remaining_level1,
            "advanced": remaining_advanced
        }
    }


