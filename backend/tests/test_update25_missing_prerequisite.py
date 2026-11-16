
"""Verify the production scheduler rejects a missing Banner prerequisite."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update25_missing_prerequisite_program.json"
HISTORY_FILE = FIXTURES / "update25_prerequisite_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("Running Update 25 missing prerequisite regression.")
    print("=" * 55)

    with PROGRAM_FILE.open("r", encoding="utf-8") as file:
        program = json.load(file)

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

        assert SCHEDULE_FILE.exists(), (
            "Scheduler did not export schedule.json."
        )

        schedule = json.loads(
            SCHEDULE_FILE.read_text(encoding="utf-8")
        )

        assert schedule["status"] == "unsatisfiable", (
            "Expected an unsatisfiable schedule because ARCH 107 "
            f"is missing, but received: {schedule['status']}"
        )

        print("PASS: Missing prerequisite produces unsatisfiable schedule.")

        # A rejected plan must not be presented as a valid schedule.
        assert schedule["status"] != "success"

        print("PASS: Invalid prerequisite plan was not accepted.")
        print("\nPASS: Update 25 negative integration regression completed.")

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
