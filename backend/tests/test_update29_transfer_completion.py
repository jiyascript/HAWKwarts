"""Verify only approved transfer equivalencies count as completed."""

from backend.transcript.transcript_validator import (
    build_academic_history,
)


def main():
    print("UPDATE 29.3 — TRANSFER COMPLETION REGRESSION TEST")
    print("=" * 65)

    courses = [
        {
            "code": "ARCH 107",
            "title": "Architecture Course 107",
            "credits": 3.0,
            "grade": "TR",
            "term": "Fall 2025",
            "level": "UG",
            "status": "transfer",
            "equivalency_verified": False,
        },
        {
            "code": "ARCH 113",
            "title": "Architecture Course 113",
            "credits": 6.0,
            "grade": "TR",
            "term": "Fall 2025",
            "level": "UG",
            "status": "transfer",
            "equivalency_verified": True,
        },
    ]

    history = build_academic_history(courses)

    assert not history["validation_errors"], (
        f"Unexpected validation errors: "
        f"{history['validation_errors']}"
    )

    actual = set(history["scheduler_course_codes"])
    expected = {"ARCH 113"}

    print("Verified transfer: ARCH 113")
    print("Unverified transfer: ARCH 107")
    print("Expected completed codes:", sorted(expected))
    print("Actual completed codes:", sorted(actual))

    assert actual == expected, (
        "BUG: Unverified transfer equivalency incorrectly "
        "counts as completed."
    )

    print("\nPASS: Only verified transfer equivalencies count.")
    print("ALL UPDATE 29.3 ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
