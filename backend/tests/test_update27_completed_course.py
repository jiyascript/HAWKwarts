"""Verify completed courses are excluded by the production scheduler."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update25_prerequisite_program.json"
HISTORY_FILE = FIXTURES / "update27_completed_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("Running Update 27 completed-course integration test.")
    print("=" * 60)

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

        semesters = {
            semester["term"]: semester
            for semester in schedule["semesters"]
        }

        all_planned = [
            course["code"]
            for semester in semesters.values()
            for course in semester["planned_courses"]
        ]

        assert "ARCH 107" not in all_planned, (
            "Completed ARCH 107 was scheduled again."
        )

        assert all_planned.count("ARCH 108") == 1, (
            f"ARCH 108 should appear exactly once: {all_planned}"
        )

        spring = semesters["Spring 2027"]

        spring_courses = {
            course["code"]: course["credits"]
            for course in spring["planned_courses"]
        }

        assert spring_courses == {"ARCH 108": 3}, (
            f"Unexpected Spring schedule: {spring_courses}"
        )

        assert schedule["total_planned_credits"] == 3

        print("PASS: Production scheduler found a valid plan.")
        print("PASS: Completed ARCH 107 was not scheduled again.")
        print("PASS: ARCH 108 scheduled exactly once.")
        print("PASS: ARCH 108 scheduled in Spring 2027.")
        print("PASS: Total newly scheduled credits = 3.")

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
