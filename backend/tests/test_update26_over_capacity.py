"""Verify that the production scheduler rejects an unavoidable 12-credit semester."""

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
HISTORY_FILE = FIXTURES / "update26_over_capacity_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("Running Update 26 over-capacity integration regression.")
    print("=" * 65)

    program = json.loads(
        PROGRAM_FILE.read_text(encoding="utf-8")
    )
    history = json.loads(
        HISTORY_FILE.read_text(encoding="utf-8")
    )

    existing_fall_credits = sum(
        course["credits"]
        for course in history["in_progress_courses"]
        if course["term"] == "Fall 2026"
    )

    assert existing_fall_credits == 9.0
    assert history["all_institution_records"] == []

    adapter = CatalogAdapter()

    # ARCH 107 must be scheduled in Fall 2026.
    assert adapter.is_offered("ARCH 107", "Fall 2026")
    assert not adapter.is_offered("ARCH 107", "Spring 2027")
    assert adapter.credit_options("ARCH 107", "Fall 2026") == [3.0]

    # ARCH 108 must follow in Spring 2027.
    assert not adapter.is_offered("ARCH 108", "Fall 2026")
    assert adapter.is_offered("ARCH 108", "Spring 2027")

    print("PASS: Existing Fall 2026 credits = 9.")
    print("PASS: ARCH 107 requires 3 additional Fall credits.")
    print("PASS: No alternative semester is available for ARCH 107.")

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

        assert schedule["status"] == "unsatisfiable", (
            "Expected UNSAT for 9 existing + 3 mandatory "
            f"Fall credits, got {schedule['status']!r}"
        )

        print("PASS: Production solver rejected the 12-credit semester.")
        print("PASS: Failure JSON reports unsatisfiable.")
        print("PASS: Undergraduate part-time credit maximum enforced.")

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
