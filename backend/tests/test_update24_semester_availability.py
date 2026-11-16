
"""Verify mandatory courses respect semester-specific availability."""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

from backend.scheduler.catalog_adapter import CatalogAdapter
from backend.scheduler.requirement_resolver import resolve_requirements


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "backend" / "tests" / "fixtures"

PROGRAM_FILE = FIXTURES / "update24_semester_availability_program.json"
HISTORY_FILE = FIXTURES / "update23_overlap_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("Running Update 24 semester availability regression.")
    print("===================================================")

    with PROGRAM_FILE.open("r", encoding="utf-8") as file:
        program = json.load(file)

    adapter = CatalogAdapter()

    # Verify the catalog assumptions used by this regression.
    assert adapter.is_offered("BIOL 100", "Fall 2026")
    assert not adapter.is_offered("BIOL 100", "Spring 2027")

    assert not adapter.is_offered("BIOL 115", "Fall 2026")
    assert adapter.is_offered("BIOL 115", "Spring 2027")

    print("PASS: Semester-specific catalog offerings verified.")

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

        assert schedule["status"] == "success", (
            f"Expected success, got: {schedule['status']}"
        )

        semesters = {
            semester["term"]: semester
            for semester in schedule["semesters"]
        }

        assert set(semesters) == {
            "Fall 2026",
            "Spring 2027",
        }

        fall_courses = {
            course["code"]
            for course in semesters["Fall 2026"]["planned_courses"]
        }

        spring_courses = {
            course["code"]
            for course in semesters["Spring 2027"]["planned_courses"]
        }

        assert fall_courses == {"BIOL 100"}, (
            f"Unexpected Fall courses: {fall_courses}"
        )

        assert spring_courses == {"BIOL 115"}, (
            f"Unexpected Spring courses: {spring_courses}"
        )

        print("PASS: BIOL 100 scheduled only in Fall 2026.")
        print("PASS: BIOL 115 scheduled only in Spring 2027.")

        all_codes = []

        for term, semester in semesters.items():
            for course in semester["planned_courses"]:
                code = course["code"]

                assert adapter.is_offered(code, term), (
                    f"{code} was scheduled in unavailable term {term}"
                )

                all_codes.append(code)

            assert semester["enrollment_warnings"] == [], (
                f"Enrollment warning in {term}"
            )

        assert len(all_codes) == len(set(all_codes)), (
            "Duplicate courses detected."
        )

        assert set(all_codes) == {"BIOL 100", "BIOL 115"}

        total_credits = sum(
            semester["planned_credits"]
            for semester in semesters.values()
        )

        assert schedule["total_planned_credits"] == total_credits

        print("PASS: Every course respects semester availability.")
        print("PASS: No duplicate courses or enrollment warnings.")
        print("PASS: Total planned credits are consistent.")

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