
"""Verify production scheduling rejects pathway/elective double-counting."""

import copy
import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.requirement_resolver import resolve_requirements

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update23_overlap_program.json"
PATHWAY_FILE = FIXTURES / "update23_overlap_pathways.json"
HISTORY_FILE = FIXTURES / "update23_overlap_history.json"

with PROGRAM_FILE.open("r", encoding="utf-8") as file:
    program = json.load(file)

negative_program = copy.deepcopy(program)

negative_program["requirements"][0]["items"][0]["options"] = [
    "CS 115"
]


def test_get_requirements(kind, program_id):
    if kind == "program" and program_id == negative_program["program_id"]:
        return negative_program

    raise AssertionError(
        f"Unexpected program lookup: {kind}, {program_id}"
    )


def test_resolve_requirements(selected_program, history):
    return resolve_requirements(
        selected_program,
        history,
        pathway_file=PATHWAY_FILE,
    )


def main():
    schedule_path = (
        ROOT / "backend" / "scheduler" / "results" / "schedule.json"
    )

    # Preserve the successful integration result.
    previous_schedule = (
        schedule_path.read_bytes()
        if schedule_path.exists()
        else None
    )

    try:
        if schedule_path.exists():
            schedule_path.unlink()

        sys.argv = [
            "backend.scheduler.scheduler_poc",
            "--history",
            str(HISTORY_FILE),
            "--academic-level",
            "undergraduate",
            "--enrollment-status",
            "part_time",
            "--program-id",
            negative_program["program_id"],
        ]

        print("Running Update 23 negative exclusivity regression.")
        print("===================================================")

        with (
            patch(
                "courses_rag.requirements_lookup.get_requirements",
                side_effect=test_get_requirements,
            ),
            patch(
                "backend.scheduler.requirement_resolver.resolve_requirements",
                side_effect=test_resolve_requirements,
            ),
        ):
            try:
                runpy.run_module(
                    "backend.scheduler.scheduler_poc",
                    run_name="__main__",
                )
            except SystemExit as exc:
                assert exc.code in (0, None), (
                    f"Scheduler exited unexpectedly: {exc.code}"
                )

        assert schedule_path.exists(), (
            "Scheduler did not export a result."
        )

        result = json.loads(
            schedule_path.read_text(encoding="utf-8")
        )

        assert result["status"] != "success", (
            "Double-counting scenario incorrectly produced "
            "a successful schedule."
        )

        print(
            "PASS: Production scheduler rejected the "
            "overlapping pathway/elective scenario."
        )

    finally:
        if previous_schedule is not None:
            schedule_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            schedule_path.write_bytes(previous_schedule)
        elif schedule_path.exists():
            schedule_path.unlink()


# These are mock callbacks, not pytest test cases.
test_get_requirements.__test__ = False
test_resolve_requirements.__test__ = False


if __name__ == "__main__":
    main()
