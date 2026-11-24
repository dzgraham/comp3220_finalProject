def split_conditions(exp):
    # Split conditions separated by semicolons, preserving nested AND/OR expressions 

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
        # No prerequisistes 
        if rule in ("", "NONE"):
            return True 

        # All conditions must be satisfied 
        if rule.startswith("AND(") and rule.endswith(")"):
            terms = split_conditions(rule[4:-1])
            return all(evaluate(term) for term in terms)

        # At least one condition must be satisfied
        if rule.startswith("OR(") and rule.endswith(")"):
            terms = split_conditions(rule[3:-1])
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

        # Individual course prerequisite 
        if rule in courses:
            return rule in completed 

        raise ValueError(f"Unrecognized condition: {rule}")
    
    return evaluate(exp)