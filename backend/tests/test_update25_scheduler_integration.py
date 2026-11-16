
"""Verify real Banner prerequisite ordering in the production scheduler."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.catalog_adapter import CatalogAdapter
from backend.scheduler.requirement_resolver import resolve_requirements
from backend.scheduler.prerequisite_parser import (
    parse_prerequisites,
    extract_prerequisite_details,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update25_prerequisite_program.json"
HISTORY_FILE = FIXTURES / "update25_prerequisite_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("Running Update 25 Banner prerequisite integration regression.")
    print("=" * 65)

    with PROGRAM_FILE.open("r", encoding="utf-8") as file:
        program = json.load(file)

    adapter = CatalogAdapter()

    # ---------------------------------------------------------
    # Verify real Banner catalog assumptions.
    # ---------------------------------------------------------

    assert adapter.is_offered("ARCH 107", "Fall 2026")
    assert not adapter.is_offered("ARCH 107", "Spring 2027")

    assert not adapter.is_offered("ARCH 108", "Fall 2026")
    assert adapter.is_offered("ARCH 108", "Spring 2027")

    assert adapter.credit_options("ARCH 107", "Fall 2026") == [3.0]
    assert adapter.credit_options("ARCH 108", "Spring 2027") == [3.0]

    print("PASS: Banner semester availability and credits verified.")

    # ---------------------------------------------------------
    # Verify the actual ARCH 108 prerequisite.
    # ---------------------------------------------------------

    info = adapter.course_info("ARCH 108", "Spring 2027")
    requirements = info.get("requirements") or {}

    indicator = (requirements.get("prerequisites") or "").strip()
    general = (requirements.get("general_requirements") or "").strip()

    parsed = parse_prerequisites(indicator, general)
    details = extract_prerequisite_details(general)

    assert parsed["status"] == "parsed"
    assert parsed["courses"] == ["ARCH 107"]
    assert parsed["logic"] == "SINGLE"

    assert any(
        detail["code"] == "ARCH 107"
        and detail["minimum_grade"] == "D"
        and detail["concurrent_allowed"] is False
        for detail in details
    ), "ARCH 108 prerequisite metadata does not match Banner."

    print("PASS: Real ARCH 108 prerequisite metadata verified.")

    # ---------------------------------------------------------
    # Run production scheduler using isolated test requirements.
    # ---------------------------------------------------------

    previous_argv = sys.argv[:]
    previous_schedule = (
        SCHEDULE_FILE.read_bytes()
        if SCHEDULE_FILE.exists()
        else None
    )

    def get_test_requirements(kind, program_id):
        if kind == "program" and program_id == program["program_id"]:
            return program

        raise AssertionError(
            f"Unexpected program lookup: {kind}, {program_id}"
        )

    def resolve_test_requirements(selected_program, history):
        return resolve_requirements(
            selected_program,
            history,
        )

    try:
        if SCHEDULE_FILE.exists():
            SCHEDULE_FILE.unlink()

        sys.argv = [
            "backend.scheduler.scheduler_poc",
            "--history",
            str(HISTORY_FILE),
            "--academic-level",
            "undergraduate",
            "--enrollment-status",
            "part_time",
            "--program-id",
            program["program_id"],
        ]

        with (
            patch(
                "courses_rag.requirements_lookup.get_requirements",
                side_effect=get_test_requirements,
            ),
            patch(
                "backend.scheduler.requirement_resolver.resolve_requirements",
                side_effect=resolve_test_requirements,
            ),
        ):
            try:
                runpy.run_module(
                    "backend.scheduler.scheduler_poc",
                    run_name="__main__",
                )
            except SystemExit as exc:
                assert exc.code in (0, None), (
                    f"Unexpected scheduler exit: {exc.code}"
                )

        # -----------------------------------------------------
        # Verify exported schedule.
        # -----------------------------------------------------

        assert SCHEDULE_FILE.exists(), (
            "Scheduler did not export schedule.json."
        )

        schedule = json.loads(
            SCHEDULE_FILE.read_text(encoding="utf-8")
        )

        assert schedule["status"] == "success", (
            f"Expected success, got: {schedule['status']}"
        )

        semesters = {
            semester["term"]: semester
            for semester in schedule["semesters"]
        }

        assert set(semesters) == {
            "Fall 2026",
            "Spring 2027",
        }

        expected_courses = {
            "Fall 2026": {"ARCH 107": 3.0},
            "Spring 2027": {"ARCH 108": 3.0},
        }

        all_codes = []

        for term, expected in expected_courses.items():
            semester = semesters[term]

            actual = {
                course["code"]: course["credits"]
                for course in semester["planned_courses"]
            }

            assert actual == expected, (
                f"{term}: expected {expected}, got {actual}"
            )

            assert len(semester["planned_courses"]) == len(actual), (
                f"Duplicate courses in {term}"
            )

            assert semester["planned_credits"] == 3.0
            assert semester["total_credits"] == 3.0
            assert semester["enrollment_warnings"] == []

            for code in actual:
                assert adapter.is_offered(code, term), (
                    f"{code} is not offered in {term}"
                )

            all_codes.extend(actual)

        print("PASS: ARCH 107 scheduled in Fall 2026.")
        print("PASS: ARCH 108 scheduled in Spring 2027.")

        assert len(all_codes) == len(set(all_codes)), (
            "Duplicate courses detected."
        )

        assert set(all_codes) == {"ARCH 107", "ARCH 108"}

        assert schedule["total_planned_credits"] == 6.0
        assert schedule["credit_summary"]["total_credits"] == 6.0
        assert schedule["credit_summary"]["undergraduate_credits"] == 6.0

        print("PASS: Real prerequisite sequence respected.")
        print("PASS: Total planned credits equal 6.")
        print("PASS: No duplicate courses or enrollment warnings.")
        print("\nPASS: Update 25 Banner integration regression completed.")

    finally:
        sys.argv = previous_argv

        if previous_schedule is not None:
            SCHEDULE_FILE.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            SCHEDULE_FILE.write_bytes(previous_schedule)
        elif SCHEDULE_FILE.exists():
            SCHEDULE_FILE.unlink()


if __name__ == "__main__":
    main()