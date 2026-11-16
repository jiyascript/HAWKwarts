
"""Regression: unavailable pathways produce structured failure JSON."""

import copy
import json
import runpy
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from backend.tests.test_update23_scheduler_integration import (
    ROOT,
    HISTORY_FILE,
    program,
)
from backend.scheduler.requirement_resolver import resolve_requirements
from backend.scheduler.catalog_adapter import CatalogAdapter


def main():
    test_program = copy.deepcopy(program)

    adapter = CatalogAdapter()

    for code in ("CS 998", "CS 999"):
        assert not adapter.is_offered(code, "Fall 2026")
        assert not adapter.is_offered(code, "Spring 2027")

    schedule_path = (
        ROOT / "backend" / "scheduler" / "results" / "schedule.json"
    )

    previous_schedule = (
        schedule_path.read_bytes()
        if schedule_path.exists()
        else None
    )

    previous_argv = sys.argv[:]

    pathway_data = {
        test_program["program_id"]: {
            "requirements": [
                {
                    "type": "pathway",
                    "name": "Programming Sequence",
                    "replaces": ["CS 115", "CS 116"],
                    "options": [
                        ["CS 998"],
                        ["CS 999"],
                    ],
                }
            ]
        }
    }

    def get_test_requirements(kind, program_id):
        if kind == "program" and program_id == test_program["program_id"]:
            return test_program

        raise AssertionError(
            f"Unexpected program lookup: {kind}, {program_id}"
        )

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pathway_file = Path(temporary_directory) / "pathways.json"
            pathway_file.write_text(
                json.dumps(pathway_data),
                encoding="utf-8",
            )

            def resolve_test_requirements(selected_program, history):
                return resolve_requirements(
                    selected_program,
                    history,
                    pathway_file=pathway_file,
                )

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
                test_program["program_id"],
            ]

            print("Running Update 24 insufficient pathway regression.")
            print("==================================================")

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

            assert schedule_path.exists(), (
                "Failure JSON was not exported."
            )

            result = json.loads(
                schedule_path.read_text(encoding="utf-8")
            )

            assert result["status"] == (
                "insufficient_pathway_availability"
            ), result

            assert result["message"] == (
                "No schedulable alternatives for "
                "pathway: Programming Sequence"
            )

            assert result["candidate_courses"] == [
                "CS 998",
                "CS 999",
            ]

            assert result["unavailable_courses"] == [
                "CS 998",
                "CS 999",
            ]

            assert result["semesters"] == []
            assert result["total_planned_credits"] == 0

            print("PASS: Insufficient pathway availability detected.")
            print("PASS: Structured pathway failure JSON exported.")
            print("PASS: Both unavailable pathway courses identified.")
            print("PASS: No invalid semester plan generated.")

    finally:
        sys.argv = previous_argv

        if previous_schedule is not None:
            schedule_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            schedule_path.write_bytes(previous_schedule)
        elif schedule_path.exists():
            schedule_path.unlink()


if __name__ == "__main__":
    main()