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
        if total_credits < limits["min_credits_per_semester"]:
            return False 

    # Count foundation courses 
    foundation_codes = get_foundation_codes(constraints)

    foundation_count = sum(code in foundation_codes for code in course_codes)

    mxFoundation = constraints["foundation_courses"]["max_per_semester"]

    if foundation_count > mxFoundation:
        return False

    return True 
