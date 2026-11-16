
"""Verify exclusivity is responsible for the negative scenario's UNSAT result."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.tests.test_update23_exclusivity_unsat import (
    ROOT,
    HISTORY_FILE,
    negative_program,
    test_get_requirements,
    test_resolve_requirements,
)

SCHEDULER_FILE = (
    ROOT / "backend" / "scheduler" / "scheduler_poc.py"
)

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    source = SCHEDULER_FILE.read_text(encoding="utf-8")

    original = """expression=z3.Implies(
                    pathway_selection_vars[
                        (pathway_index, option_index)
                    ],
                    z3.Not(assignment)
                )"""

    replacement = """expression=z3.BoolVal(True)"""

    assert source.count(original) == 1, (
        "Expected exactly one exclusivity constraint block."
    )

    modified_source = source.replace(
        original,
        replacement,
        1,
    )

    previous_schedule = (
        SCHEDULE_FILE.read_bytes()
        if SCHEDULE_FILE.exists()
        else None
    )

    previous_argv = sys.argv[:]

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
            negative_program["program_id"],
        ]

        print("Running Update 23 exclusivity-disabled comparison.")
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
            namespace = {
                "__name__": "__main__",
                "__file__": str(SCHEDULER_FILE),
                "__package__": "backend.scheduler",
            }

            try:
                exec(
                    compile(
                        modified_source,
                        str(SCHEDULER_FILE),
                        "exec",
                    ),
                    namespace,
                )
            except SystemExit as exc:
                assert exc.code in (0, None), (
                    f"Unexpected scheduler exit: {exc.code}"
                )

        assert SCHEDULE_FILE.exists(), (
            "Scheduler did not export a comparison result."
        )

        result = json.loads(
            SCHEDULE_FILE.read_text(encoding="utf-8")
        )

        assert result["status"] == "success", (
            "Expected SAT with exclusivity disabled, "
            f"got {result['status']}"
        )

        planned = [
            course["code"]
            for semester in result["semesters"]
            for course in semester["planned_courses"]
        ]

        assert "CS 115" in planned
        assert "CS 116" in planned

        print("PASS: Removing exclusivity makes the scenario SAT.")
        print("PASS: CS 115 and CS 116 remain scheduled.")
        print(
            "PASS: Exclusivity is the decisive constraint "
            "in the negative regression."
        )

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