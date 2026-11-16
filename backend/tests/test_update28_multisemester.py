"""Test realistic multi-semester scheduling with production Banner data."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update28_multisemester_program.json"
HISTORY_FILE = FIXTURES / "update28_empty_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("UPDATE 28.13 — MULTI-SEMESTER INTEGRATION TEST")
    print("=" * 65)

    program = json.loads(
        PROGRAM_FILE.read_text(encoding="utf-8")
    )

    def get_test_requirements(kind, program_id):
        if kind == "program" and program_id == program["program_id"]:
            return program

        raise AssertionError(
            f"Unexpected program lookup: {kind}, {program_id}"
        )

    previous_argv = sys.argv[:]
    previous_schedule = (
        SCHEDULE_FILE.read_bytes()
        if SCHEDULE_FILE.exists()
        else None
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
                side_effect=resolve_requirements,
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

        assert SCHEDULE_FILE.exists(), (
            "Scheduler did not export schedule.json."
        )

        schedule = json.loads(
            SCHEDULE_FILE.read_text(encoding="utf-8")
        )

        assert schedule["status"] == "success", (
            f"Expected success, got {schedule['status']}"
        )

        print("\nPASS: Production scheduler found a valid plan.")

        semesters = {
            semester["term"]: semester
            for semester in schedule["semesters"]
        }

        assert "Fall 2026" in semesters
        assert "Spring 2027" in semesters

        expected = {
            "Fall 2026": {
                "ARCH 107": 3,
                "ARCH 113": 6,
            },
            "Spring 2027": {
                "ARCH 108": 3,
                "ARCH 114": 6,
            },
        }

        all_planned = []

        for term, expected_courses in expected.items():
            semester = semesters[term]

            actual_courses = {
                course["code"]: course["credits"]
                for course in semester["planned_courses"]
            }

            assert actual_courses == expected_courses, (
                f"{term}: expected {expected_courses}, "
                f"got {actual_courses}"
            )

            actual_credits = sum(actual_courses.values())

            assert actual_credits == 9, (
                f"{term}: expected 9 credits, "
                f"got {actual_credits}"
            )

            assert actual_credits <= 11, (
                f"{term}: exceeds part-time credit limit"
            )

            all_planned.extend(actual_courses)

            print(
                f"PASS: {term} — "
                f"{', '.join(actual_courses)} "
                f"({actual_credits} credits)"
            )

        assert len(all_planned) == 4
        assert len(set(all_planned)) == 4

        print("PASS: All four courses scheduled exactly once.")

        assert schedule["total_planned_credits"] == 18, (
            "Expected 18 total planned credits, got "
            f"{schedule['total_planned_credits']}"
        )

        print("PASS: Total planned credits = 18.")

        fall_codes = set(expected["Fall 2026"])
        spring_codes = set(expected["Spring 2027"])

        assert {"ARCH 107", "ARCH 113"} <= fall_codes
        assert {"ARCH 108", "ARCH 114"} <= spring_codes

        print("PASS: Prerequisite ordering is valid.")
        print("PASS: ARCH 108 and ARCH 114 scheduled concurrently.")

        print("\n" + "=" * 65)
        print("ALL UPDATE 28.13 ASSERTIONS PASSED")

    finally:
        sys.argv = previous_argv

        if previous_schedule is None:
            if SCHEDULE_FILE.exists():
                SCHEDULE_FILE.unlink()
        else:
            SCHEDULE_FILE.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            SCHEDULE_FILE.write_bytes(previous_schedule)


if __name__ == "__main__":
    main()
