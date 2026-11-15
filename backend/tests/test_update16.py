
from backend.scheduler.requirement_resolver import (
    resolve_requirements
)


program = {
    "program_id": "test-transfer-credit",
    "requirements": [
        {
            "name": "Core Computer Science",
            "items": [
                {"type": "course", "course": "CS 115"},
                {"type": "course", "course": "CS 116"},
                {"type": "course", "course": "CS 201"}
            ]
        }
    ]
}


history = {
    "completed_courses": [
        {
            "code": "CS 115",
            "grade": "A",
            "credits": 3
        }
    ],
    "transfer_courses": [
        {
            "code": "CS 116",
            "credits": 3,
            "equivalency_verified": True
        }
    ],
    "in_progress_courses": []
}


result = resolve_requirements(
    program=program,
    student_history=history
)

print("\nTest 1: Completed and verified transfer courses")
print("Expected remaining courses: ['CS 201']")
print("Actual remaining courses:", result["remaining_courses"])

assert result["remaining_courses"] == ["CS 201"], (
    "Completed and verified transfer courses "
    "must not be scheduled again."
)

print("PASS: Completed and transfer credits handled correctly.")


# Test 2: Unverified transfer courses must not
# automatically satisfy degree requirements.

history_unverified = {
    "completed_courses": [
        {
            "code": "CS 115",
            "grade": "A",
            "credits": 3
        }
    ],
    "transfer_courses": [
        {
            "code": "CS 116",
            "credits": 3,
            "equivalency_verified": False
        }
    ],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history_unverified
)

print("\nTest 2: Unverified transfer equivalency")
print("Expected remaining courses: ['CS 116', 'CS 201']")
print("Actual remaining courses:", result["remaining_courses"])

assert result["remaining_courses"] == ["CS 116", "CS 201"], (
    "Unverified transfer courses must not automatically "
    "satisfy degree requirements."
)

print("PASS: Unverified transfer credits handled safely.")


# Test 3: Verified transfer credits satisfy elective choices.

program_electives = {
    "program_id": "test-transfer-electives",
    "requirements": [
        {
            "name": "Computer Science Electives",
            "items": [
                {
                    "type": "choose",
                    "count": 2,
                    "options": [
                        "CS 331",
                        "CS 351",
                        "CS 425"
                    ]
                }
            ]
        }
    ]
}

history_electives = {
    "completed_courses": [
        {
            "code": "CS 331",
            "grade": "A"
        }
    ],
    "transfer_courses": [
        {
            "code": "CS 351",
            "equivalency_verified": True
        }
    ],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program_electives,
    student_history=history_electives
)

print("\nTest 3: Verified transfer credits in elective groups")
print("Expected choice groups: []")
print("Actual choice groups:", result["choice_groups"])

assert result["choice_groups"] == [], (
    "Verified transfer credits must count toward "
    "elective-choice requirements."
)

print("PASS: Transfer credits satisfy elective requirements.")


# Test 4: Verified transfer credits satisfy alternative pathways.

from unittest.mock import patch

program_pathways = {
    "program_id": "test-transfer-pathways",
    "requirements": [
        {
            "name": "Programming Foundation",
            "items": [
                {"type": "course", "course": "CS 115"},
                {"type": "course", "course": "CS 116"}
            ]
        }
    ]
}

history_pathways = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"}
    ],
    "transfer_courses": [
        {
            "code": "CS 116",
            "equivalency_verified": True
        }
    ],
    "in_progress_courses": []
}

pathway_rules = [
    {
        "name": "Programming Foundation",
        "options": [
            ["CS 115", "CS 116"],
            ["CS 201"]
        ],
        "replaces": ["CS 115", "CS 116", "CS 201"]
    }
]

with patch(
    "backend.scheduler.requirement_resolver.load_program_pathways",
    return_value=pathway_rules
):
    result = resolve_requirements(
        program=program_pathways,
        student_history=history_pathways
    )

print("\nTest 4: Verified transfer credits in alternative pathways")
print("Expected satisfied pathways: ['Programming Foundation']")
print("Actual satisfied pathways:", result["satisfied_pathways"])
print("Actual remaining courses:", result["remaining_courses"])

assert result["satisfied_pathways"] == ["Programming Foundation"], (
    "Verified transfer credits must satisfy "
    "alternative degree pathways."
)

assert result["remaining_courses"] == [], (
    "Satisfied pathways must not create duplicate "
    "mandatory course requirements."
)

print("PASS: Transfer credits satisfy alternative pathways.")
