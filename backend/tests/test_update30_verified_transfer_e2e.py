"""End-to-end scheduling test with a verified transfer course."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update28_multisemester_program.json"
HISTORY_FILE = FIXTURES / "update30_verified_transfer_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("UPDATE 30.4 — VERIFIED TRANSFER END-TO-END TEST")
    print("=" * 70)

    program = json.loads(PROGRAM_FILE.read_text(encoding="utf-8"))

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

        assert schedule.get("status") == "unsatisfiable", (
            "Expected an unsatisfiable schedule because ARCH 107 "
            "has an unverified minimum-grade equivalency; got "
            f"{schedule.get('status')!r}"
        )

        assert schedule.get("candidate_courses") == [
            "ARCH 113",
            "ARCH 108",
            "ARCH 114",
        ], (
            "Verified ARCH 107 should be excluded from "
            "remaining degree requirements."
        )

        assert schedule.get("unavailable_courses") == [], (
            "All remaining courses should be offered "
            "within the planning window."
        )

        assert schedule.get("semesters") == [], (
            "An unsatisfiable schedule must not contain "
            "a generated semester plan."
        )

        assert schedule.get("total_planned_credits") == 0, (
            "An unsatisfiable schedule must not report "
            "planned credits."
        )

        print("PASS: Verified ARCH 107 excluded from requirements.")
        print("PASS: Remaining courses are catalog-available.")
        print("PASS: Unverified minimum-grade equivalency blocks scheduling.")
        print("PASS: Failure export contains no invalid semester plan.")
        print("ALL UPDATE 30.12 ASSERTIONS PASSED")

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
