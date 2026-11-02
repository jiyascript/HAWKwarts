import json
from pathlib import Path

SCHEDULE_PATH = (
    Path(__file__).resolve().parent
    / "results"
    / "schedule.json"
)

def test_schedule_output():
    with SCHEDULE_PATH.open("r", encoding="utf-8") as file:
        result = json.load(file)

    assert result["schema_version"] == "1.0"
    assert result["status"] == "success"
    assert result["academic_level"] in {
        "undergraduate", "graduate", "coterminal"
    }
    assert result["enrollment_status"] in {
        "full_time", "part_time"
    }

    semesters = result["semesters"]
    assert isinstance(semesters, list)

    for semester in semesters:
        assert isinstance(semester["term"], str)
        assert isinstance(semester["existing_courses"], list)
        assert isinstance(semester["planned_courses"], list)

        for course in (
            semester["existing_courses"]
            + semester["planned_courses"]
        ):
            assert isinstance(course["code"], str)
            assert course["course_level"] in {
                "undergraduate", "graduate", "unknown"
            }
            assert course["credits"] > 0

        assert (
            semester["existing_credits"]
            + semester["planned_credits"]
            == semester["total_credits"]
        )

        assert (
            semester["total_undergraduate_credits"]
            + semester["total_graduate_credits"]
            + semester["total_unknown_level_credits"]
            == semester["total_credits"]
        )

    summary = result["credit_summary"]

    assert summary["total_credits"] == sum(
        semester["total_credits"]
        for semester in semesters
    )

    assert (
        summary["undergraduate_credits"]
        + summary["graduate_credits"]
        + summary["unknown_level_credits"]
        == summary["total_credits"]
    )

    assert result["total_planned_credits"] == sum(
        semester["planned_credits"]
        for semester in semesters
    )

    print("All scheduler JSON contract tests passed!")

def test_failure_schedule_output():
    from tempfile import TemporaryDirectory
    from backend.scheduler.schedule_export import export_failure_json

    with TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "schedule.json"

        export_failure_json(
            output_path=output_path,
            status="unsatisfiable",
            message="No valid schedule satisfies the constraints.",
            candidate_courses=["CS 512", "CS 513"],
            unavailable_courses=[]
        )

        result = json.loads(
            output_path.read_text(encoding="utf-8")
        )

        assert result["schema_version"] == "1.0"
        assert result["status"] == "unsatisfiable"
        assert isinstance(result["message"], str)
        assert result["semesters"] == []
        assert result["total_planned_credits"] == 0
        assert result["candidate_courses"] == [
            "CS 512", "CS 513"
        ]

        print("All failure schedule JSON tests passed!")

if __name__ == "__main__":
    test_schedule_output()
    test_failure_schedule_output()
