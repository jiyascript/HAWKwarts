
from backend.scheduler.prerequisite_validator import (
    validate_prerequisite_for_term
)


def make_history(grade=None):
    completed = []

    if grade is not None:
        completed.append({
            "code": "CS 115",
            "grade": grade,
            "credits": 3
        })

    return {
        "completed_courses": completed,
        "transfer_courses": [],
        "in_progress_courses": []
    }


test_cases = [
    # Name, grade, minimum grade, target term,
    # prerequisite term, concurrency allowed, expected
    ("Grade A meets C minimum",
     "A", "C", 1, None, False, "satisfied"),

    ("Grade D fails C minimum",
     "D", "C", 1, None, False, "not_satisfied"),

    ("Prerequisite in earlier semester",
     None, "C", 1, 0, False, "conditional"),

    ("Same semester, concurrency allowed",
     None, "C", 1, 1, True, "conditional"),

    ("Same semester, concurrency prohibited",
     None, "C", 1, 1, False, "not_satisfied"),

    ("Prerequisite in later semester",
     None, "C", 1, 2, False, "not_satisfied"),

    ("Missing prerequisite entirely",
     None, "C", 1, None, False, "not_satisfied")
]


for (
    name,
    grade,
    minimum_grade,
    target_term,
    prerequisite_term,
    concurrent_allowed,
    expected
) in test_cases:

    result = validate_prerequisite_for_term(
        prerequisite_code="CS 115",
        minimum_grade=minimum_grade,
        history=make_history(grade),
        target_term=target_term,
        prerequisite_term=prerequisite_term,
        concurrent_allowed=concurrent_allowed
    )

    actual = result["status"]

    print(f"\nTest: {name}")
    print(f"Expected: {expected}")
    print(f"Actual:   {actual}")

    assert actual == expected, (
        f"FAILED: {name} - expected {expected}, got {actual}"
    )

    print("PASS")

print("\nAll 7 grade and semester-timing tests passed.")

