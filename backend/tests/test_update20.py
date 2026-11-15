
from backend.scheduler.requirement_resolver import (
    resolve_requirements
)

# Test 1: End-to-end degree requirement resolution.

program = {
    "program_id": "computer-science:bs-bac-ba",
    "requirements": [
        {
            "name": "Programming Requirements",
            "items": [
                {"type": "course", "course": "CS 115"},
                {"type": "course", "course": "CS 116"}
            ]
        },
        {
            "name": "Mathematics Requirements",
            "items": [
                {"type": "course", "course": "MATH 151"}
            ]
        },
        {
            "name": "Core Computer Science",
            "items": [
                {"type": "course", "course": "CS 450"}
            ]
        },
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
                        "CS 430"
                    ]
                }
            ]
        },
        {
            "name": "Humanities Requirements",
            "items": [
                {
                    "type": "credit_bucket",
                    "credits_required": 6,
                    "subject": "HUM"
                }
            ]
        }
    ]
}

history = {
    "completed_courses": [
        {"code": "CS 201", "grade": "A"},
        {"code": "MATH 151", "grade": "B"},
        {"code": "CS 331", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": [
        {"code": "CS 351"}
    ]
}

result = resolve_requirements(
    program=program,
    student_history=history
)

print("\nTest 1: End-to-end degree requirement resolution")
print("Full result:", result)

# Verify alternative programming pathway.
assert "Programming Sequence" in result["satisfied_pathways"], (
    "CS 201 must satisfy the programming pathway."
)

# Verify completed courses are excluded.
assert "MATH 151" not in result["remaining_courses"], (
    "Completed mathematics courses must not remain required."
)

# Verify outstanding mandatory courses.
assert result["remaining_courses"] == ["CS 450"], (
    "Only CS 450 should remain as a mandatory course."
)

# Verify elective choice group.
assert len(result["choice_groups"]) == 1, (
    "The advanced elective requirement must remain active."
)

choice = result["choice_groups"][0]

assert choice["required_count"] == 3
assert choice["remaining_count"] == 1
assert choice["in_progress_count"] == 1
assert choice["options"] == ["CS 425", "CS 430"]

# Verify unsupported requirements are preserved.
assert len(result["unresolved_requirements"]) == 1

assert result["unresolved_requirements"][0]["type"] == (
    "credit_bucket"
)

print("PASS: End-to-end degree requirement resolution works.")


# Test 2: End-to-end degree audit with verified transfer credits.

program_transfer = {
    "program_id": "computer-science:bs-bac-ba",
    "requirements": [
        {
            "name": "Programming Requirements",
            "items": [
                {"type": "course", "course": "CS 115"},
                {"type": "course", "course": "CS 116"}
            ]
        },
        {
            "name": "Mathematics Requirements",
            "items": [
                {"type": "course", "course": "MATH 151"}
            ]
        },
        {
            "name": "Core Computer Science",
            "items": [
                {"type": "course", "course": "CS 450"}
            ]
        },
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
                        "CS 430"
                    ]
                }
            ]
        }
    ]
}

history_transfer = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"},
        {"code": "MATH 151", "grade": "B"}
    ],
    "transfer_courses": [
        {
            "code": "CS 116",
            "equivalency_verified": True
        },
        {
            "code": "CS 331",
            "equivalency_verified": True
        },
        {
            "code": "CS 425",
            "equivalency_verified": False
        }
    ],
    "in_progress_courses": [
        {"code": "CS 351"}
    ]
}

result = resolve_requirements(
    program=program_transfer,
    student_history=history_transfer
)

print("\nTest 2: End-to-end degree audit with transfer credits")
print("Full result:", result)

# Verify programming pathway.
assert "Programming Sequence" in result["satisfied_pathways"], (
    "CS 115 plus verified transfer CS 116 must satisfy "
    "the programming pathway."
)

# Verify completed and transferred mandatory courses.
assert result["remaining_courses"] == ["CS 450"], (
    "Only CS 450 should remain mandatory."
)

# Verify elective requirements.
assert len(result["choice_groups"]) == 1, (
    "The elective requirement should remain active."
)

choice = result["choice_groups"][0]

assert choice["required_count"] == 3, (
    "Three elective courses must be required."
)

assert choice["remaining_count"] == 1, (
    "One additional elective must remain."
)

assert choice["in_progress_count"] == 1, (
    "CS 351 must count as an in-progress elective."
)

assert choice["options"] == ["CS 425", "CS 430"], (
    "Unverified CS 425 must remain an available option."
)

# Verify no unexpected unresolved requirements.
assert result["unresolved_requirements"] == [], (
    "All requirements in this scenario should be structured."
)

print("PASS: End-to-end transfer credit resolution works.")


# Test 3: End-to-end audit with a partially completed pathway.

history_partial_pathway = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"},
        {"code": "MATH 151", "grade": "B"},
        {"code": "CS 331", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": [
        {"code": "CS 351"}
    ]
}

result = resolve_requirements(
    program=program_transfer,
    student_history=history_partial_pathway
)

print("\nTest 3: End-to-end audit with partial programming pathway")
print("Full result:", result)

# Programming pathway must not be marked satisfied.
assert result["satisfied_pathways"] == [], (
    "A partially completed programming pathway "
    "must not be marked satisfied."
)

# The partially completed pathway must remain visible.
assert len(result["unsatisfied_pathways"]) == 1, (
    "The unfinished programming pathway must be preserved."
)

pathway = result["unsatisfied_pathways"][0]

assert pathway["name"] == "Programming Sequence"

assert pathway["recommended_pathway"] == [
    "CS 115",
    "CS 116"
], (
    "The resolver should recommend continuing "
    "the already-started programming sequence."
)

assert pathway["remaining_courses"] == ["CS 116"], (
    "CS 116 should remain necessary to finish "
    "the selected programming pathway."
)

# Verify outstanding mandatory courses.
assert result["remaining_courses"] == ["CS 450"], (
    "Only CS 450 should remain in the mandatory "
    "course list outside the programming pathway."
)

# Verify elective requirements.
assert len(result["choice_groups"]) == 1

choice = result["choice_groups"][0]

assert choice["required_count"] == 3
assert choice["remaining_count"] == 1
assert choice["in_progress_count"] == 1
assert choice["options"] == ["CS 425", "CS 430"]

# No unsupported requirements in this scenario.
assert result["unresolved_requirements"] == []

print("PASS: Partial programming pathway resolved correctly.")


# Test 4: End-to-end audit with programming pathway in progress.

history_pending_pathway = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"},
        {"code": "MATH 151", "grade": "B"},
        {"code": "CS 331", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": [
        {"code": "CS 116"},
        {"code": "CS 351"}
    ]
}

result = resolve_requirements(
    program=program_transfer,
    student_history=history_pending_pathway
)

print("\nTest 4: End-to-end audit with pending programming pathway")
print("Full result:", result)

# The programming pathway is not yet completed.
assert result["satisfied_pathways"] == [], (
    "An in-progress pathway must not be marked satisfied."
)

# The pathway should be classified as pending.
assert result["pending_pathways"] == ["Programming Sequence"], (
    "CS 115 completed and CS 116 in progress "
    "must produce a pending programming pathway."
)

# It should not be classified as unsatisfied.
assert result["unsatisfied_pathways"] == [], (
    "A pathway with all remaining courses in progress "
    "should not be classified as unsatisfied."
)

# Verify mandatory requirements.
assert result["remaining_courses"] == ["CS 450"], (
    "CS 450 should remain the only outstanding "
    "mandatory course outside the pathway."
)

# Verify elective requirement.
assert len(result["choice_groups"]) == 1

choice = result["choice_groups"][0]

assert choice["required_count"] == 3
assert choice["remaining_count"] == 1
assert choice["in_progress_count"] == 1
assert choice["options"] == ["CS 425", "CS 430"]

# No unresolved requirements should exist.
assert result["unresolved_requirements"] == []

print("PASS: Pending programming pathway resolved correctly.")


# Test 5: End-to-end audit with all structured requirements completed.

history_fully_completed = {
    "completed_courses": [
        {"code": "CS 201", "grade": "A"},
        {"code": "MATH 151", "grade": "A"},
        {"code": "CS 450", "grade": "B"},
        {"code": "CS 331", "grade": "A"},
        {"code": "CS 351", "grade": "B"},
        {"code": "CS 425", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program_transfer,
    student_history=history_fully_completed
)

print("\nTest 5: Fully completed degree requirements")
print("Full result:", result)

# Programming pathway must be satisfied.
assert result["satisfied_pathways"] == ["Programming Sequence"], (
    "CS 201 must satisfy the alternative programming pathway."
)

# No unfinished programming pathways.
assert result["pending_pathways"] == [], (
    "No programming pathway should remain pending."
)

assert result["unsatisfied_pathways"] == [], (
    "No programming pathway should remain unsatisfied."
)

# No mandatory courses should remain.
assert result["remaining_courses"] == [], (
    "All mandatory course requirements should be completed."
)

# No mandatory courses should be in progress.
assert result["in_progress_requirements"] == [], (
    "No mandatory requirements should remain in progress."
)

# All three electives are completed.
assert result["choice_groups"] == [], (
    "The completed elective requirement must not remain active."
)

# No unsupported requirements in this scenario.
assert result["unresolved_requirements"] == [], (
    "All requirements in this scenario should be structured."
)

# The resolver must still indicate preliminary status.
assert result["status"] == "preliminary", (
    "A completed structured audit must not be presented "
    "as official graduation clearance."
)

print("PASS: Fully completed structured degree audit resolved correctly.")
