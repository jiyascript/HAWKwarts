
from backend.scheduler.prerequisite_validator import (
    validate_course_prerequisites
)


history = {
    "completed_courses": [],
    "transfer_courses": [],
    "in_progress_courses": []
}

course = {
    "course_id": "TEST 499",
    "prerequisites": "Instructor permission required",
    "general_requirements": ""
}

result = validate_course_prerequisites(
    course=course,
    history=history
)

print("\nTest 1: Unsupported prerequisite expression")
print("Expected status: unverified")
print("Actual status:", result["status"])
print("Full result:", result)

assert result["status"] == "unverified", (
    "Unsupported prerequisites must not be treated as eligible."
)

print("PASS: Unsupported prerequisite handled safely.")


# Test 2: Unsupported Banner general requirements.

course_with_unsupported_general = {
    "course_id": "TEST 498",
    "prerequisites": "CS 115",
    "general_requirements": "Department approval required"
}

result = validate_course_prerequisites(
    course=course_with_unsupported_general,
    history=history
)

print("\nTest 2: Unsupported Banner general requirements")
print("Expected status: unverified")
print("Actual status:", result["status"])
print("Full result:", result)

assert result["status"] == "unverified", (
    "Unsupported Banner general requirements must not "
    "be treated as eligible."
)

print("PASS: Unsupported Banner general requirements handled safely.")


# Test 3: Unsupported Banner requirements during
# semester-specific prerequisite validation.

from backend.scheduler.prerequisite_validator import (
    validate_banner_prerequisites_for_term
)

course_with_unsupported_term_requirement = {
    "course_id": "TEST 497",
    "prerequisites": "CS 115",
    "general_requirements": "Department approval required"
}

result = validate_banner_prerequisites_for_term(
    course=course_with_unsupported_term_requirement,
    history=history,
    target_term=1,
    planned_terms={}
)

print("\nTest 3: Unsupported semester-specific Banner requirement")
print("Expected status: unverified")
print("Actual status:", result["status"])
print("Full result:", result)

assert result["status"] == "unverified", (
    "Semester-specific validation must not approve "
    "unsupported Banner requirements."
)

print("PASS: Semester-specific Banner safeguard works.")
