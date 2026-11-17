"""Integration tests for session-based academic scheduling."""

from backend.session.session_manager import SessionManager
from backend.scheduler.history_adapter import prepare_scheduler_history
from backend.transcript.transcript_validator import build_academic_history


def test_session_history_prepares_correct_scheduler_course_sets():
    courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
        {
            "code": "MATH 151",
            "title": "Calculus I",
            "credits": 5.0,
            "grade": "TR",
            "term": None,
            "level": None,
            "status": "transfer",
            "equivalency_verified": False,
        },
        {
            "code": "CS 115",
            "title": "Object-Oriented Programming",
            "credits": 2.0,
            "grade": "IP",
            "term": "Fall 2026",
            "level": "UG",
            "status": "in_progress",
        },
    ]

    history = build_academic_history(courses)

    assert history["validation_errors"] == []

    manager = SessionManager()
    session_id = manager.create_session()

    try:
        manager.store_academic_history(session_id, history)

        session_history = manager.get_academic_history(session_id)

        (
            scheduler_history,
            completed_codes,
            in_progress_codes,
        ) = prepare_scheduler_history(session_history)

        assert scheduler_history["validation_errors"] == []

        assert completed_codes == {"CS 100"}
        assert in_progress_codes == {"CS 115"}

        assert "MATH 151" not in completed_codes
        assert "CS 115" not in completed_codes
        assert "CS 100" not in in_progress_codes

    finally:
        manager.delete_session(session_id)


def test_verified_transfer_becomes_scheduler_eligible():
    courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
        {
            "code": "MATH 151",
            "title": "Calculus I",
            "credits": 5.0,
            "grade": "TR",
            "term": None,
            "level": None,
            "status": "transfer",
            "equivalency_verified": False,
        },
    ]

    original_history = build_academic_history(courses)

    manager = SessionManager()
    session_id = manager.create_session()

    try:
        manager.store_academic_history(
            session_id,
            original_history,
        )

        before_history = manager.get_academic_history(
            session_id
        )

        _, before_completed, _ = prepare_scheduler_history(
            before_history
        )

        assert before_completed == {"CS 100"}

        updated_history = manager.verify_session_transfer(
            session_id,
            index=0,
            verified=True,
            institutional_confirmation=True,
        )

        (
            scheduler_history,
            after_completed,
            after_in_progress,
        ) = prepare_scheduler_history(updated_history)

        assert scheduler_history["validation_errors"] == []

        assert after_completed == {
            "CS 100",
            "MATH 151",
        }

        assert after_in_progress == set()

        assert (
            original_history["transfer_courses"][0][
                "equivalency_verified"
            ]
            is False
        )

        assert (
            before_history["transfer_courses"][0][
                "equivalency_verified"
            ]
            is False
        )

        assert (
            scheduler_history["transfer_courses"][0][
                "equivalency_verified"
            ]
            is True
        )

    finally:
        manager.delete_session(session_id)


def test_session_grade_correction_updates_scheduler_eligibility():
    courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "F",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    original_history = build_academic_history(courses)

    manager = SessionManager()
    session_id = manager.create_session()

    try:
        manager.store_academic_history(
            session_id,
            original_history,
        )

        before_history = manager.get_academic_history(
            session_id
        )

        _, before_completed, _ = prepare_scheduler_history(
            before_history
        )

        assert "CS 100" not in before_completed

        corrected_history = manager.correct_session_course(
            session_id,
            collection="all_institution_records",
            index=0,
            changes={"grade": "A"},
        )

        (
            scheduler_history,
            after_completed,
            after_in_progress,
        ) = prepare_scheduler_history(corrected_history)

        assert scheduler_history["validation_errors"] == []

        assert "CS 100" in after_completed
        assert after_in_progress == set()

        assert (
            original_history["all_institution_records"][0]["grade"]
            == "F"
        )

        assert (
            before_history["all_institution_records"][0]["grade"]
            == "F"
        )

        assert (
            scheduler_history["all_institution_records"][0]["grade"]
            == "A"
        )

        stored_history = manager.get_academic_history(
            session_id
        )

        assert (
            stored_history["all_institution_records"][0]["grade"]
            == "A"
        )

    finally:
        manager.delete_session(session_id)


def test_student_sessions_keep_scheduler_histories_isolated():
    student_a_courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    student_b_courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "F",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    manager = SessionManager()

    session_a = manager.create_session()
    session_b = manager.create_session()

    try:
        manager.store_academic_history(
            session_a,
            build_academic_history(student_a_courses),
        )

        manager.store_academic_history(
            session_b,
            build_academic_history(student_b_courses),
        )

        _, completed_a, _ = prepare_scheduler_history(
            manager.get_academic_history(session_a)
        )

        _, completed_b, _ = prepare_scheduler_history(
            manager.get_academic_history(session_b)
        )

        assert completed_a == {"CS 100"}
        assert completed_b == set()

        manager.correct_session_course(
            session_b,
            collection="all_institution_records",
            index=0,
            changes={"grade": "A"},
        )

        _, updated_completed_b, _ = prepare_scheduler_history(
            manager.get_academic_history(session_b)
        )

        assert updated_completed_b == {"CS 100"}

        student_a_history = manager.get_academic_history(
            session_a
        )

        assert (
            student_a_history["all_institution_records"][0]["grade"]
            == "A"
        )

        _, updated_completed_a, _ = prepare_scheduler_history(
            student_a_history
        )

        assert updated_completed_a == {"CS 100"}

    finally:
        manager.delete_session(session_a)
        manager.delete_session(session_b)


def test_expired_session_cannot_supply_scheduler_history():
    from datetime import datetime, timedelta, timezone

    import pytest

    courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    manager = SessionManager()
    session_id = manager.create_session()

    manager.store_academic_history(
        session_id,
        build_academic_history(courses),
    )

    manager._sessions[session_id]["last_activity"] = (
        datetime.now(timezone.utc) - timedelta(minutes=31)
    )

    with pytest.raises(KeyError):
        prepare_scheduler_history(
            manager.get_academic_history(session_id)
        )

    assert session_id not in manager._sessions


def test_deleted_session_cannot_supply_scheduler_history():
    import pytest

    courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    manager = SessionManager()
    session_id = manager.create_session()

    manager.store_academic_history(
        session_id,
        build_academic_history(courses),
    )

    manager.delete_session(session_id)

    with pytest.raises(KeyError):
        prepare_scheduler_history(
            manager.get_academic_history(session_id)
        )

    assert session_id not in manager._sessions


def test_scheduler_history_resolver_accepts_in_memory_input():
    from backend.scheduler.history_adapter import load_scheduler_history

    courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    original = build_academic_history(courses)

    history, completed, in_progress = load_scheduler_history(
        raw_history=original
    )

    assert history["validation_errors"] == []
    assert completed == {"CS 100"}
    assert in_progress == set()
    assert original == build_academic_history(courses)


def test_scheduler_history_resolver_file_matches_memory(tmp_path):
    import json

    from backend.scheduler.history_adapter import load_scheduler_history

    courses = [
        {
            "code": "CS 100",
            "title": "Introduction to Computer Science",
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        },
    ]

    original = build_academic_history(courses)

    fixture_path = tmp_path / "synthetic_history.json"
    fixture_path.write_text(
        json.dumps(original),
        encoding="utf-8",
    )

    memory_result = load_scheduler_history(
        raw_history=original
    )

    file_result = load_scheduler_history(
        history_path=fixture_path
    )

    assert file_result == memory_result


def test_scheduler_history_resolver_rejects_ambiguous_inputs():
    import pytest

    from backend.scheduler.history_adapter import load_scheduler_history

    original = build_academic_history([])

    with pytest.raises(ValueError):
        load_scheduler_history()

    with pytest.raises(ValueError):
        load_scheduler_history(
            history_path="synthetic_history.json",
            raw_history=original,
        )


def test_scheduler_returns_unsatisfiable_in_memory():
    """Impossible schedules return structured results without disk writes."""
    from contextlib import redirect_stdout
    from copy import deepcopy
    from io import StringIO
    from pathlib import Path
    from unittest.mock import patch
    import hashlib
    import json

    from backend.scheduler.scheduler_poc import run_scheduler
    from backend.scheduler.requirement_resolver import resolve_requirements

    fixtures = Path("backend/tests/fixtures")

    program = json.loads(
        (fixtures / "update28_impossible_program.json").read_text(
            encoding="utf-8"
        )
    )

    history = json.loads(
        (fixtures / "update28_empty_history.json").read_text(
            encoding="utf-8"
        )
    )

    original_program = deepcopy(program)
    original_history = deepcopy(history)

    schedule_path = Path(
        "backend/scheduler/results/schedule.json"
    )

    def fingerprint():
        if not schedule_path.exists():
            return None

        return hashlib.sha256(
            schedule_path.read_bytes()
        ).hexdigest()

    before = fingerprint()

    def get_test_requirements(kind, program_id):
        assert kind == "program"
        assert program_id == program["program_id"]
        return program

    with (
        patch(
            "backend.scheduler.scheduler_poc.get_requirements",
            side_effect=get_test_requirements,
        ),
        patch(
            "backend.scheduler.scheduler_poc.resolve_requirements",
            side_effect=resolve_requirements,
        ),
        redirect_stdout(StringIO()),
    ):
        result = run_scheduler(
            raw_history=history,
            argv=[
                "--academic-level",
                "undergraduate",
                "--enrollment-status",
                "part_time",
                "--program-id",
                program["program_id"],
            ],
            return_result=True,
        )

    assert isinstance(result, dict)
    assert result["schema_version"] == "1.0"
    assert result["status"] == "unsatisfiable"

    assert set(result["candidate_courses"]) == {
        "ARCH 108",
        "ARCH 201",
    }

    assert result["semesters"] == []
    assert result["total_planned_credits"] == 0

    assert isinstance(result["message"], str)
    assert result["message"]

    assert history == original_history
    assert program == original_program
    assert fingerprint() == before


def test_scheduler_returns_insufficient_electives_in_memory():
    """Unavailable elective choices return a structured in-memory failure."""
    from contextlib import redirect_stdout
    from copy import deepcopy
    from io import StringIO
    from pathlib import Path
    from unittest.mock import patch
    import hashlib
    import json

    from backend.scheduler.scheduler_poc import run_scheduler
    from backend.scheduler.requirement_resolver import resolve_requirements

    fixtures = Path("backend/tests/fixtures")

    program = json.loads(
        (fixtures / "update23_overlap_program.json").read_text(
            encoding="utf-8"
        )
    )

    history = json.loads(
        (fixtures / "update23_overlap_history.json").read_text(
            encoding="utf-8"
        )
    )

    pathway_file = (
        fixtures / "update23_overlap_pathways.json"
    )

    original_program = deepcopy(program)
    original_history = deepcopy(history)

    test_program = deepcopy(program)
    elective = test_program["requirements"][0]["items"][0]
    elective["options"] = ["CS 998", "CS 999"]

    schedule_path = Path(
        "backend/scheduler/results/schedule.json"
    )

    def fingerprint():
        if not schedule_path.exists():
            return None

        return hashlib.sha256(
            schedule_path.read_bytes()
        ).hexdigest()

    before = fingerprint()

    def get_test_requirements(kind, program_id):
        assert kind == "program"
        assert program_id == test_program["program_id"]
        return test_program

    def resolve_test_requirements(selected_program, student_history):
        return resolve_requirements(
            selected_program,
            student_history,
            pathway_file=pathway_file,
        )

    with (
        patch(
            "backend.scheduler.scheduler_poc.get_requirements",
            side_effect=get_test_requirements,
        ),
        patch(
            "backend.scheduler.scheduler_poc.resolve_requirements",
            side_effect=resolve_test_requirements,
        ),
        redirect_stdout(StringIO()),
    ):
        result = run_scheduler(
            raw_history=history,
            argv=[
                "--academic-level",
                "undergraduate",
                "--enrollment-status",
                "part_time",
                "--program-id",
                test_program["program_id"],
            ],
            return_result=True,
        )

    assert isinstance(result, dict)
    assert result["schema_version"] == "1.0"
    assert result["status"] == "insufficient_elective_availability"

    assert result["message"] == (
        "Not enough available courses for "
        "Programming Elective: need 1, found 0"
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

    assert history == original_history
    assert program == original_program
    assert fingerprint() == before


def test_scheduler_returns_insufficient_pathways_in_memory():
    """Unavailable pathway alternatives return structured failure results."""
    from contextlib import redirect_stdout
    from copy import deepcopy
    from io import StringIO
    from pathlib import Path
    from unittest.mock import patch
    import hashlib
    import json

    from backend.scheduler.scheduler_poc import run_scheduler
    from backend.scheduler.requirement_resolver import resolve_requirements
    from backend.scheduler.catalog_adapter import CatalogAdapter

    fixtures = Path("backend/tests/fixtures")

    program = json.loads(
        (fixtures / "update23_overlap_program.json").read_text(
            encoding="utf-8"
        )
    )

    history = json.loads(
        (fixtures / "update23_overlap_history.json").read_text(
            encoding="utf-8"
        )
    )

    pathway_file = (
        fixtures / "update23_overlap_pathways.json"
    )

    original_program = deepcopy(program)
    original_history = deepcopy(history)

    schedule_path = Path(
        "backend/scheduler/results/schedule.json"
    )

    def fingerprint():
        if not schedule_path.exists():
            return None

        return hashlib.sha256(
            schedule_path.read_bytes()
        ).hexdigest()

    before = fingerprint()

    def get_test_requirements(kind, program_id):
        assert kind == "program"
        assert program_id == program["program_id"]
        return program

    def resolve_test_requirements(selected_program, student_history):
        return resolve_requirements(
            selected_program,
            student_history,
            pathway_file=pathway_file,
        )

    original_is_offered = CatalogAdapter.is_offered

    def controlled_availability(self, code, term):
        if code in {"CS 115", "CS 201"}:
            return False

        return original_is_offered(self, code, term)

    with (
        patch(
            "backend.scheduler.scheduler_poc.get_requirements",
            side_effect=get_test_requirements,
        ),
        patch(
            "backend.scheduler.scheduler_poc.resolve_requirements",
            side_effect=resolve_test_requirements,
        ),
        patch.object(
            CatalogAdapter,
            "is_offered",
            controlled_availability,
        ),
        redirect_stdout(StringIO()),
    ):
        result = run_scheduler(
            raw_history=history,
            argv=[
                "--academic-level",
                "undergraduate",
                "--enrollment-status",
                "part_time",
                "--program-id",
                program["program_id"],
            ],
            return_result=True,
        )

    assert isinstance(result, dict)
    assert result["schema_version"] == "1.0"
    assert result["status"] == "insufficient_pathway_availability"

    assert result["message"] == (
        "No schedulable alternatives for pathway: "
        "Programming Sequence"
    )

    assert result["candidate_courses"] == [
        "CS 115",
        "CS 116",
        "CS 201",
    ]

    assert result["unavailable_courses"] == [
        "CS 115",
        "CS 201",
    ]

    assert result["semesters"] == []
    assert result["total_planned_credits"] == 0

    assert history == original_history
    assert program == original_program
    assert fingerprint() == before


def test_scheduler_returns_no_schedulable_courses_in_memory():
    """Completed configured requirements produce no remaining course plan."""
    from contextlib import redirect_stdout
    from copy import deepcopy
    from io import StringIO
    from pathlib import Path
    from unittest.mock import patch
    import hashlib
    import json

    from backend.scheduler.scheduler_poc import run_scheduler
    from backend.scheduler.requirement_resolver import resolve_requirements

    fixtures = Path("backend/tests/fixtures")

    program = json.loads(
        (fixtures / "update25_prerequisite_program.json").read_text(
            encoding="utf-8"
        )
    )

    history = json.loads(
        (fixtures / "update25_prerequisite_history.json").read_text(
            encoding="utf-8"
        )
    )

    completed_courses = [
        {
            "code": code,
            "title": code,
            "credits": 3.0,
            "grade": "A",
            "term": "Fall 2025",
            "level": "UG",
            "status": "institution",
        }
        for code in ("ARCH 107", "ARCH 108")
    ]

    history["completed_courses"] = completed_courses
    history["scheduler_course_codes"] = [
        "ARCH 107",
        "ARCH 108",
    ]
    history["all_institution_records"] = deepcopy(
        completed_courses
    )

    original_history = deepcopy(history)
    original_program = deepcopy(program)

    schedule_path = Path(
        "backend/scheduler/results/schedule.json"
    )

    def fingerprint():
        if not schedule_path.exists():
            return None

        return hashlib.sha256(
            schedule_path.read_bytes()
        ).hexdigest()

    before = fingerprint()

    def get_test_requirements(kind, program_id):
        assert kind == "program"
        assert program_id == program["program_id"]
        return program

    with (
        patch(
            "backend.scheduler.scheduler_poc.get_requirements",
            side_effect=get_test_requirements,
        ),
        patch(
            "backend.scheduler.scheduler_poc.resolve_requirements",
            side_effect=resolve_requirements,
        ),
        redirect_stdout(StringIO()),
    ):
        result = run_scheduler(
            raw_history=history,
            argv=[
                "--academic-level",
                "undergraduate",
                "--enrollment-status",
                "part_time",
                "--program-id",
                program["program_id"],
            ],
            return_result=True,
        )

    assert isinstance(result, dict)
    assert result["schema_version"] == "1.0"
    assert result["status"] == "no_schedulable_courses"

    assert result["candidate_courses"] == []
    assert result["unavailable_courses"] == []
    assert result["semesters"] == []
    assert result["total_planned_credits"] == 0

    assert isinstance(result["message"], str)
    assert result["message"]

    assert history == original_history
    assert program == original_program
    assert fingerprint() == before


def test_scheduler_returns_success_in_memory():
    """A valid prerequisite plan returns an in-memory schedule."""
    from contextlib import redirect_stdout
    from copy import deepcopy
    from io import StringIO
    from pathlib import Path
    from unittest.mock import patch
    import hashlib
    import json

    from backend.scheduler.scheduler_poc import run_scheduler
    from backend.scheduler.requirement_resolver import resolve_requirements

    fixtures = Path("backend/tests/fixtures")

    program = json.loads(
        (fixtures / "update25_prerequisite_program.json").read_text(
            encoding="utf-8"
        )
    )

    history = json.loads(
        (fixtures / "update25_prerequisite_history.json").read_text(
            encoding="utf-8"
        )
    )

    original_program = deepcopy(program)
    original_history = deepcopy(history)

    schedule_path = Path(
        "backend/scheduler/results/schedule.json"
    )

    def fingerprint():
        if not schedule_path.exists():
            return None

        return hashlib.sha256(
            schedule_path.read_bytes()
        ).hexdigest()

    before = fingerprint()

    def get_test_requirements(kind, program_id):
        assert kind == "program"
        assert program_id == program["program_id"]
        return program

    with (
        patch(
            "backend.scheduler.scheduler_poc.get_requirements",
            side_effect=get_test_requirements,
        ),
        patch(
            "backend.scheduler.scheduler_poc.resolve_requirements",
            side_effect=resolve_requirements,
        ),
        redirect_stdout(StringIO()),
    ):
        result = run_scheduler(
            raw_history=history,
            argv=[
                "--academic-level",
                "undergraduate",
                "--enrollment-status",
                "part_time",
                "--program-id",
                program["program_id"],
            ],
            return_result=True,
        )

    assert isinstance(result, dict)
    assert result["schema_version"] == "1.0"
    assert result["status"] == "success"

    assert result["total_planned_credits"] == 6

    semesters = {
        semester["term"]: semester
        for semester in result["semesters"]
    }

    assert "Fall 2026" in semesters
    assert "Spring 2027" in semesters

    fall_courses = [
        course["code"]
        for course in semesters["Fall 2026"]["planned_courses"]
    ]

    spring_courses = [
        course["code"]
        for course in semesters["Spring 2027"]["planned_courses"]
    ]

    assert fall_courses == ["ARCH 107"]
    assert spring_courses == ["ARCH 108"]

    assert history == original_history
    assert program == original_program
    assert fingerprint() == before


def test_session_bridge_generates_schedule_in_memory():
    """A stored advising session can produce a valid in-memory schedule."""
    from contextlib import redirect_stdout
    from copy import deepcopy
    from io import StringIO
    from pathlib import Path
    from unittest.mock import patch
    import hashlib
    import json

    from backend.session.session_manager import SessionManager
    from backend.session.scheduler_bridge import schedule_session
    from backend.scheduler.requirement_resolver import resolve_requirements

    fixtures = Path("backend/tests/fixtures")

    program = json.loads(
        (fixtures / "update25_prerequisite_program.json").read_text(
            encoding="utf-8"
        )
    )

    history = json.loads(
        (fixtures / "update25_prerequisite_history.json").read_text(
            encoding="utf-8"
        )
    )

    original_history = deepcopy(history)
    original_program = deepcopy(program)

    schedule_path = Path(
        "backend/scheduler/results/schedule.json"
    )

    def fingerprint():
        if not schedule_path.exists():
            return None

        return hashlib.sha256(
            schedule_path.read_bytes()
        ).hexdigest()

    before = fingerprint()

    manager = SessionManager()
    session_id = manager.create_session()

    manager.store_academic_history(session_id, history)

    stored_before = manager.get_academic_history(session_id)

    def get_test_requirements(kind, program_id):
        assert kind == "program"
        assert program_id == program["program_id"]
        return program

    with (
        patch(
            "backend.scheduler.scheduler_poc.get_requirements",
            side_effect=get_test_requirements,
        ),
        patch(
            "backend.scheduler.scheduler_poc.resolve_requirements",
            side_effect=resolve_requirements,
        ),
        redirect_stdout(StringIO()),
    ):
        result = schedule_session(
            manager,
            session_id,
            academic_level="undergraduate",
            enrollment_status="part_time",
            program_id=program["program_id"],
        )

    assert isinstance(result, dict)
    assert result["schema_version"] == "1.0"
    assert result["status"] == "success"
    assert result["total_planned_credits"] == 6

    semesters = {
        semester["term"]: semester
        for semester in result["semesters"]
    }

    assert set(semesters) == {
        "Fall 2026",
        "Spring 2027",
    }

    fall_courses = [
        course["code"]
        for course in semesters["Fall 2026"]["planned_courses"]
    ]

    spring_courses = [
        course["code"]
        for course in semesters["Spring 2027"]["planned_courses"]
    ]

    assert fall_courses == ["ARCH 107"]
    assert spring_courses == ["ARCH 108"]

    assert manager.get_academic_history(session_id) == stored_before
    assert history == original_history
    assert program == original_program
    assert fingerprint() == before


def test_session_bridge_rejects_missing_academic_history():
    """A session without stored history cannot request a schedule."""
    from unittest.mock import patch
    import pytest

    from backend.session.session_manager import SessionManager
    from backend.session.scheduler_bridge import schedule_session

    manager = SessionManager()
    session_id = manager.create_session()

    with patch(
        "backend.session.scheduler_bridge.run_scheduler"
    ) as scheduler:
        with pytest.raises(
            ValueError,
            match="no stored academic history",
        ):
            schedule_session(
                manager,
                session_id,
                academic_level="undergraduate",
                enrollment_status="part_time",
                program_id="computer-science:bs-bac-ba",
            )

        scheduler.assert_not_called()


def test_session_bridge_rejects_expired_session():
    """An expired session cannot invoke the scheduling engine."""
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch
    import pytest

    from backend.session.session_manager import (
        SESSION_TIMEOUT,
        SessionManager,
    )
    from backend.session.scheduler_bridge import schedule_session

    manager = SessionManager()
    session_id = manager.create_session()

    manager._sessions[session_id]["last_activity"] = (
        datetime.now(timezone.utc)
        - SESSION_TIMEOUT
        - timedelta(seconds=1)
    )

    with patch(
        "backend.session.scheduler_bridge.run_scheduler"
    ) as scheduler:
        with pytest.raises(
            KeyError,
            match="expired",
        ):
            schedule_session(
                manager,
                session_id,
                academic_level="undergraduate",
                enrollment_status="part_time",
                program_id="computer-science:bs-bac-ba",
            )

        scheduler.assert_not_called()

    assert session_id not in manager._sessions


def test_session_bridge_rejects_deleted_session():
    """A deleted advising session cannot invoke the scheduler."""
    from unittest.mock import patch
    import pytest

    from backend.session.session_manager import SessionManager
    from backend.session.scheduler_bridge import schedule_session

    manager = SessionManager()
    session_id = manager.create_session()

    manager.delete_session(session_id)

    with patch(
        "backend.session.scheduler_bridge.run_scheduler"
    ) as scheduler:
        with pytest.raises(
            KeyError,
            match="not found",
        ):
            schedule_session(
                manager,
                session_id,
                academic_level="undergraduate",
                enrollment_status="part_time",
                program_id="computer-science:bs-bac-ba",
            )

        scheduler.assert_not_called()

    assert session_id not in manager._sessions
