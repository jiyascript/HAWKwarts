"""Regression test for mixed transfer and institutional records."""

from backend.transcript.transcript_validator import (
    build_academic_history,
)


def main():
    print("UPDATE 29.7 — MIXED COMPLETION REGRESSION TEST")
    print("=" * 65)

    courses = [
        {
            "code": "ARCH 107",
            "title": "Architecture Course 107",
            "credits": 3.0,
            "grade": "TR",
            "term": "Fall 2024",
            "level": "UG",
            "status": "transfer",
            "equivalency_verified": False,
        },
        {
            "code": "ARCH 107",
            "title": "Architecture Course 107",
            "credits": 3.0,
            "grade": "A",
            "term": "Spring 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    history = build_academic_history(courses)

    assert not history["validation_errors"], (
        f"Unexpected errors: {history['validation_errors']}"
    )

    assert history["scheduler_course_codes"] == ["ARCH 107"], (
        "Valid institutional completion must remain recognized."
    )

    assert len(history["completed_courses"]) == 1, (
        "Expected one completed institutional course."
    )

    assert len(history["transfer_courses"]) == 1, (
        "Unverified transfer record must be preserved."
    )

    assert (
        history["transfer_courses"][0]["equivalency_verified"]
        is False
    ), "Transfer verification status was unexpectedly changed."

    assert any(
        "multiple categories" in warning
        for warning in history["warnings"]
    ), "Expected duplicate-category warning."

    print("PASS: Institutional completion preserved.")
    print("PASS: Unverified transfer retained.")
    print("PASS: Transfer verification status unchanged.")
    print("PASS: Duplicate-category warning generated.")
    print("ALL UPDATE 29.7 ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
