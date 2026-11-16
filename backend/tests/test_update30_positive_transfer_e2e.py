"""End-to-end scheduling test for a verified transfer without downstream grade restrictions."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update28_multisemester_program.json"
HISTORY_FILE = FIXTURES / "update30_positive_transfer_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("UPDATE 30.14 — POSITIVE VERIFIED TRANSFER END-TO-END TEST")
    print("=" * 70)

    program = json.loads(PROGRAM_FILE.read_text(encoding="utf-8"))
    history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))

    assert history["scheduler_course_codes"] == ["ARCH 114"]
    assert history["transfer_courses"][0]["equivalency_verified"] is True

    def get_test_requirements(kind, program_id):
        assert program_id == program["program_id"], (
            f"Unexpected program ID: {program_id}"
        )
        return program

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

        print("Exported schedule status:", schedule.get("status"))

        assert schedule.get("status") == "success", (
            f"Expected success, got {schedule.get('status')!r}"
        )

        semesters = {
            semester["term"]: semester
            for semester in schedule["semesters"]
        }

        expected = {
            "Fall 2026": {
                "ARCH 107": 3,
                "ARCH 113": 6,
            },
            "Spring 2027": {
                "ARCH 108": 3,
            },
        }

        all_planned = []

        for term, expected_courses in expected.items():
            assert term in semesters, (
                f"Missing semester: {term}"
            )

            semester = semesters[term]

            actual_courses = {
                course["code"]: course["credits"]
                for course in semester["planned_courses"]
            }

            print(f"{term}: {actual_courses}")

            assert actual_courses == expected_courses, (
                f"{term}: expected {expected_courses}, "
                f"got {actual_courses}"
            )

            assert sum(actual_courses.values()) <= 11, (
                f"{term}: exceeds part-time credit limit."
            )

            all_planned.extend(actual_courses)

        assert "ARCH 114" not in all_planned, (
            "Verified transfer ARCH 114 was scheduled again."
        )

        assert len(all_planned) == 3
        assert len(set(all_planned)) == 3

        assert schedule["total_planned_credits"] == 12, (
            "Expected 12 newly planned credits, got "
            f"{schedule['total_planned_credits']}"
        )

        print("PASS: Verified ARCH 114 transfer excluded.")
        print("PASS: Three remaining courses scheduled once.")
        print("PASS: Semester assignments match expectations.")
        print("PASS: Part-time credit limits respected.")
        print("PASS: Total planned credits equal 12.")
        print("ALL UPDATE 30.14 ASSERTIONS PASSED")

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
