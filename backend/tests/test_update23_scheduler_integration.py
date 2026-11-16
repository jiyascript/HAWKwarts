"""Run the production scheduler against isolated Update 23 fixtures."""

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


def test_get_requirements(kind, program_id):
    if kind == "program" and program_id == program["program_id"]:
        return program

    raise AssertionError(
        f"Unexpected program lookup: {kind}, {program_id}"
    )


def test_resolve_requirements(selected_program, history):
    return resolve_requirements(
        selected_program,
        history,
        pathway_file=PATHWAY_FILE,
    )

def assert_exported_schedule():
    """Verify the synthetic overlap schedule and credit accounting."""

    schedule_path = (
        ROOT / "backend" / "scheduler" / "results" / "schedule.json"
    )

    assert schedule_path.is_file(), (
        "Scheduler did not export schedule.json."
    )

    with schedule_path.open("r", encoding="utf-8") as file:
        schedule = json.load(file)

    assert schedule["status"] == "success", (
        f"Expected a successful schedule, got: {schedule['status']}"
    )

    semesters = {
        semester["term"]: semester
        for semester in schedule["semesters"]
    }

    assert set(semesters) == {"Fall 2026", "Spring 2027"}

    expected_courses = {
        "Fall 2026": {"CS 115": 2},
        "Spring 2027": {"CS 116": 2, "CS 350": 3},
    }

    all_codes = []

    for term, expected in expected_courses.items():
        semester = semesters[term]
        planned = semester["planned_courses"]

        actual = {
            course["code"]: course["credits"]
            for course in planned
        }

        assert len(actual) == len(planned), (
            f"Duplicate planned course in {term}"
        )

        assert actual == expected, (
            f"{term}: expected {expected}, got {actual}"
        )

        expected_credits = sum(expected.values())

        assert semester["planned_credits"] == expected_credits
        assert semester["total_credits"] == expected_credits
        assert semester["enrollment_warnings"] == []

        all_codes.extend(actual)

    assert len(all_codes) == len(set(all_codes)), (
        "A course appears in multiple semesters."
    )

    assert "CS 201" not in all_codes

    assert schedule["total_planned_credits"] == 7
    assert schedule["credit_summary"]["total_credits"] == 7
    assert schedule["credit_summary"]["undergraduate_credits"] == 7

    print("PASS: Scheduler exported a successful schedule.")
    print("PASS: Fall 2026 contains CS 115 (2 credits).")
    print("PASS: Spring 2027 contains CS 116 and CS 350 (5 credits).")
    print("PASS: No duplicate courses or CS 201 scheduling.")
    print("PASS: Total scheduled credits equal 7.")
    print("PASS: Both semesters satisfy enrollment constraints.")

def main():
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

    print("Running Update 23 synthetic scheduler integration test.")
    print("=======================================================")

    schedule_path = (
        ROOT / "backend" / "scheduler" / "results" / "schedule.json"
    )

    if schedule_path.exists():
        schedule_path.unlink()

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
        runpy.run_module(
            "backend.scheduler.scheduler_poc",
            run_name="__main__",
        )

    assert_exported_schedule()


if __name__ == "__main__":
    main()
