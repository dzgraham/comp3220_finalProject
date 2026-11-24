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
        raise ValueError("Invalid semester term: {term}")

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
