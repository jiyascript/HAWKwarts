
from backend.scheduler.prerequisite_validator import (
    evaluate_prerequisite_expression_for_term
)

# Test a course-range prerequisite with missing metadata.
expression = {
    "type": "course_range",
    "subject": "HUM",
    "start": 200,
    "end": 299
}

history = {
    "completed_courses": [],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = evaluate_prerequisite_expression_for_term(
    expression=expression,
    history=history,
    target_term=1,
    planned_terms={},
    detail_lookup={}
)

print("Expected status: unverified")
print("Actual status:", result["status"])
print("Full result:", result)

assert result["status"] == "unverified", (
    "Missing prerequisite metadata must return unverified."
)

print("\nPASS: Missing metadata handled safely.")


# Test 2: Metadata exists, but no matching course was found.
valid_metadata = {
    "HUM 200 to 299": {
        "minimum_grade": None,
        "concurrent_allowed": False
    }
}

result = evaluate_prerequisite_expression_for_term(
    expression=expression,
    history=history,
    target_term=1,
    planned_terms={},
    detail_lookup=valid_metadata
)

print("\nTest 2: Valid metadata, no matching course")
print("Expected status: not_satisfied")
print("Actual status:", result["status"])

assert result["status"] == "not_satisfied", (
    "A missing course with valid metadata must return not_satisfied."
)

print("PASS: Course eligibility correctly evaluated.")


# Test 3: Incomplete metadata with a matching completed course.
incomplete_metadata = {
    "HUM 200 to 299": {
        "minimum_grade": "C"
        # concurrent_allowed is missing
    }
}

history_with_course = {
    "completed_courses": [
        {
            "code": "HUM 205",
            "grade": "A",
            "credits": 3
        }
    ],
    "transfer_courses": [],
    "in_progress_courses": []
}

result = evaluate_prerequisite_expression_for_term(
    expression=expression,
    history=history_with_course,
    target_term=1,
    planned_terms={},
    detail_lookup=incomplete_metadata
)

print("\nTest 3: Incomplete course-range metadata")
print("Expected status: unverified")
print("Actual status:", result["status"])

assert result["status"] == "unverified", (
    "Incomplete metadata must return unverified."
)

print("PASS: Incomplete metadata handled safely.")


# Test 4: Invalid metadata type.
invalid_metadata = {
    "HUM 200 to 299": {
        "minimum_grade": "C",
        "concurrent_allowed": "False"
    }
}

result = evaluate_prerequisite_expression_for_term(
    expression=expression,
    history=history_with_course,
    target_term=1,
    planned_terms={},
    detail_lookup=invalid_metadata
)

print("\nTest 4: Invalid metadata type")
print("Expected status: unverified")
print("Actual status:", result["status"])

assert result["status"] == "unverified", (
    "Invalid metadata types must return unverified."
)

print("PASS: Invalid metadata handled safely.")

