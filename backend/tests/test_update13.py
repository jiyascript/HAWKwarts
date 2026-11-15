
from backend.scheduler.prerequisite_validator import (
    evaluate_prerequisite_expression_for_term
)

# (CS 115 AND CS 116) OR CS 201
expression = {
    "type": "OR",
    "children": [
        {
            "type": "AND",
            "children": [
                {"type": "course", "code": "CS 115"},
                {"type": "course", "code": "CS 116"}
            ]
        },
        {"type": "course", "code": "CS 201"}
    ]
}

def make_history(codes):
    return {
        "completed_courses": [
            {
                "code": code,
                "grade": "A",
                "credits": 3
            }
            for code in codes
        ],
        "transfer_courses": [],
        "in_progress_courses": []
    }


test_cases = [
    (
        "Both CS 115 and CS 116 completed",
        ["CS 115", "CS 116"],
        "satisfied"
    ),
    (
        "Only CS 201 completed",
        ["CS 201"],
        "satisfied"
    ),
    (
        "Only CS 115 completed",
        ["CS 115"],
        "not_satisfied"
    ),
    (
        "No prerequisites completed",
        [],
        "not_satisfied"
    ),
    (
        "All three courses completed",
        ["CS 115", "CS 116", "CS 201"],
        "satisfied"
    )
]


for name, completed_codes, expected in test_cases:
    result = evaluate_prerequisite_expression_for_term(
        expression=expression,
        history=make_history(completed_codes),
        target_term=1,
        planned_terms={},
        detail_lookup={}
    )

    actual = result["status"]

    print(f"\nTest: {name}")
    print(f"Expected: {expected}")
    print(f"Actual:   {actual}")

    assert actual == expected, (
        f"FAILED: {name} - expected {expected}, got {actual}"
    )

    print("PASS")

print("\nAll 5 nested AND/OR regression tests passed.")
