"""Verify the production scheduler rejects an impossible course plan."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update28_impossible_program.json"
HISTORY_FILE = FIXTURES / "update28_empty_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("UPDATE 28.19 — IMPOSSIBLE SCHEDULE INTEGRATION TEST")
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

        scheduler_exit = None

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
                scheduler_exit = exc.code

        print("\nScheduler exit code:", scheduler_exit)

        if SCHEDULE_FILE.exists():
            schedule = json.loads(
                SCHEDULE_FILE.read_text(encoding="utf-8")
            )

            print(
                "Exported schedule status:",
                schedule.get("status"),
            )

            assert schedule.get("status") == "unsatisfiable", (
                "Expected unsatisfiable schedule status, got "
                f"{schedule.get('status')!r}"
            )

            print(
                "PASS: No successful schedule was exported."
            )

        else:
            print(
                "PASS: Scheduler did not export a successful schedule."
            )

        print("\n" + "=" * 65)
        print("UPDATE 28.19 NEGATIVE SCENARIO PASSED")

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
