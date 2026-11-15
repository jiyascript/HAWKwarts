
from backend.scheduler.requirement_resolver import (
    resolve_requirements
)

# Test 1: Unsupported degree requirement type.

program = {
    "program_id": "test-unresolved-requirements",
    "requirements": [
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
    "completed_courses": [],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = resolve_requirements(
    program=program,
    student_history=history
)

print("\nTest 1: Unsupported degree requirement type")
print("Expected unresolved requirements: 1")
print("Actual unresolved requirements:", len(result["unresolved_requirements"]))
print("Full unresolved requirements:", result["unresolved_requirements"])

assert len(result["unresolved_requirements"]) == 1, (
    "Unsupported degree requirements must not be silently dropped."
)

unresolved = result["unresolved_requirements"][0]

assert unresolved["group"] == "Humanities Requirements", (
    "The original requirement group must be preserved."
)

assert unresolved["type"] == "credit_bucket", (
    "The unsupported requirement type must be preserved."
)

assert unresolved["item"]["credits_required"] == 6, (
    "The original credit requirement must be preserved."
)

assert result["remaining_courses"] == [], (
    "Unsupported requirements must not generate invented courses."
)

print("PASS: Unsupported degree requirement preserved safely.")


# Test 2: Requirement group with missing or empty items.

program_empty_group = {
    "program_id": "test-empty-requirement-group",
    "requirements": [
        {
            "name": "Mathematics Requirements",
            "items": []
        }
    ]
}

result = resolve_requirements(
    program=program_empty_group,
    student_history=history
)

print("\nTest 2: Empty degree requirement group")
print("Expected unresolved requirements: 1")
print("Actual unresolved requirements:", len(result["unresolved_requirements"]))
print("Full unresolved requirements:", result["unresolved_requirements"])

assert len(result["unresolved_requirements"]) == 1, (
    "Empty requirement groups must not be silently dropped."
)

unresolved = result["unresolved_requirements"][0]

assert unresolved["group"] == "Mathematics Requirements", (
    "The original requirement group name must be preserved."
)

assert unresolved["reason"] == (
    "No structured requirement items available"
), (
    "The resolver must explain why the requirement "
    "could not be processed."
)

assert result["remaining_courses"] == [], (
    "Missing requirement data must not generate invented courses."
)

print("PASS: Empty degree requirement group preserved safely.")


# Test 3: Course requirement with a missing course code.

program_missing_course = {
    "program_id": "test-missing-course-code",
    "requirements": [
        {
            "name": "Core Computer Science",
            "items": [
                {
                    "type": "course",
                    "course": ""
                }
            ]
        }
    ]
}

result = resolve_requirements(
    program=program_missing_course,
    student_history=history
)

print("\nTest 3: Missing course code")
print("Expected unresolved requirements: 1")
print("Actual unresolved requirements:", len(result["unresolved_requirements"]))
print("Full unresolved requirements:", result["unresolved_requirements"])

assert len(result["unresolved_requirements"]) == 1, (
    "Course requirements with missing codes must not "
    "be silently dropped."
)

unresolved = result["unresolved_requirements"][0]

assert unresolved["group"] == "Core Computer Science", (
    "The original requirement group must be preserved."
)

assert unresolved["type"] == "course", (
    "The original requirement type must be preserved."
)

assert unresolved["reason"] == "Missing course code", (
    "The resolver must explain why the course "
    "requirement could not be processed."
)

print("PASS: Missing course code preserved safely.")


# Test 4: Multiple unresolved requirements in one program.

program_multiple_unresolved = {
    "program_id": "test-multiple-unresolved",
    "requirements": [
        {
            "name": "Mathematics Requirements",
            "items": [
                {
                    "type": "course",
                    "course": "MATH 151"
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
        },
        {
            "name": "Core Computer Science",
            "items": [
                {
                    "type": "course",
                    "course": ""
                }
            ]
        }
    ]
}

result = resolve_requirements(
    program=program_multiple_unresolved,
    student_history=history
)

print("\nTest 4: Multiple unresolved requirements")
print("Expected remaining courses: ['MATH 151']")
print("Actual remaining courses:", result["remaining_courses"])
print("Expected unresolved requirements: 2")
print("Actual unresolved requirements:", len(result["unresolved_requirements"]))
print("Full unresolved requirements:", result["unresolved_requirements"])

assert result["remaining_courses"] == ["MATH 151"], (
    "Valid course requirements must still be processed."
)

assert len(result["unresolved_requirements"]) == 2, (
    "All unresolved requirements must be preserved."
)

unresolved_groups = {
    item["group"]
    for item in result["unresolved_requirements"]
}

assert unresolved_groups == {
    "Humanities Requirements",
    "Core Computer Science"
}, (
    "Both unresolved requirement groups must be preserved."
)

print("PASS: Multiple unresolved requirements handled correctly.")


# Test 5: Course requirement with no course field.

program_missing_field = {
    "program_id": "test-missing-course-field",
    "requirements": [
        {
            "name": "Required Computer Science Courses",
            "items": [
                {
                    "type": "course"
                }
            ]
        }
    ]
}

result = resolve_requirements(
    program=program_missing_field,
    student_history=history
)

print("\nTest 5: Missing course field")
print("Expected unresolved requirements: 1")
print("Actual unresolved requirements:", len(result["unresolved_requirements"]))
print("Full unresolved requirements:", result["unresolved_requirements"])

assert len(result["unresolved_requirements"]) == 1, (
    "A missing course field must not cause "
    "the requirement to be silently dropped."
)

unresolved = result["unresolved_requirements"][0]

assert unresolved["group"] == "Required Computer Science Courses", (
    "The requirement group must be preserved."
)

assert unresolved["type"] == "course", (
    "The requirement type must be preserved."
)

assert unresolved["reason"] == "Missing course code", (
    "The resolver must explain the missing course field."
)

assert result["remaining_courses"] == [], (
    "The resolver must not invent a course code."
)

print("PASS: Missing course field handled safely.")
