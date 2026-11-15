
from backend.scheduler.requirement_resolver import (
    resolve_requirements
)

# Test program using the actual pathway configuration.
program = {
    "program_id": "computer-science:bs-bac-ba",
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

# Test 1: CS 201 satisfies the alternative programming pathway.
history = {
    "completed_courses": [
        {"code": "CS 201", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history
)

print("\nTest 1: CS 201 alternative programming pathway")
print("Expected satisfied pathways: ['Programming Sequence']")
print("Actual satisfied pathways:", result["satisfied_pathways"])
print("Expected remaining courses: []")
print("Actual remaining courses:", result["remaining_courses"])

assert result["satisfied_pathways"] == ["Programming Sequence"], (
    "CS 201 must satisfy the alternative programming pathway."
)

assert result["remaining_courses"] == [], (
    "Students who completed CS 201 must not be required "
    "to take CS 115 or CS 116."
)

assert result["unsatisfied_pathways"] == [], (
    "A completed programming pathway must not remain unsatisfied."
)

print("PASS: CS 201 satisfies the programming requirement.")


# Test 2: CS 115 + CS 116 satisfy the programming pathway.

history_sequence = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"},
        {"code": "CS 116", "grade": "B"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history_sequence
)

print("\nTest 2: CS 115 + CS 116 programming pathway")
print("Expected satisfied pathways: ['Programming Sequence']")
print("Actual satisfied pathways:", result["satisfied_pathways"])
print("Expected remaining courses: []")
print("Actual remaining courses:", result["remaining_courses"])

assert result["satisfied_pathways"] == ["Programming Sequence"], (
    "Completing CS 115 and CS 116 must satisfy "
    "the programming pathway."
)

assert result["remaining_courses"] == [], (
    "Students who completed CS 115 and CS 116 "
    "must not have additional programming requirements."
)

assert result["unsatisfied_pathways"] == [], (
    "A completed programming pathway must not remain unsatisfied."
)

print("PASS: CS 115 + CS 116 satisfy the programming requirement.")


# Test 3: Student completed CS 115 but not CS 116.

history_partial = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history_partial
)

print("\nTest 3: Partially completed programming pathway")
print("Expected satisfied pathways: []")
print("Actual satisfied pathways:", result["satisfied_pathways"])
print("Actual unsatisfied pathways:", result["unsatisfied_pathways"])

assert result["satisfied_pathways"] == [], (
    "Completing only CS 115 must not satisfy "
    "the entire programming pathway."
)

assert len(result["unsatisfied_pathways"]) == 1, (
    "A partially completed pathway must remain unresolved."
)

pathway = result["unsatisfied_pathways"][0]

print("Expected recommended pathway: ['CS 115', 'CS 116']")
print("Actual recommended pathway:", pathway["recommended_pathway"])
print("Expected remaining courses: ['CS 116']")
print("Actual remaining courses:", pathway["remaining_courses"])

assert pathway["recommended_pathway"] == ["CS 115", "CS 116"], (
    "The resolver should recommend continuing "
    "the already-started programming sequence."
)

assert pathway["remaining_courses"] == ["CS 116"], (
    "Only CS 116 should remain in the started pathway."
)

print("PASS: Partial programming pathway handled correctly.")


# Test 4: CS 115 completed and CS 116 in progress.

history_in_progress = {
    "completed_courses": [
        {"code": "CS 115", "grade": "A"}
    ],
    "transfer_courses": [],
    "in_progress_courses": [
        {"code": "CS 116"}
    ]
}

result = resolve_requirements(
    program=program,
    student_history=history_in_progress
)

print("\nTest 4: Programming pathway in progress")
print("Expected satisfied pathways: []")
print("Actual satisfied pathways:", result["satisfied_pathways"])
print("Expected pending pathways: ['Programming Sequence']")
print("Actual pending pathways:", result["pending_pathways"])
print("Expected unsatisfied pathways: []")
print("Actual unsatisfied pathways:", result["unsatisfied_pathways"])

assert result["satisfied_pathways"] == [], (
    "An in-progress course must not count as completed."
)

assert result["pending_pathways"] == ["Programming Sequence"], (
    "A pathway with all courses completed or in progress "
    "must be marked pending."
)

assert result["unsatisfied_pathways"] == [], (
    "A pending pathway must not also be marked unsatisfied."
)

assert result["remaining_courses"] == [], (
    "Courses already in progress must not be scheduled again."
)

print("PASS: In-progress programming pathway handled correctly.")


# Test 5: Student has not started either programming pathway.

history_not_started = {
    "completed_courses": [],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history_not_started
)

print("\nTest 5: No programming pathway started")
print("Expected satisfied pathways: []")
print("Actual satisfied pathways:", result["satisfied_pathways"])
print("Expected pending pathways: []")
print("Actual pending pathways:", result["pending_pathways"])
print("Actual unsatisfied pathways:", result["unsatisfied_pathways"])

assert result["satisfied_pathways"] == [], (
    "An unstarted pathway must not be marked satisfied."
)

assert result["pending_pathways"] == [], (
    "An unstarted pathway must not be marked pending."
)

assert len(result["unsatisfied_pathways"]) == 1, (
    "The unresolved programming requirement must be preserved."
)

pathway = result["unsatisfied_pathways"][0]

assert pathway["options"] == [
    ["CS 115", "CS 116"],
    ["CS 201"]
], (
    "Both valid programming pathways must remain available."
)

assert pathway["recommended_pathway"] is None, (
    "The resolver must not automatically select a pathway "
    "when neither option has been started."
)

assert pathway["reason"] == (
    "No pathway started; selection required"
), (
    "The resolver must indicate that pathway selection is required."
)

print("PASS: Unstarted programming pathways preserved correctly.")
