"""Verify the production scheduler accepts exactly 11 semester credits."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.catalog_adapter import CatalogAdapter
from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update25_prerequisite_program.json"
HISTORY_FILE = FIXTURES / "update26_exact_capacity_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("Running Update 26 exact-capacity integration regression.")
    print("=" * 65)

    with PROGRAM_FILE.open("r", encoding="utf-8") as file:
        program = json.load(file)

    with HISTORY_FILE.open("r", encoding="utf-8") as file:
        history = json.load(file)

    existing_fall_credits = sum(
        course["credits"]
        for course in history["in_progress_courses"]
        if course["term"] == "Fall 2026"
    )

    assert existing_fall_credits == 8.0

    adapter = CatalogAdapter()

    assert adapter.is_offered("ARCH 107", "Fall 2026")
    assert adapter.is_offered("ARCH 108", "Spring 2027")

    assert adapter.credit_options("ARCH 107", "Fall 2026") == [3.0]
    assert adapter.credit_options("ARCH 108", "Spring 2027") == [3.0]

    print("PASS: Banner availability and credit values verified.")
    print("PASS: Existing Fall 2026 credits = 8.")

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

    def resolve_test_requirements(selected_program, academic_history):
        return resolve_requirements(
            selected_program,
            academic_history,
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

        assert SCHEDULE_FILE.exists(), (
            "Scheduler did not export schedule.json."
        )

        schedule = json.loads(
            SCHEDULE_FILE.read_text(encoding="utf-8")
        )

        assert schedule["status"] == "success", (
            f"Expected success, got {schedule['status']}"
        )

        assert schedule["enrollment_status"] == "part_time"
        assert schedule["academic_level"] == "undergraduate"

        semesters = {
            semester["term"]: semester
            for semester in schedule["semesters"]
        }

        assert set(semesters) == {
            "Fall 2026",
            "Spring 2027",
        }

        fall = semesters["Fall 2026"]
        spring = semesters["Spring 2027"]

        fall_planned = {
            course["code"]: course["credits"]
            for course in fall["planned_courses"]
        }

        spring_planned = {
            course["code"]: course["credits"]
            for course in spring["planned_courses"]
        }

        assert fall_planned == {"ARCH 107": 3.0}, fall_planned
        assert spring_planned == {"ARCH 108": 3.0}, spring_planned

        assert fall["existing_credits"] == 8.0
        assert fall["planned_credits"] == 3.0
        assert fall["total_credits"] == 11.0

        assert spring["existing_credits"] == 0.0
        assert spring["planned_credits"] == 3.0
        assert spring["total_credits"] == 3.0

        assert fall["total_credits"] <= 11
        assert spring["total_credits"] <= 11

        assert fall["enrollment_warnings"] == []
        assert spring["enrollment_warnings"] == []

        print("PASS: ARCH 107 scheduled in Fall 2026.")
        print("PASS: ARCH 108 scheduled in Spring 2027.")
        print("PASS: Fall 2026 existing credits = 8.")
        print("PASS: Fall 2026 planned credits = 3.")
        print("PASS: Fall 2026 total credits = 11 / 11.")
        print("PASS: Spring 2027 total credits = 3 / 11.")
        print("PASS: Exact-capacity schedule accepted.")

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
