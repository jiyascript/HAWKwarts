
from backend.scheduler.requirement_resolver import (
    resolve_requirements
)

# Test program with a one_of elective requirement.
program = {
    "program_id": "test-elective-one-of",
    "requirements": [
        {
            "name": "Computer Science Electives",
            "items": [
                {
                    "type": "one_of",
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

# Test 1: One elective option already completed.
history = {
    "completed_courses": [
        {"code": "CS 351", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history
)

print("\nTest 1: Completed one_of elective requirement")
print("Expected choice groups: []")
print("Actual choice groups:", result["choice_groups"])

assert result["choice_groups"] == [], (
    "Completing one valid elective must satisfy "
    "a one_of requirement."
)

print("PASS: Completed one_of elective requirement handled correctly.")


# Test 2: No one_of elective options completed.

history_none = {
    "completed_courses": [],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history_none
)

print("\nTest 2: Uncompleted one_of elective requirement")
print("Expected number of choice groups: 1")
print("Actual number of choice groups:", len(result["choice_groups"]))

assert len(result["choice_groups"]) == 1, (
    "An unsatisfied one_of requirement must remain visible."
)

choice = result["choice_groups"][0]

print("Expected options: ['CS 331', 'CS 351', 'CS 425']")
print("Actual options:", choice["options"])
print("Expected required count: 1")
print("Actual required count:", choice["required_count"])
print("Expected remaining count: 1")
print("Actual remaining count:", choice["remaining_count"])

assert choice["options"] == [
    "CS 331", "CS 351", "CS 425"
], (
    "All available elective options must be preserved."
)

assert choice["required_count"] == 1, (
    "A one_of requirement must require exactly one course."
)

assert choice["remaining_count"] == 1, (
    "One elective course must remain when none are completed."
)

assert choice["in_progress_count"] == 0, (
    "No elective courses should be marked in progress."
)

print("PASS: Uncompleted one_of elective requirement handled correctly.")


# Test 3: Partially completed choose requirement.

program_choose = {
    "program_id": "test-elective-choose",
    "requirements": [
        {
            "name": "Advanced Computer Science Electives",
            "items": [
                {
                    "type": "choose",
                    "count": 3,
                    "options": [
                        "CS 331",
                        "CS 351",
                        "CS 425",
                        "CS 430",
                        "CS 450"
                    ]
                }
            ]
        }
    ]
}

history_choose = {
    "completed_courses": [
        {"code": "CS 331", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program_choose,
    student_history=history_choose
)

print("\nTest 3: Partially satisfied choose requirement")
print("Expected number of choice groups: 1")
print("Actual number of choice groups:", len(result["choice_groups"]))

assert len(result["choice_groups"]) == 1, (
    "A partially satisfied choose requirement must remain visible."
)

choice = result["choice_groups"][0]

print("Expected required count: 3")
print("Actual required count:", choice["required_count"])
print("Expected remaining count: 2")
print("Actual remaining count:", choice["remaining_count"])
print("Actual available options:", choice["options"])

assert choice["required_count"] == 3, (
    "The choose requirement must preserve its original count."
)

assert choice["remaining_count"] == 2, (
    "One completed elective should reduce the remaining count "
    "from three to two."
)

assert choice["options"] == [
    "CS 351",
    "CS 425",
    "CS 430",
    "CS 450"
], (
    "Completed courses must be removed from available options."
)

assert choice["in_progress_count"] == 0, (
    "No elective courses should be marked in progress."
)

print("PASS: Partially satisfied choose requirement handled correctly.")


# Test 4: Choose requirement with an elective in progress.

history_choose_in_progress = {
    "completed_courses": [
        {"code": "CS 331", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": [
        {"code": "CS 351"}
    ]
}

result = resolve_requirements(
    program=program_choose,
    student_history=history_choose_in_progress
)

print("\nTest 4: Choose requirement with an elective in progress")
print("Expected number of choice groups: 1")
print("Actual number of choice groups:", len(result["choice_groups"]))

assert len(result["choice_groups"]) == 1, (
    "An incomplete choose requirement must remain visible."
)

choice = result["choice_groups"][0]

print("Expected required count: 3")
print("Actual required count:", choice["required_count"])
print("Expected remaining count: 1")
print("Actual remaining count:", choice["remaining_count"])
print("Expected in-progress count: 1")
print("Actual in-progress count:", choice["in_progress_count"])
print("Actual available options:", choice["options"])

assert choice["required_count"] == 3, (
    "The original elective requirement must remain unchanged."
)

assert choice["remaining_count"] == 1, (
    "Completed and in-progress electives must reduce "
    "the number of additional courses needed."
)

assert choice["in_progress_count"] == 1, (
    "The resolver must track pending elective coursework."
)

assert choice["options"] == [
    "CS 425",
    "CS 430",
    "CS 450"
], (
    "Completed and in-progress courses must not be "
    "recommended as additional elective options."
)

print("PASS: In-progress elective requirement handled correctly.")


# Test 5: Invalid choose requirement configuration.

program_invalid_choose = {
    "program_id": "test-invalid-choose",
    "requirements": [
        {
            "name": "Advanced Computer Science Electives",
            "items": [
                {
                    "type": "choose",
                    "count": 3,
                    "options": [
                        "CS 331",
                        "CS 351"
                    ]
                }
            ]
        }
    ]
}

history_invalid = {
    "completed_courses": [],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program_invalid_choose,
    student_history=history_invalid
)

print("\nTest 5: Invalid choose requirement")
print("Expected choice groups: []")
print("Actual choice groups:", result["choice_groups"])
print("Actual unresolved requirements:", result["unresolved_requirements"])

assert result["choice_groups"] == [], (
    "An invalid choose requirement must not create "
    "an impossible elective choice group."
)

assert len(result["unresolved_requirements"]) == 1, (
    "Invalid elective requirements must be preserved "
    "for further review."
)

unresolved = result["unresolved_requirements"][0]

assert unresolved["type"] == "choose", (
    "The unresolved requirement must preserve its type."
)

assert unresolved["reason"] == "Invalid or incomplete choice group", (
    "The resolver must explain why the requirement "
    "could not be processed."
)

print("PASS: Invalid elective configuration handled safely.")


# Test 6: Duplicate elective options must not be counted twice.

program_duplicates = {
    "program_id": "test-duplicate-electives",
    "requirements": [
        {
            "name": "Computer Science Electives",
            "items": [
                {
                    "type": "choose",
                    "count": 2,
                    "options": [
                        "CS 331",
                        "CS 331",
                        "CS 351",
                        "CS 425"
                    ]
                }
            ]
        }
    ]
}

history_duplicates = {
    "completed_courses": [
        {"code": "CS 331", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program_duplicates,
    student_history=history_duplicates
)

print("\nTest 6: Duplicate elective options")
print("Expected number of choice groups: 1")
print("Actual number of choice groups:", len(result["choice_groups"]))

assert len(result["choice_groups"]) == 1, (
    "One completed course must not satisfy a "
    "two-course elective requirement."
)

choice = result["choice_groups"][0]

print("Expected required count: 2")
print("Actual required count:", choice["required_count"])
print("Expected remaining count: 1")
print("Actual remaining count:", choice["remaining_count"])
print("Expected available options: ['CS 351', 'CS 425']")
print("Actual available options:", choice["options"])

assert choice["required_count"] == 2, (
    "Duplicate options must not change the required count."
)

assert choice["remaining_count"] == 1, (
    "CS 331 must count only once toward the requirement."
)

assert choice["options"] == ["CS 351", "CS 425"], (
    "Duplicate and completed course options must be removed."
)

print("PASS: Duplicate elective options handled correctly.")
