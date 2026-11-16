"""Verify elective/pathway semester credit capacity in production."""

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
HISTORY_FILE = FIXTURES / "update26_elective_capacity_history.json"

SCHEDULE_FILE = (
    ROOT / "backend" / "scheduler" / "results" / "schedule.json"
)


def main():
    print("Running Update 26 elective/pathway capacity regression.")
    print("=" * 65)

    program = json.loads(
        PROGRAM_FILE.read_text(encoding="utf-8")
    )
    history = json.loads(
        HISTORY_FILE.read_text(encoding="utf-8")
    )

    spring_existing = sum(
        course["credits"]
        for course in history["in_progress_courses"]
        if course["term"] == "Spring 2027"
    )

    assert spring_existing == 6.0

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
            pathway_file=PATHWAY_FILE,
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

        semesters = {
            semester["term"]: semester
            for semester in schedule["semesters"]
        }

        assert set(semesters) == {
            "Fall 2026",
            "Spring 2027",
        }

        all_planned_codes = []

        for term, semester in semesters.items():
            planned_courses = semester["planned_courses"]

            planned_codes = [
                course["code"]
                for course in planned_courses
            ]

            assert len(planned_codes) == len(set(planned_codes)), (
                f"Duplicate planned courses in {term}"
            )

            planned_sum = sum(
                course["credits"]
                for course in planned_courses
            )

            assert semester["planned_credits"] == planned_sum, (
                f"Incorrect planned credits in {term}"
            )

            assert semester["total_credits"] == (
                semester["existing_credits"] + planned_sum
            ), f"Incorrect total credits in {term}"

            assert semester["total_credits"] <= 11, (
                f"{term} exceeds 11-credit limit"
            )

            assert semester["enrollment_warnings"] == [], (
                f"Unexpected enrollment warnings in {term}"
            )

            all_planned_codes.extend(planned_codes)

        assert len(all_planned_codes) == len(set(all_planned_codes)), (
            "A course appears in multiple semesters."
        )

        fall = semesters["Fall 2026"]
        spring = semesters["Spring 2027"]

        assert fall["existing_credits"] == 0
        assert spring["existing_credits"] == 6.0

        assert "CS 201" not in all_planned_codes, (
            "Unexpected CS 201 selection."
        )

        assert set(all_planned_codes) == {
            "CS 115",
            "CS 116",
            "CS 350",
        }, (
            f"Unexpected course selection: {all_planned_codes}"
        )

        assert fall["planned_credits"] == 2
        assert fall["total_credits"] == 2

        assert spring["planned_credits"] == 5
        assert spring["total_credits"] == 11

        assert schedule["total_planned_credits"] == 7
        assert schedule["credit_summary"]["total_credits"] == 13

        print("PASS: Production scheduler found a valid plan.")
        print("PASS: Mandatory/pathway/elective course selection verified.")
        print("PASS: No duplicate planned courses.")
        print("PASS: Spring existing credits = 6.")
        print("PASS: Spring planned credits = 5.")
        print("PASS: Spring total credits = 11 / 11.")
        print("PASS: Elective/pathway credits respect semester capacity.")

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
