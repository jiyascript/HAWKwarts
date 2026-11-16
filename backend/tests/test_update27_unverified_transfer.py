"""Regression tests for unverified transfer prerequisites."""

import json
from pathlib import Path

from backend.transcript.transcript_validator import (
    validate_academic_history,
)
from backend.scheduler.prerequisite_validator import (
    check_course_prerequisite,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "update27_transfer_history.json"
)


def main():
    history = json.loads(
        FIXTURE.read_text(encoding="utf-8")
    )

    assert len(history["transfer_courses"]) == 1

    # Simulate transfer credit without approved equivalency.
    history["transfer_courses"][0][
        "equivalency_verified"
    ] = False

    normalized = validate_academic_history(history)

    assert normalized["validation_errors"] == []

    result = check_course_prerequisite(
        prerequisite_code="ARCH 107",
        minimum_grade=None,
        history=normalized,
    )

    assert result["status"] == "unverified", result

    print(
        "PASS: Unverified transfer does not satisfy "
        "a prerequisite without a grade minimum."
    )

    result = check_course_prerequisite(
        prerequisite_code="ARCH 107",
        minimum_grade="D",
        history=normalized,
    )

    assert result["status"] == "unverified", result

    print(
        "PASS: Unverified transfer does not satisfy "
        "a minimum-grade prerequisite."
    )

    # Verified course equivalency alone does not establish
    # minimum-grade eligibility.
    history["transfer_courses"][0][
        "equivalency_verified"
    ] = True

    normalized = validate_academic_history(history)

    result = check_course_prerequisite(
        prerequisite_code="ARCH 107",
        minimum_grade="D",
        history=normalized,
    )

    assert result["status"] == "unverified", result
    assert (
        result["reason"]
        == "Transfer grade equivalency requires verification"
    )

    print(
        "PASS: Verified transfer equivalency alone "
        "does not establish minimum-grade eligibility."
    )


if __name__ == "__main__":
    main()
