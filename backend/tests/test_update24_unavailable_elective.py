
"""Test that an unavailable optional elective does not crash scheduling."""

import copy
import json
import runpy
import sys
from unittest.mock import patch

from backend.tests.test_update23_scheduler_integration import (
    ROOT,
    HISTORY_FILE,
    PATHWAY_FILE,
    program,
)
from backend.scheduler.requirement_resolver import resolve_requirements
from backend.scheduler.catalog_adapter import CatalogAdapter


def main():
    test_program = copy.deepcopy(program)

    elective = test_program["requirements"][0]["items"][0]
    elective["options"] = ["CS 350", "CS 999"]

    adapter = CatalogAdapter()

    assert not adapter.is_offered("CS 999", "Fall 2026")
    assert not adapter.is_offered("CS 999", "Spring 2027")
    assert adapter.is_offered("CS 350", "Spring 2027")

    schedule_path = (
        ROOT / "backend" / "scheduler" / "results" / "schedule.json"
    )

    previous_schedule = (
        schedule_path.read_bytes()
        if schedule_path.exists()
        else None
    )

    previous_argv = sys.argv[:]

    def get_test_requirements(kind, program_id):
        if kind == "program" and program_id == test_program["program_id"]:
            return test_program
        raise AssertionError(f"Unexpected lookup: {kind}, {program_id}")

    def resolve_test_requirements(selected_program, history):
        return resolve_requirements(
            selected_program,
            history,
            pathway_file=PATHWAY_FILE,
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
            test_program["program_id"],
        ]

        print("Running Update 24 unavailable elective regression.")
        print("===================================================")

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

        assert schedule_path.exists(), "No schedule JSON exported."

        result = json.loads(
            schedule_path.read_text(encoding="utf-8")
        )

        assert result["status"] == "success", (
            f"Expected SAT, got {result['status']}"
        )

        planned = [
            course["code"]
            for semester in result["semesters"]
            for course in semester["planned_courses"]
        ]

        assert "CS 350" in planned
        assert "CS 999" not in planned
        assert result["total_planned_credits"] == 7

        print("PASS: Unavailable elective CS 999 was not scheduled.")
        print("PASS: Available elective CS 350 was scheduled.")
        print("PASS: Scheduler returned SAT with 7 planned credits.")

    finally:
        sys.argv = previous_argv

        if previous_schedule is not None:
            schedule_path.parent.mkdir(parents=True, exist_ok=True)
            schedule_path.write_bytes(previous_schedule)
        elif schedule_path.exists():
            schedule_path.unlink()


if __name__ == "__main__":
    main()
