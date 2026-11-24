
from csp.data_loader import load_courses, load_constraints
from csp.prerequisites import prerequisites_satisfied


def main():
    courses = load_courses()
    constraints = load_constraints()

    print("Total courses loaded:", len(courses))

    print(
        "Maximum semester credits:",
        constraints["registration_limits"]["part_1"][
            "max_credits_per_semester"
        ]
    )

    print(
        "COMP1161 prerequisites met:",
        prerequisites_satisfied(
            "COMP1161",
            {"COMP1126", "COMP1127"},
            courses
        )
    )


if __name__ == "__main__":
    main()
